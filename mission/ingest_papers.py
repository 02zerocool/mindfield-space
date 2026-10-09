"""
ingest_papers.py — Academic paper ingest for Mindfield
=======================================================
Purpose-built for researchers. Handles:
  - PDF extraction via pymupdf (much better than pypdf for academic papers)
  - BibTeX metadata (.bib files) → author, year, journal, DOI stored in tags
  - Section-aware chunking (Abstract kept whole, Methods/Results/Discussion preserved)
  - Source deduplication (won't re-ingest a paper already in your field)
  - arXiv fetch by ID (fetches PDF + metadata from arxiv.org)
  - Jupyter notebook (.ipynb) support
  - Direct note-writing to memory field

Usage:
  # Ingest a directory of PDFs (dry run first)
  python research/ingest_papers.py --dry-run --dir papers/

  # Ingest with BibTeX metadata
  python research/ingest_papers.py --ingest --dir papers/ --bib library.bib

  # Fetch and ingest an arXiv paper by ID
  python research/ingest_papers.py --arxiv 2305.12345

  # Write a quick note directly to your memory field
  python research/ingest_papers.py --note "Just read Smith 2023 — key insight: X" --source "my_notes"

Options:
  --lean-url URL      lean_api base URL        (default: http://127.0.0.1:8018)
  --dir PATH          directory of papers to ingest
  --bib FILE          BibTeX file for metadata (.bib from Zotero/Mendeley)
  --arxiv ID          fetch paper from arXiv by ID (e.g. 2305.12345)
  --note TEXT         write a note directly to memory
  --source NAME       source label override
  --dry-run           preview only — no writes
  --ingest            write to LanceDB
  --force             re-ingest even if source already exists
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path


# ── PDF extraction ────────────────────────────────────────────────────────────

def extract_pdf_pymupdf(path: Path) -> str:
    """Extract text via pymupdf — handles two-column layouts, tables, equations."""
    import fitz  # pymupdf
    doc = fitz.open(str(path))
    pages = []
    for page in doc:
        # sort=True preserves reading order (critical for two-column papers)
        pages.append(page.get_text(sort=True))
    doc.close()
    return "\n\n".join(pages)


def extract_pdf_pypdf(path: Path) -> str:
    """Fallback PDF extraction via pypdf."""
    import pypdf
    reader = pypdf.PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def extract_pdf(path: Path) -> str:
    try:
        return extract_pdf_pymupdf(path)
    except ImportError:
        pass
    try:
        return extract_pdf_pypdf(path)
    except ImportError:
        print(f"  [!] No PDF library found. Install pymupdf: pip install pymupdf")
        return ""


def extract_notebook(path: Path) -> str:
    """Extract prose and markdown from a Jupyter notebook (.ipynb)."""
    try:
        nb = json.loads(path.read_text(encoding="utf-8"))
        parts = []
        for cell in nb.get("cells", []):
            if cell.get("cell_type") in ("markdown", "raw"):
                src = "".join(cell.get("source", []))
                if src.strip():
                    parts.append(src)
            elif cell.get("cell_type") == "code":
                # Include code outputs (text/plain) — often contain results
                for output in cell.get("outputs", []):
                    text = output.get("text", [])
                    if isinstance(text, list):
                        text = "".join(text)
                    if text.strip():
                        parts.append(f"[output] {text[:500]}")
        return "\n\n".join(parts)
    except Exception as e:
        print(f"  [!] notebook parse failed: {e}")
        return ""


def extract_text(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in (".txt", ".md", ".rst"):
        return path.read_text(encoding="utf-8", errors="replace")
    elif ext == ".pdf":
        return extract_pdf(path)
    elif ext == ".ipynb":
        return extract_notebook(path)
    return ""


# ── BibTeX parser ─────────────────────────────────────────────────────────────

def parse_bib(bib_path: Path) -> dict:
    """
    Parse a BibTeX file into a dict keyed by cite-key.
    Each entry: {"author": ..., "year": ..., "title": ..., "journal": ...,
                 "doi": ..., "abstract": ...}
    No external deps — minimal regex parser.
    """
    text = bib_path.read_text(encoding="utf-8", errors="replace")
    entries = {}

    # Match each @TYPE{key, ... }
    for m in re.finditer(r'@\w+\s*\{\s*([^,\s]+)\s*,', text):
        key   = m.group(1).strip()
        start = m.end()
        # Find the matching closing brace
        depth = 1
        pos   = start
        while pos < len(text) and depth > 0:
            if text[pos] == '{':
                depth += 1
            elif text[pos] == '}':
                depth -= 1
            pos += 1
        body = text[start:pos - 1]

        entry = {}
        for field in ("author", "year", "title", "journal", "booktitle", "doi", "abstract", "pages", "volume"):
            fm = re.search(rf'\b{field}\s*=\s*[{{"](.+?)[}}"]\s*[,}}]', body, re.IGNORECASE | re.DOTALL)
            if fm:
                val = fm.group(1).strip()
                val = re.sub(r'\s+', ' ', val)       # normalise whitespace
                val = val.replace('{', '').replace('}', '')  # strip bib braces
                entry[field] = val

        if entry:
            entries[key] = entry

    return entries


def bib_key_for_file(filename: str, bib: dict) -> dict | None:
    """
    Try to match a PDF filename to a BibTeX entry.
    Matches on cite-key, or on author+year if cite-key doesn't match.
    """
    stem = Path(filename).stem.lower()

    # Direct cite-key match
    for key, entry in bib.items():
        if key.lower() == stem:
            return entry

    # Fuzzy: first author surname + year appears in filename
    for key, entry in bib.items():
        author = entry.get("author", "")
        year   = entry.get("year", "")
        # Extract first author surname
        surname = re.split(r'[,\s]', author)[0].lower()
        if surname and year and surname in stem and year in stem:
            return entry

    return None


def bib_to_tags(entry: dict) -> list:
    """Convert a BibTeX entry to a tags list for lean_api /write."""
    tags = []
    if entry.get("author"):
        # First author surname only
        surname = re.split(r'[,\s]', entry["author"])[0]
        tags.append(f"author:{surname}")
    if entry.get("year"):
        tags.append(f"year:{entry['year']}")
    if entry.get("journal") or entry.get("booktitle"):
        venue = entry.get("journal") or entry.get("booktitle")
        tags.append(f"venue:{venue[:40]}")
    if entry.get("doi"):
        tags.append(f"doi:{entry['doi']}")
    return tags


# ── Section-aware chunking ────────────────────────────────────────────────────

SECTION_HEADINGS = re.compile(
    r'^(abstract|introduction|background|related work|methods?|methodology|'
    r'materials and methods|experimental|results?|findings?|discussion|'
    r'conclusions?|summary|references?|acknowledgements?)\s*$',
    re.IGNORECASE | re.MULTILINE
)


def chunk_academic(text: str, chunk_size: int = 1200, overlap: int = 150) -> list[str]:
    """
    Section-aware chunking for academic papers.
    - Abstract is kept as a single chunk (whole section)
    - Other sections are chunked at chunk_size with paragraph preference
    - Overlap bridges chunk boundaries
    """
    text = re.sub(r'\n{3,}', '\n\n', text.strip())

    # Split into sections at heading boundaries
    parts  = SECTION_HEADINGS.split(text)
    heads  = SECTION_HEADINGS.findall(text)
    # parts = [pre-abstract text, heading, body, heading, body, ...]

    chunks = []
    section_name = ""

    def _chunk_body(body: str, section: str) -> list[str]:
        """Chunk a section body with overlap, preferring paragraph breaks."""
        body = body.strip()
        if not body:
            return []
        # Abstract: always one chunk
        if "abstract" in section.lower():
            return [f"Abstract\n\n{body}"] if body else []
        result = []
        pos    = 0
        while pos < len(body):
            end = pos + chunk_size
            if end < len(body):
                para = body.rfind("\n\n", pos, end)
                if para > pos + chunk_size // 2:
                    end = para
                else:
                    sent = max(body.rfind(". ", pos, end), body.rfind(".\n", pos, end))
                    if sent > pos + chunk_size // 2:
                        end = sent + 1
            chunk = body[pos:end].strip()
            if chunk:
                prefix = f"{section.strip().title()}\n\n" if section else ""
                result.append(prefix + chunk)
            pos = end - overlap if end < len(body) else len(body)
        return result

    # Handle preamble (before first heading)
    if parts:
        preamble = parts[0].strip()
        if preamble:
            chunks.extend(_chunk_body(preamble, ""))

    # Handle heading + body pairs
    for i, head in enumerate(heads):
        body_idx = i * 2 + 2  # interleaved: part[0]=pre, part[1]=head1, part[2]=body1...
        body = parts[body_idx].strip() if body_idx < len(parts) else ""
        # Skip reference lists — they're rarely useful in semantic search
        if "reference" in head.lower():
            continue
        chunks.extend(_chunk_body(body, head))

    return [c for c in chunks if c.strip()]


# ── arXiv fetch ───────────────────────────────────────────────────────────────

def fetch_arxiv(arxiv_id: str, download_dir: Path) -> tuple[Path | None, dict]:
    """
    Fetch a paper from arXiv.
    Returns (pdf_path, metadata_dict) or (None, {}) on failure.

    metadata keys: title, author, year, doi, abstract
    """
    # Normalise ID — strip version suffix for metadata query
    clean_id = re.sub(r'v\d+$', '', arxiv_id.strip())

    # Fetch metadata via Atom API
    api_url = f"https://export.arxiv.org/api/query?id_list={clean_id}"
    meta = {}
    try:
        with urllib.request.urlopen(api_url, timeout=15) as r:
            xml = r.read().decode("utf-8")
        # Extract fields with simple regex (no lxml dependency)
        title_m   = re.search(r'<title>(.+?)</title>', xml, re.DOTALL)
        author_ms = re.findall(r'<name>(.+?)</name>', xml)
        pub_m     = re.search(r'<published>(\d{4})', xml)
        doi_m     = re.search(r'<arxiv:doi[^>]*>(.+?)</arxiv:doi>', xml)
        abs_m     = re.search(r'<summary>(.+?)</summary>', xml, re.DOTALL)

        if title_m:
            meta["title"]    = re.sub(r'\s+', ' ', title_m.group(1)).strip()
        if author_ms:
            meta["author"]   = author_ms[0]   # first author
        if pub_m:
            meta["year"]     = pub_m.group(1)
        if doi_m:
            meta["doi"]      = doi_m.group(1).strip()
        if abs_m:
            meta["abstract"] = re.sub(r'\s+', ' ', abs_m.group(1)).strip()

        print(f"  arXiv metadata: '{meta.get('title','?')}' ({meta.get('year','?')})")
    except Exception as e:
        print(f"  [!] arXiv metadata fetch failed: {e}")

    # Download PDF
    pdf_url  = f"https://arxiv.org/pdf/{clean_id}"
    pdf_path = download_dir / f"arxiv_{clean_id.replace('/', '_')}.pdf"
    try:
        print(f"  Downloading PDF from {pdf_url} ...")
        urllib.request.urlretrieve(pdf_url, str(pdf_path))
        print(f"  Saved: {pdf_path.name}  ({pdf_path.stat().st_size // 1024} KB)")
    except Exception as e:
        print(f"  [!] PDF download failed: {e}")
        return None, meta

    return pdf_path, meta


# ── lean_api helpers ──────────────────────────────────────────────────────────

def lean_health(lean_url: str) -> bool:
    try:
        with urllib.request.urlopen(f"{lean_url}/health", timeout=5) as r:
            h = json.loads(r.read())
            print(f"  lean_api health: {h}")
            return True
    except Exception as e:
        print(f"  [!] Cannot reach lean_api at {lean_url}: {e}")
        return False


def lean_sources(lean_url: str) -> set:
    """Return set of source labels already in the memory field."""
    try:
        payload = json.dumps({"query": "_all_", "k": 1000}).encode()
        req = urllib.request.Request(
            f"{lean_url}/search",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
        return {row.get("source", "") for row in data.get("results", [])}
    except Exception:
        return set()


def write_chunk(lean_url: str, content: str, source: str, tags: list) -> bool:
    payload = json.dumps({"content": content, "source": source, "tags": tags}).encode()
    req = urllib.request.Request(
        f"{lean_url}/write",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read()).get("ok", False)
    except Exception as e:
        print(f"    [!] write failed: {e}")
        return False


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Academic paper ingest for Mindfield")
    parser.add_argument("--dry-run",   action="store_true")
    parser.add_argument("--ingest",    action="store_true")
    parser.add_argument("--force",     action="store_true", help="Re-ingest even if source exists")
    parser.add_argument("--dir",       type=Path, help="Directory of papers/notebooks to ingest")
    parser.add_argument("--bib",       type=Path, help="BibTeX file for metadata")
    parser.add_argument("--arxiv",     type=str,  help="Fetch arXiv paper by ID")
    parser.add_argument("--note",      type=str,  help="Write a note directly to memory")
    parser.add_argument("--source",    type=str,  default="", help="Source label override")
    parser.add_argument("--lean-url",  default="http://127.0.0.1:8018")
    parser.add_argument("--chunk-size",type=int,  default=1200)
    args = parser.parse_args()

    if not any([args.dry_run, args.ingest, args.arxiv, args.note]):
        print("Specify --dry-run, --ingest, --arxiv ID, or --note TEXT")
        sys.exit(1)

    lean_url = args.lean_url

    # ── Direct note ──────────────────────────────────────────────────────────
    if args.note:
        if not lean_health(lean_url):
            sys.exit(1)
        source = args.source or "notes"
        ok = write_chunk(lean_url, args.note, source, ["type:note"])
        print(f"  {'Written' if ok else 'FAILED'}: {args.note[:80]}")
        return

    # ── arXiv fetch ──────────────────────────────────────────────────────────
    if args.arxiv:
        download_dir = Path(args.dir) if args.dir else Path("ingest/ingest_queue")
        download_dir.mkdir(parents=True, exist_ok=True)
        pdf_path, meta = fetch_arxiv(args.arxiv, download_dir)
        if pdf_path is None:
            sys.exit(1)
        if args.ingest:
            if not lean_health(lean_url):
                sys.exit(1)
            text   = extract_pdf(pdf_path)
            chunks = chunk_academic(text, args.chunk_size)
            source = args.source or f"arxiv_{args.arxiv}"
            tags   = bib_to_tags(meta)
            tags.append("type:arxiv")
            print(f"\n  Ingesting {len(chunks)} chunks from arXiv:{args.arxiv} ...")
            ok_count = sum(write_chunk(lean_url, c, source, tags) for c in chunks)
            print(f"  Done. Written: {ok_count}/{len(chunks)}")
        else:
            text   = extract_pdf(pdf_path) if pdf_path else ""
            chunks = chunk_academic(text, args.chunk_size) if text else []
            print(f"\n  Dry run: would ingest {len(chunks)} chunks")
            print(f"  Metadata: {meta}")
        return

    # ── Directory ingest ──────────────────────────────────────────────────────
    if not args.dir:
        print("Specify --dir PATH")
        sys.exit(1)

    source_dir = Path(args.dir)
    if not source_dir.exists():
        print(f"Directory not found: {source_dir}")
        sys.exit(1)

    SUPPORTED = {".txt", ".md", ".rst", ".pdf", ".ipynb"}
    SKIP      = {"readme.md", "readme.txt", ".gitkeep"}
    files     = [f for f in source_dir.iterdir()
                 if f.is_file()
                 and f.suffix.lower() in SUPPORTED
                 and f.name.lower() not in SKIP]

    if not files:
        print(f"No supported files in {source_dir}")
        sys.exit(0)

    # Load BibTeX
    bib = {}
    if args.bib:
        bib = parse_bib(Path(args.bib))
        print(f"  BibTeX: loaded {len(bib)} entries from {args.bib}")

    # Check existing sources to skip duplicates
    existing = set()
    if args.ingest and not args.force:
        print("  Checking existing sources in memory field...")
        existing = lean_sources(lean_url)
        if existing:
            print(f"  Found {len(existing)} existing sources — will skip duplicates (use --force to override)")

    print(f"\n{'DRY RUN' if args.dry_run else 'INGEST MODE'}")
    print(f"Files: {len(files)}  BibTeX entries: {len(bib)}\n")

    plan = []
    for f in sorted(files):
        source = args.source or f.stem
        if source in existing:
            print(f"  SKIP  {f.name}  (already in memory field — use --force to re-ingest)")
            continue
        text = extract_text(f)
        if not text.strip():
            print(f"  SKIP  {f.name}  (no text extracted)")
            continue
        chunks = chunk_academic(text, args.chunk_size)
        meta   = bib_key_for_file(f.name, bib) if bib else None
        tags   = bib_to_tags(meta) if meta else []
        if f.suffix.lower() == ".ipynb":
            tags.append("type:notebook")
        elif f.suffix.lower() == ".pdf":
            tags.append("type:paper")
        print(f"  {f.name:<50}  {len(chunks):>4} chunks  {len(tags)} tags  source='{source}'")
        plan.append((f, chunks, source, tags))

    total = sum(len(c) for _, c, _, _ in plan)
    print(f"\nTotal: {total} chunks from {len(plan)} files")

    if args.dry_run:
        print("\nDry run complete. Run with --ingest to write.")
        return

    if not lean_health(lean_url):
        sys.exit(1)

    print(f"\nWriting {total} chunks...\n")
    written = failed = 0
    for f, chunks, source, tags in plan:
        print(f"  {f.name}  ({len(chunks)} chunks)...")
        for i, chunk in enumerate(chunks):
            if write_chunk(lean_url, chunk, source, tags):
                written += 1
            else:
                failed += 1
            if (i + 1) % 20 == 0:
                print(f"    {i+1}/{len(chunks)}...")
            time.sleep(0.02)
        print(f"    done")

    print(f"\nComplete. Written: {written}  Failed: {failed}")
    if failed == 0:
        print("Verify: curl http://127.0.0.1:8018/stats")


if __name__ == "__main__":
    main()
