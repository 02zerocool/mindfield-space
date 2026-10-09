"""
ingest_ads.py — NASA ADS (Astrophysics Data System) ingest
===========================================================
NASA ADS is the premier database for astrophysics and space science literature.
Covers NASA technical reports, journal papers, conference proceedings, and more.

Requires a FREE API key — register at: https://ui.adsabs.harvard.edu/user/settings/token

Set your key:
  export ADS_API_KEY=your_key_here
  # or add to .env:  ADS_API_KEY=your_key_here

Usage:
  # Search ADS
  python mission/ingest_ads.py --query "Mars dust storm atmospheric opacity" --k 20 --dry-run
  python mission/ingest_ads.py --query "ECLSS water recovery system" --k 10 --ingest

  # Filter by year range
  python mission/ingest_ads.py --query "orbital debris" --year-min 2015 --k 30 --ingest

  # Search NASA technical reports specifically
  python mission/ingest_ads.py --query "entry descent landing" --collection NASA --k 20 --ingest

  # Ingest into a domain stack
  python mission/ingest_ads.py --query "propulsion electric thruster" \\
    --k 20 --ingest --domain-url http://127.0.0.1:18004
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.parse
from pathlib import Path
from dotenv import load_dotenv  # noqa: F401 — optional, falls back to env var

# Try loading .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ADS_API = "https://api.adsabs.harvard.edu/v1"

COLLECTIONS = {
    "NASA":     'bibstem:"NASA"',
    "journal":  'property:refereed',
    "preprint": 'property:not_refereed',
    "all":      None,
}


# ── ADS API ───────────────────────────────────────────────────────────────────

def ads_search(query: str, api_key: str, k: int = 10,
               year_min: int = None, year_max: int = None,
               collection: str = None) -> list[dict]:
    """
    Search NASA ADS. Returns list of paper records.
    Fields: title, author, year, abstract, identifier, bibcode, doi
    """
    fq_parts = []
    if year_min or year_max:
        lo = year_min or 1900
        hi = year_max or 2100
        fq_parts.append(f"year:[{lo} TO {hi}]")
    if collection and collection != "all":
        extra = COLLECTIONS.get(collection)
        if extra:
            fq_parts.append(extra)

    params = {
        "q":  query,
        "fl": "title,author,year,abstract,identifier,bibcode,doi,keyword,pub",
        "rows": k,
        "sort": "score desc",
    }
    if fq_parts:
        params["fq"] = " AND ".join(fq_parts)

    url = f"{ADS_API}/search/query?" + urllib.parse.urlencode(params)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type":  "application/json",
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
        return data.get("response", {}).get("docs", [])
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print("  [!] ADS API key invalid or missing. Get a free key at: https://ui.adsabs.harvard.edu/user/settings/token")
        else:
            print(f"  [!] ADS search failed: HTTP {e.code}")
        return []
    except Exception as e:
        print(f"  [!] ADS search failed: {e}")
        return []


# ── Content builder ───────────────────────────────────────────────────────────

def record_to_content_tags(record: dict) -> tuple[str, str, list[str]]:
    bibcode = record.get("bibcode", "")
    title   = " ".join(record.get("title", [""]))
    authors = record.get("author", [])
    year    = str(record.get("year", ""))
    abstract= record.get("abstract", "")
    doi_list= record.get("doi", [])
    pub     = record.get("pub", "")
    keywords= record.get("keyword", [])

    first_author = authors[0].split(",")[0].strip() if authors else ""
    source = f"ads_{bibcode.replace('/', '_').replace('.', '_')}" if bibcode else "ads_unknown"

    content = ""
    if title:
        content += f"{title}\n\n"
    if abstract:
        content += abstract

    tags = ["type:ads"]
    if first_author:
        tags.append(f"author:{first_author}")
    if year:
        tags.append(f"year:{year}")
    if doi_list:
        tags.append(f"doi:{doi_list[0]}")
    if pub:
        tags.append(f"venue:{pub[:40]}")
    for kw in keywords[:3]:
        tags.append(f"kw:{kw[:30]}")

    return source, content, tags


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
    parser = argparse.ArgumentParser(description="NASA ADS ingest for Mindfield-Space")
    parser.add_argument("--query",       required=True)
    parser.add_argument("--k",           type=int, default=10)
    parser.add_argument("--year-min",    type=int)
    parser.add_argument("--year-max",    type=int)
    parser.add_argument("--collection",  choices=list(COLLECTIONS.keys()), default="all")
    parser.add_argument("--dry-run",     action="store_true")
    parser.add_argument("--ingest",      action="store_true")
    parser.add_argument("--lean-url",    default="http://127.0.0.1:8018")
    parser.add_argument("--domain-url",  type=str)
    args = parser.parse_args()

    if not args.dry_run and not args.ingest:
        print("Specify --dry-run or --ingest")
        sys.exit(1)

    api_key = os.environ.get("ADS_API_KEY", "")
    if not api_key:
        print("\n[!] ADS_API_KEY not set.")
        print("    Get a free key at: https://ui.adsabs.harvard.edu/user/settings/token")
        print("    Then: export ADS_API_KEY=your_key  (or add to .env)")
        sys.exit(1)

    lean_url = args.domain_url or args.lean_url

    print(f"\nSearching ADS: '{args.query}' (k={args.k})\n")
    records = ads_search(
        args.query, api_key,
        k=args.k,
        year_min=args.year_min,
        year_max=args.year_max,
        collection=args.collection,
    )

    if not records:
        print("  No results.")
        sys.exit(0)

    plan = []
    for rec in records:
        source, content, tags = record_to_content_tags(rec)
        title = " ".join(rec.get("title", ["?"]))[:70]
        year  = rec.get("year", "?")
        print(f"  ({year}) {title}")
        plan.append((source, content, tags))

    print(f"\nTotal: {len(plan)} records")
    if args.dry_run:
        print("\nDry run complete. Run with --ingest to write.")
        return

    if not lean_health(lean_url):
        sys.exit(1)

    written = failed = 0
    for source, content, tags in plan:
        if write_chunk(lean_url, content, source, tags):
            written += 1
        else:
            failed += 1
        time.sleep(0.05)

    print(f"\nDone. Written: {written}  Failed: {failed}")


if __name__ == "__main__":
    main()
