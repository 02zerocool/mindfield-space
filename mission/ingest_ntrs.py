"""
ingest_ntrs.py — NASA Technical Reports Server ingest
======================================================
Searches NTRS (ntrs.nasa.gov) and ingests reports into your memory field.
All NASA technical reports are public domain. No authentication required.

Usage:
  # Search and preview
  python mission/ingest_ntrs.py --query "orbital debris mitigation" --k 20 --dry-run

  # Search and ingest
  python mission/ingest_ntrs.py --query "ECLSS water recovery" --k 10 --ingest

  # Fetch a specific report by NTRS ID
  python mission/ingest_ntrs.py --id 19940013935 --ingest

  # Ingest with full PDF text (when available)
  python mission/ingest_ntrs.py --query "entry descent landing" --k 10 --ingest --full-text

Options:
  --lean-url URL    lean_api base URL  (default: http://127.0.0.1:8018)
  --query TEXT      search query
  --k N             number of results to fetch (default: 10)
  --id ID           fetch a specific NTRS document ID
  --ingest          write to memory field
  --dry-run         preview only
  --full-text       attempt to download and extract full PDF text
  --domain-url URL  ingest into a domain lean_api (e.g. http://127.0.0.1:18003)
"""

import argparse
import json
import sys
import time
import urllib.request
import urllib.parse
from pathlib import Path
import tempfile

NTRS_API  = "https://ntrs.nasa.gov/api/citations"


# ── NTRS API ──────────────────────────────────────────────────────────────────

def ntrs_search(query: str, rows: int = 10, start: int = 0) -> list[dict]:
    """Search NTRS. Returns list of citation records."""
    params = urllib.parse.urlencode({
        "q":     query,
        "rows":  rows,
        "start": start,
    })
    url = f"{NTRS_API}/search?{params}"
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            data = json.loads(r.read())
        return data.get("results", [])
    except Exception as e:
        print(f"  [!] NTRS search failed: {e}")
        return []


def ntrs_fetch(ntrs_id: str | int) -> dict | None:
    """Fetch a single NTRS citation by ID."""
    url = f"{NTRS_API}/{ntrs_id}"
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"  [!] NTRS fetch failed for {ntrs_id}: {e}")
        return None


def ntrs_download_pdf(ntrs_id: str | int, record: dict, dest_dir: Path) -> Path | None:
    """
    Download the first available PDF for a NTRS record.
    Returns path to downloaded file, or None if unavailable.
    """
    downloads = record.get("downloads", [])
    # Prefer 'Full Text' type, then any PDF
    pdf_entry = None
    for d in downloads:
        if d.get("fileType", "").upper() == "STI" or d.get("links", {}).get("original"):
            pdf_entry = d
            break
    if not pdf_entry and downloads:
        pdf_entry = downloads[0]
    if not pdf_entry:
        return None

    links = pdf_entry.get("links", {})
    url   = links.get("original") or links.get("pdf")
    if not url:
        return None

    fname  = pdf_entry.get("fileName", f"ntrs_{ntrs_id}.pdf")
    dest   = dest_dir / fname
    try:
        urllib.request.urlretrieve(url, str(dest))
        return dest
    except Exception as e:
        print(f"    [!] PDF download failed: {e}")
        return None


# ── Metadata → memory ─────────────────────────────────────────────────────────

def record_to_metadata(record: dict) -> tuple[str, str, list[str]]:
    """
    Extract (source_label, abstract_text, tags) from an NTRS record.
    """
    ntrs_id = record.get("id", "")
    title   = record.get("title", "").strip()
    authors = record.get("authorsList", [])
    date    = record.get("publicationDate", "")[:10]
    year    = date[:4] if date else ""
    rnum    = record.get("reportNumber", "")
    abstract= record.get("abstract", "").strip()
    center  = record.get("center", {}).get("name", "")

    first_author = authors[0] if authors else ""
    source = f"ntrs_{ntrs_id}"
    if first_author and year:
        surname = first_author.split()[-1].lower()
        source  = f"{surname}_{year}_ntrs{ntrs_id}"

    tags = ["type:ntrs"]
    if first_author:
        tags.append(f"author:{first_author.split()[-1]}")
    if year:
        tags.append(f"year:{year}")
    if rnum:
        tags.append(f"report:{rnum}")
    if center:
        tags.append(f"center:{center[:30]}")

    # Build the abstract chunk — title + abstract together for context
    content = ""
    if title:
        content += f"{title}\n\n"
    if abstract:
        content += abstract

    return source, content, tags


# ── lean_api helpers ──────────────────────────────────────────────────────────

