"""
fits_metadata.py — FITS header extraction for memory field
===========================================================
Astronomical FITS files carry rich metadata in their headers:
instrument parameters, observation targets, coordinates, exposure times,
filter configurations, processing provenance.

This tool extracts FITS headers and writes them as searchable memory records.
The data arrays are NOT stored — only the human-readable metadata.

Requires: pip install astropy

Usage:
  python mission/fits_metadata.py --dir observations/ --dry-run
  python mission/fits_metadata.py --dir observations/ --ingest
  python mission/fits_metadata.py --file my_observation.fits --ingest
  python mission/fits_metadata.py --dir mast_downloads/ --ingest --domain-url http://127.0.0.1:18008
"""

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path


# ── FITS header extraction ────────────────────────────────────────────────────

# Keys we always want if present — covers HST, JWST, Chandra, XMM, TESS, Kepler
# Spitzer, VLA, ALMA, and most ground-based instruments
HEADER_KEYS = [
    # Observation identity
    "TELESCOP", "INSTRUME", "DETECTOR", "FILTER", "FILTNAM1", "FILTNAM2",
    # Target
    "TARGNAME", "OBJECT", "PROPID", "PROPOSID", "PI_NAME",
    # Coordinates
    "RA_TARG", "DEC_TARG", "EQUINOX", "RADESYS",
    # Time
    "DATE-OBS", "TIME-OBS", "EXPSTART", "EXPEND", "EXPTIME", "ONTIME",
    # Instrument config
    "APERTURE", "GRATING", "DISPAXIS", "NAXIS1", "NAXIS2",
    # Processing
    "CAL_VER", "PROCTIME", "PIPELINE", "ORIGIN",
    # Mission-specific common
    "VISIT_ID", "OBSET_ID", "ASSNMNT", "OBSMODE", "OBSTYPE",
    # JWST
    "PROGRAM", "OBSERVTN", "VISIT", "EFFEXPTM", "BKGDTARG",
    # Chandra
    "OBS_ID", "GRATING", "DETNAM",
    # XMM
    "OBS_ID", "INSTRUME", "REVOLUT",
]


def extract_fits_metadata(path: Path) -> dict:
    """Extract header metadata from a FITS file. Returns dict of key: value."""
    try:
        from astropy.io import fits
    except ImportError:
        print("  [!] astropy not installed. Run: pip install astropy")
        return {}

    meta = {}
    try:
        with fits.open(str(path), memmap=True) as hdul:
            # Collect from all headers — primary + first extension usually has everything
            for hdu in hdul[:3]:
                hdr = hdu.header
                for key in HEADER_KEYS:
                    if key in hdr and key not in meta:
                        val = hdr[key]
                        if val not in (None, "", "N/A", "INDEF"):
                            meta[key] = str(val).strip()
                # Also grab any comment cards that describe the observation
                for key in ("COMMENT", "HISTORY"):
                    if key in hdr:
                        comments = [str(c).strip() for c in hdr[key] if str(c).strip()]
                        if comments:
                            meta[key] = " | ".join(comments[:5])
    except Exception as e:
        print(f"  [!] FITS read failed {path.name}: {e}")

    return meta


def metadata_to_content(path: Path, meta: dict) -> str:
    """Format FITS metadata as a readable text chunk."""
    lines = [f"FITS observation: {path.name}\n"]

    # Instrument and target first
    for key in ["TELESCOP", "INSTRUME", "TARGNAME", "OBJECT", "FILTER", "APERTURE"]:
        if key in meta:
            lines.append(f"{key}: {meta[key]}")

    # Coordinates
    for key in ["RA_TARG", "DEC_TARG"]:
        if key in meta:
            lines.append(f"{key}: {meta[key]}")

    # Timing
    for key in ["DATE-OBS", "EXPTIME", "ONTIME", "EFFEXPTM"]:
        if key in meta:
            lines.append(f"{key}: {meta[key]}")

    # Program / PI
    for key in ["PI_NAME", "PROPID", "PROPOSID", "PROGRAM", "VISIT_ID"]:
        if key in meta:
            lines.append(f"{key}: {meta[key]}")

    # Processing provenance
    for key in ["PIPELINE", "CAL_VER", "ORIGIN"]:
        if key in meta:
            lines.append(f"{key}: {meta[key]}")

    # Remaining keys not already shown
    shown = {"TELESCOP", "INSTRUME", "TARGNAME", "OBJECT", "FILTER", "APERTURE",
             "RA_TARG", "DEC_TARG", "DATE-OBS", "EXPTIME", "ONTIME", "EFFEXPTM",
             "PI_NAME", "PROPID", "PROPOSID", "PROGRAM", "VISIT_ID",
             "PIPELINE", "CAL_VER", "ORIGIN", "COMMENT", "HISTORY"}
    for key, val in meta.items():
        if key not in shown:
            lines.append(f"{key}: {val}")

    if "COMMENT" in meta:
        lines.append(f"\nComment: {meta['COMMENT'][:200]}")

    return "\n".join(lines)


def metadata_to_tags(meta: dict) -> list[str]:
    tags = ["type:fits"]
    for key, tag in [
        ("TELESCOP", "telescope"), ("INSTRUME", "instrument"),
        ("FILTER", "filter"), ("DATE-OBS", "date"), ("PI_NAME", "pi"),
    ]:
        if key in meta:
            tags.append(f"{tag}:{meta[key][:30]}")
    return tags


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
    parser = argparse.ArgumentParser(description="FITS metadata ingest for Mindfield-Space")
    parser.add_argument("--dir",        type=Path, help="Directory of .fits / .fit files")
    parser.add_argument("--file",       type=Path, help="Single FITS file")
    parser.add_argument("--dry-run",    action="store_true")
    parser.add_argument("--ingest",     action="store_true")
    parser.add_argument("--lean-url",   default="http://127.0.0.1:8018")
    parser.add_argument("--domain-url", type=str)
    args = parser.parse_args()

    if not args.dry_run and not args.ingest:
        print("Specify --dry-run or --ingest")
        sys.exit(1)

    files = []
    if args.file:
        files = [args.file]
    elif args.dir:
        files = [f for f in args.dir.rglob("*")
                 if f.suffix.lower() in (".fits", ".fit", ".fts")]
    else:
        print("Specify --file or --dir")
        sys.exit(1)

    if not files:
        print("No FITS files found.")
        sys.exit(0)

    print(f"\n{'DRY RUN' if args.dry_run else 'INGEST MODE'}")
    print(f"FITS files: {len(files)}\n")

    lean_url = args.domain_url or args.lean_url
    plan     = []

    for f in sorted(files):
        meta    = extract_fits_metadata(f)
        content = metadata_to_content(f, meta)
        tags    = metadata_to_tags(meta)
        source  = f"fits_{f.stem}"
        target  = meta.get("TARGNAME") or meta.get("OBJECT") or "?"
        tel     = meta.get("TELESCOP", "?")
        date    = meta.get("DATE-OBS", "?")
        print(f"  {f.name:<45}  target={target}  tel={tel}  date={date}")
        if content.strip():
            plan.append((source, content, tags))
        else:
            print(f"    SKIP — no metadata extracted")

    print(f"\nTotal: {len(plan)} records to write")
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
        time.sleep(0.02)

    print(f"\nDone. Written: {written}  Failed: {failed}")


if __name__ == "__main__":
    main()
