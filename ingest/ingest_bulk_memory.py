"""
ingest_bulk_memory.py — Bulk ingest files into your memory field
================================================================
Reads all files in ingest_queue/, chunks them, embeds via lean_api /write.

Usage:
  python ingest/ingest_bulk_memory.py --dry-run    # preview only — no writes
  python ingest/ingest_bulk_memory.py --ingest     # write to LanceDB

Options:
  --lean-url URL    lean_api base URL  (default: http://127.0.0.1:8018)
  --chunk-size N    characters per chunk (default: 800)
  --overlap N       character overlap between chunks (default: 100)
  --source NAME     source label (default: filename)

Supported formats: .txt, .md, .pdf

Place your documents in:  ingest/ingest_queue/
Done documents are moved to: ingest/ingest_done/

SAFETY: Always --dry-run first. Review chunk counts. Then --ingest.
"""

import argparse
import json
import os
import re
import shutil
import sys
import time
import urllib.request
from pathlib import Path


QUEUE_DIR = Path(__file__).parent / "ingest_queue"
DONE_DIR  = Path(__file__).parent / "ingest_done"
DONE_DIR.mkdir(exist_ok=True)


# ── Text extraction ───────────────────────────────────────────────────────────

def extract_text_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def extract_text_pdf(path: Path) -> str:
    try:
        import pypdf
        reader = pypdf.PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except ImportError:
        print(f"  [!] pypdf not installed — skipping {path.name}. Run: pip install pypdf")
        return ""


def extract_text(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in (".txt", ".md", ".rst"):
        return extract_text_txt(path)
    elif ext == ".pdf":
        return extract_text_pdf(path)
    else:
        return ""


# ── Chunker ───────────────────────────────────────────────────────────────────

def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    """Split text into overlapping chunks. Tries to break on paragraph boundaries."""
    text = re.sub(r"\n{3,}", "\n\n", text.strip())
    chunks = []
    pos = 0
    while pos < len(text):
        end = pos + chunk_size
        if end < len(text):
            # Try to break on paragraph boundary
            para = text.rfind("\n\n", pos, end)
            if para > pos + chunk_size // 2:
                end = para
            else:
                # Fall back to sentence boundary
                sent = max(text.rfind(". ", pos, end), text.rfind(".\n", pos, end))
                if sent > pos + chunk_size // 2:
                    end = sent + 1
        chunk = text[pos:end].strip()
        if chunk:
            chunks.append(chunk)
        pos = end - overlap if end < len(text) else len(text)
    return chunks


# ── Lean API writer ───────────────────────────────────────────────────────────

def write_chunk(lean_url: str, content: str, source: str) -> bool:
    payload = json.dumps({"content": content, "source": source}).encode()
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
    parser = argparse.ArgumentParser(description="Bulk ingest files into memory field")
    parser.add_argument("--dry-run",    action="store_true", help="Preview only — no writes")
    parser.add_argument("--ingest",     action="store_true", help="Write to LanceDB")
    parser.add_argument("--lean-url",   default="http://127.0.0.1:8018", help="lean_api URL")
    parser.add_argument("--chunk-size", type=int, default=800)
    parser.add_argument("--overlap",    type=int, default=100)
    parser.add_argument("--source",     default="",  help="Override source label")
    args = parser.parse_args()

    if not args.dry_run and not args.ingest:
        print("Specify --dry-run or --ingest")
        sys.exit(1)

    SKIP_NAMES = {"readme.md", "readme.txt", "readme.rst", ".gitkeep"}
    files = [f for f in QUEUE_DIR.iterdir()
             if f.is_file()
             and f.suffix.lower() in (".txt", ".md", ".rst", ".pdf")
             and f.name.lower() not in SKIP_NAMES]

    if not files:
        print(f"No supported files found in {QUEUE_DIR}")
        print("Supported: .txt .md .rst .pdf")
        sys.exit(0)

    print(f"\n{'DRY RUN — no writes' if args.dry_run else 'INGEST MODE'}")
    print(f"Lean API: {args.lean_url}")
    print(f"Chunk size: {args.chunk_size} chars  Overlap: {args.overlap} chars")
    print(f"Files found: {len(files)}\n")

    total_chunks = 0
    plan = []

    for f in sorted(files):
        text = extract_text(f)
        if not text.strip():
            print(f"  SKIP  {f.name}  (no text extracted)")
            continue
        chunks = chunk_text(text, args.chunk_size, args.overlap)
        source = args.source or f.stem
        print(f"  {f.name:<45}  {len(chunks):>4} chunks  source='{source}'")
        plan.append((f, chunks, source))
        total_chunks += len(chunks)

    print(f"\nTotal: {total_chunks} chunks from {len(plan)} files")

    if args.dry_run:
        print("\nDry run complete. Run with --ingest to write.")
        return

    # Verify lean_api is reachable
    try:
        with urllib.request.urlopen(f"{args.lean_url}/health", timeout=5) as r:
            h = json.loads(r.read())
            print(f"\nlean_api health: {h}")
    except Exception as e:
        print(f"\n[!] Cannot reach lean_api at {args.lean_url}: {e}")
        print("    Start lean_api first: python lean/lean_api.py")
        sys.exit(1)

    print(f"\nWriting {total_chunks} chunks...\n")
    written = 0
    failed  = 0

    for f, chunks, source in plan:
        print(f"  {f.name}  ({len(chunks)} chunks)...")
        for i, chunk in enumerate(chunks):
            ok = write_chunk(args.lean_url, chunk, source)
            if ok:
                written += 1
            else:
                failed += 1
            if (i + 1) % 20 == 0:
                print(f"    {i+1}/{len(chunks)}...")
            time.sleep(0.02)  # gentle rate limit

        # Move to done
        dest = DONE_DIR / f.name
        if dest.exists():
            dest = DONE_DIR / f"{f.stem}_{int(time.time())}{f.suffix}"
        shutil.move(str(f), str(dest))
        print(f"    moved -> ingest_done/{dest.name}")

    print(f"\nDone. Written: {written}  Failed: {failed}")
    print("Verify with: curl http://127.0.0.1:8018/stats")


if __name__ == "__main__":
    main()
