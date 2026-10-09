"""
ingest_arxiv_space.py — arXiv space science ingest
===================================================
Fetches papers from arXiv space categories and ingests into memory field.
No API key required. arXiv is fully open access.

Space-relevant arXiv categories:
  astro-ph       Astrophysics (all sub-categories)
  astro-ph.EP    Earth and Planetary Astrophysics
  astro-ph.IM    Instrumentation and Methods
  astro-ph.SR    Solar and Stellar Astrophysics
  gr-qc          General Relativity and Quantum Cosmology
  physics.space-ph  Space Physics
  eess.SP        Signal Processing (relevant for telemetry/comms)

Usage:
  # Fetch recent astro-ph.EP papers
  python mission/ingest_arxiv_space.py --category astro-ph.EP --k 20 --dry-run

  # Fetch by search query
  python mission/ingest_arxiv_space.py --query "Mars atmosphere dust storm" --k 10 --ingest

  # Fetch a specific arXiv paper by ID
  python mission/ingest_arxiv_space.py --id 2305.12345 --ingest

  # Ingest into a domain stack
  python mission/ingest_arxiv_space.py --query "orbital debris collision probability" \\
    --k 20 --ingest --domain-url http://127.0.0.1:18005
"""

import argparse
import json
import re
import sys
import time
import urllib.request
import urllib.parse
from pathlib import Path
import tempfile


ARXIV_API = "https://export.arxiv.org/api/query"

SPACE_CATEGORIES = {
    "astro-ph":     "Astrophysics",
    "astro-ph.EP":  "Earth and Planetary",
    "astro-ph.IM":  "Instrumentation and Methods",
    "astro-ph.HE":  "High Energy Astrophysics",
    "astro-ph.SR":  "Solar and Stellar",
    "astro-ph.CO":  "Cosmology",
    "astro-ph.GA":  "Galaxies",
    "gr-qc":        "General Relativity",
    "physics.space-ph": "Space Physics",
    "eess.SP":      "Signal Processing",
}


# ── arXiv API ─────────────────────────────────────────────────────────────────

def arxiv_query(query: str = "", category: str = "", k: int = 10,
                start: int = 0) -> list[dict]:
    """Query arXiv API. Returns list of paper dicts."""
    search_parts = []
    if query:
        search_parts.append(f"all:{urllib.parse.quote(query)}")
    if category:
        search_parts.append(f"cat:{category}")

    search_query = "+AND+".join(search_parts) if search_parts else "cat:astro-ph"

    params = urllib.parse.urlencode({
        "search_query": search_query,
        "max_results":  k,
        "start":        start,
        "sortBy":       "relevance",
        "sortOrder":    "descending",
    })
    url = f"{ARXIV_API}?{params}"

    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            xml = r.read().decode("utf-8")
        return _parse_arxiv_atom(xml)
    except Exception as e:
        print(f"  [!] arXiv query failed: {e}")
        return []


def arxiv_by_id(arxiv_id: str) -> dict | None:
    """Fetch a single arXiv paper by ID."""
    clean = re.sub(r'v\d+$', '', arxiv_id.strip())
    url   = f"{ARXIV_API}?id_list={clean}"
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            xml = r.read().decode("utf-8")
        papers = _parse_arxiv_atom(xml)
        return papers[0] if papers else None
    except Exception as e:
        print(f"  [!] arXiv fetch failed: {e}")
        return None


def _parse_arxiv_atom(xml: str) -> list[dict]:
    """Parse arXiv Atom XML into list of paper dicts."""
    papers = []
    for entry in re.finditer(r'<entry>(.*?)</entry>', xml, re.DOTALL):
        e = entry.group(1)

        def _tag(name: str) -> str:
            m = re.search(rf'<{name}[^>]*>(.+?)</{name}>', e, re.DOTALL)
            return re.sub(r'\s+', ' ', m.group(1)).strip() if m else ""

        arxiv_id = ""
        id_m = re.search(r'<id>.*?/abs/([^<\s]+)</id>', e)
        if id_m:
            arxiv_id = re.sub(r'v\d+$', '', id_m.group(1))

        authors = re.findall(r'<name>(.+?)</name>', e)
        cats    = re.findall(r'<category[^>]+term="([^"]+)"', e)

        papers.append({
            "id":       arxiv_id,
            "title":    _tag("title"),
            "abstract": _tag("summary"),
            "authors":  authors,
            "year":     _tag("published")[:4],
            "categories": cats,
            "pdf_url":  f"https://arxiv.org/pdf/{arxiv_id}" if arxiv_id else "",
        })
    return papers


# ── Content builder ───────────────────────────────────────────────────────────