def lean_health(lean_url: str) -> bool:
    try:
        with urllib.request.urlopen(f"{lean_url}/health", timeout=5) as r:
            print(f"  lean_api: {json.loads(r.read())}")
            return True
    except Exception as e:
        print(f"  [!] Cannot reach lean_api at {lean_url}: {e}")
        return False


def write_chunk(lean_url: str, content: str, source: str, tags: list) -> bool:
    if not content.strip():
        return False
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


def extract_pdf_text(pdf_path: Path) -> str:
    """Extract text from downloaded PDF. Tries pymupdf then pypdf."""
    try:
        import fitz
        doc = fitz.open(str(pdf_path))
        return "\n\n".join(p.get_text(sort=True) for p in doc)
    except ImportError:
        pass
    try:
        import pypdf
        reader = pypdf.PdfReader(str(pdf_path))
        return "\n".join(p.extract_text() or "" for p in reader.pages)
    except ImportError:
        return ""


def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 150) -> list[str]:
    import re
    text = re.sub(r'\n{3,}', '\n\n', text.strip())
    chunks, pos = [], 0
    while pos < len(text):
        end = pos + chunk_size
        if end < len(text):
            para = text.rfind("\n\n", pos, end)
            if para > pos + chunk_size // 2:
                end = para
        chunk = text[pos:end].strip()
        if chunk:
            chunks.append(chunk)
        pos = end - overlap if end < len(text) else len(text)
    return chunks


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="NASA NTRS ingest for Mindfield-Space")
    parser.add_argument("--query",      type=str)
    parser.add_argument("--id",         type=str)
    parser.add_argument("--k",          type=int, default=10)
    parser.add_argument("--dry-run",    action="store_true")
    parser.add_argument("--ingest",     action="store_true")
    parser.add_argument("--full-text",  action="store_true",
                        help="Download and extract full PDF text (slower, more thorough)")
    parser.add_argument("--lean-url",   default="http://127.0.0.1:8018")
    parser.add_argument("--domain-url", type=str,
                        help="Ingest into a domain stack (e.g. http://127.0.0.1:18003)")
    args = parser.parse_args()

    if not args.dry_run and not args.ingest:
        print("Specify --dry-run or --ingest")
        sys.exit(1)
    if not args.query and not args.id:
        print("Specify --query TEXT or --id NTRS_ID")
        sys.exit(1)

    lean_url = args.domain_url or args.lean_url

    # ── Fetch records ─────────────────────────────────────────────────────────
    records = []
    if args.id:
        rec = ntrs_fetch(args.id)
        if rec:
            records = [rec]
    else:
        print(f"\nSearching NTRS: '{args.query}' (k={args.k})...\n")
        records = ntrs_search(args.query, rows=args.k)

    if not records:
        print("  No results found.")
        sys.exit(0)

    print(f"  Found {len(records)} records\n")

    # ── Preview / plan ────────────────────────────────────────────────────────
    plan = []
    for rec in records:
        ntrs_id = rec.get("id", "?")
        title   = rec.get("title", "?")[:80]
        year    = rec.get("publicationDate", "")[:4]
        source, abstract_text, tags = record_to_metadata(rec)
        n_downloads = len(rec.get("downloads", []))
        print(f"  [{ntrs_id}] ({year}) {title}")
        print(f"    source='{source}'  downloads={n_downloads}  abstract={'yes' if abstract_text else 'no'}")
        plan.append((rec, source, abstract_text, tags))

    print(f"\nTotal: {len(plan)} reports")
    if args.dry_run:
        print("\nDry run complete. Run with --ingest to write.")
        return

    # ── Ingest ────────────────────────────────────────────────────────────────
    if not lean_health(lean_url):
        sys.exit(1)

    written = failed = 0
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        for rec, source, abstract_text, tags in plan:
            ntrs_id = rec.get("id", "?")
            chunks  = []

            if args.full_text and rec.get("downloads"):
                pdf_path = ntrs_download_pdf(ntrs_id, rec, tmp)
                if pdf_path:
                    full_text = extract_pdf_text(pdf_path)
                    if full_text.strip():
                        chunks = chunk_text(full_text)
                        print(f"  {source}: {len(chunks)} chunks from full text")
                    else:
                        print(f"  {source}: PDF text extraction empty — using abstract")

            if not chunks and abstract_text.strip():
                chunks = [abstract_text]
                print(f"  {source}: 1 chunk (abstract)")

            if not chunks:
                print(f"  {source}: SKIP — no content available")
                continue

            for chunk in chunks:
                if write_chunk(lean_url, chunk, source, tags):
                    written += 1
                else:
                    failed += 1
                time.sleep(0.02)

    print(f"\nDone. Written: {written}  Failed: {failed}")
    if failed == 0:
        print(f"Verify: curl {lean_url}/stats")


if __name__ == "__main__":
    main()