def paper_to_content_tags(paper: dict) -> tuple[str, str, list[str]]:
    """Return (source, content, tags) for a paper."""
    arxiv_id    = paper.get("id", "")
    title       = paper.get("title", "")
    abstract    = paper.get("abstract", "")
    authors     = paper.get("authors", [])
    year        = paper.get("year", "")
    categories  = paper.get("categories", [])

    first_author = authors[0].split()[-1] if authors else ""
    source = f"arxiv_{arxiv_id}" if arxiv_id else "arxiv_unknown"
    if first_author and year:
        source = f"{first_author.lower()}_{year}_arxiv{arxiv_id.replace('/', '_')}"

    content = ""
    if title:
        content += f"{title}\n\n"
    if abstract:
        content += abstract

    tags = ["type:arxiv"]
    if first_author:
        tags.append(f"author:{first_author}")
    if year:
        tags.append(f"year:{year}")
    for cat in categories[:3]:
        tags.append(f"cat:{cat}")

    return source, content, tags


def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 150) -> list[str]:
    import re as _re
    text = _re.sub(r'\n{3,}', '\n\n', text.strip())
    chunks, pos = [], 0
    while pos < len(text):
        end = pos + chunk_size
        if end < len(text):
            para = text.rfind("\n\n", pos, end)
            if para > pos + chunk_size // 2:
                end = para
        c = text[pos:end].strip()
        if c:
            chunks.append(c)
        pos = end - overlap if end < len(text) else len(text)
    return chunks


def extract_pdf(pdf_path: Path) -> str:
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


# ── lean_api helpers ──────────────────────────────────────────────────────────

def lean_health(lean_url: str) -> bool:
    try:
        with urllib.request.urlopen(f"{lean_url}/health", timeout=5) as r:
            print(f"  lean_api: {json.loads(r.read())}")
            return True
    except Exception as e:
        print(f"  [!] Cannot reach {lean_url}: {e}")
        return False


def write_chunk(lean_url: str, content: str, source: str, tags: list) -> bool:
    if not content.strip():
        return False
    payload = json.dumps({"content": content, "source": source, "tags": tags}).encode()
    req = urllib.request.Request(
        f"{lean_url}/write", data=payload,
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
    parser = argparse.ArgumentParser(description="arXiv space ingest for Mindfield-Space")
    parser.add_argument("--query",       type=str)
    parser.add_argument("--category",    type=str, choices=list(SPACE_CATEGORIES.keys()))
    parser.add_argument("--id",          type=str)
    parser.add_argument("--k",           type=int, default=10)
    parser.add_argument("--dry-run",     action="store_true")
    parser.add_argument("--ingest",      action="store_true")
    parser.add_argument("--full-text",   action="store_true",
                        help="Download full PDFs (slower — abstract-only is usually sufficient)")
    parser.add_argument("--lean-url",    default="http://127.0.0.1:8018")
    parser.add_argument("--domain-url",  type=str)
    parser.add_argument("--list-categories", action="store_true")
    args = parser.parse_args()

    if args.list_categories:
        print("\nSpace-relevant arXiv categories:\n")
        for cat, desc in SPACE_CATEGORIES.items():
            print(f"  {cat:<22}  {desc}")
        return

    if not args.dry_run and not args.ingest:
        print("Specify --dry-run or --ingest")
        sys.exit(1)
    if not any([args.query, args.category, args.id]):
        print("Specify --query, --category, or --id")
        sys.exit(1)

    lean_url = args.domain_url or args.lean_url

    # ── Fetch ─────────────────────────────────────────────────────────────────
    papers = []
    if args.id:
        p = arxiv_by_id(args.id)
        if p:
            papers = [p]
    else:
        cat_label = SPACE_CATEGORIES.get(args.category, args.category or "")
        print(f"\nQuerying arXiv: query='{args.query or ''}' category='{args.category or ''}' k={args.k}\n")
        papers = arxiv_query(args.query or "", args.category or "", k=args.k)

    if not papers:
        print("  No results.")
        sys.exit(0)

    print(f"  Found {len(papers)} papers\n")

    plan = []
    for p in papers:
        source, content, tags = paper_to_content_tags(p)
        print(f"  [{p.get('id','?')}] ({p.get('year','?')}) {p.get('title','?')[:70]}")
        plan.append((p, source, content, tags))

    print(f"\nTotal: {len(plan)} papers")
    if args.dry_run:
        print("\nDry run complete. Run with --ingest to write.")
        return

    if not lean_health(lean_url):
        sys.exit(1)

    written = failed = 0
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        for paper, source, content, tags in plan:
            chunks = []

            if args.full_text and paper.get("pdf_url"):
                pdf_dest = tmp / f"{source}.pdf"
                try:
                    urllib.request.urlretrieve(paper["pdf_url"], str(pdf_dest))
                    full = extract_pdf(pdf_dest)
                    if full.strip():
                        chunks = chunk_text(full)
                        print(f"  {source}: {len(chunks)} chunks (full text)")
                except Exception as e:
                    print(f"  {source}: PDF download failed ({e}) — using abstract")

            if not chunks and content.strip():
                chunks = [content]
                print(f"  {source}: 1 chunk (abstract)")

            for chunk in chunks:
                if write_chunk(lean_url, chunk, source, tags):
                    written += 1
                else:
                    failed += 1
                time.sleep(0.02)

    print(f"\nDone. Written: {written}  Failed: {failed}")


if __name__ == "__main__":
    main()
