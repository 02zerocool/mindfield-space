"""
health_check.py — Verify your Mindfield stack is running
=========================================================
Checks all services and reports what's up/down.

Usage:
  python scripts/health_check.py
"""

import json
import sys
import urllib.request
from pathlib import Path

# Core services — required for basic memory search/write
SERVICES_CORE = [
    ("nomic-embed",  "http://127.0.0.1:8082/health",   "Embedding server"),
    ("lean-api",     "http://127.0.0.1:8018/health",   "Lean memory API"),
    ("lean-stats",   "http://127.0.0.1:8018/stats",    "Memory stats"),
]

# Optional services — not included in v0.1, available as extensions
SERVICES_OPTIONAL = [
    ("voyager",  "http://127.0.0.1:8008/api/health",  "Web frontend (not in v0.1)"),
    ("bifrost",  "http://127.0.0.1:8200/health",      "Bifrost bridge (optional)"),
    ("gguf",     "http://127.0.0.1:8009/health",      "GGUF inference (bring your own model)"),
]

SERVICES = SERVICES_CORE  # health_check only fails on core services

def check(url: str, timeout: int = 3) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            body = json.loads(r.read())
            return True, str(body)
    except urllib.error.URLError:
        return False, "unreachable"
    except Exception as e:
        return False, str(e)


def main() -> int:
    print("\nMindfield health check\n")
    print(f"{'Service':<20} {'Status':<10} {'Detail'}")
    print("─" * 70)

    all_ok = True
    for name, url, desc in SERVICES:
        ok, detail = check(url)
        status = "UP   ✓" if ok else "DOWN ✗"
        color  = "\033[32m" if ok else "\033[33m"  # green / yellow
        reset  = "\033[0m"
        print(f"{color}{name:<20} {status:<10}{reset}  {detail[:60]}")
        if not ok and "optional" not in desc.lower():
            all_ok = False

    # LanceDB dir check
    lancedb = Path(__file__).parent.parent / "lancedb"
    if lancedb.exists():
        tables = list(lancedb.glob("*.lance"))
        print(f"\n{'lancedb':<20} {'EXISTS':<10}  {len(tables)} table(s) at {lancedb}")
    else:
        print(f"\n{'lancedb':<20} {'MISSING':<10}  run: python setup.py")
        all_ok = False

    # Optional services (informational only — not required)
    print(f"\n{'Optional services (not in v0.1)':}")
    print("─" * 70)
    for name, url, desc in SERVICES_OPTIONAL:
        ok_svc, detail = check(url)
        status = "UP   ✓" if ok_svc else "n/a   "
        color  = "\033[32m" if ok_svc else "\033[90m"
        reset  = "\033[0m"
        print(f"{color}{name:<20} {status:<10}{reset}  {desc}")

    print()
    if all_ok:
        print("  Core stack running. Try:")
        print("    curl -X POST http://127.0.0.1:8018/search \\")
        print("         -H 'Content-Type: application/json' \\")
        print("         -d '{\"query\": \"your question\", \"k\": 5}'\n")
    else:
        print("  Core services not running. Start with:")
        print("    docker-compose up nomic-embed lean")
        print("    OR")
        print("    llama-server --model models/nomic-embed-text-v1.5.Q8_0.gguf --port 8082 --embedding &")
        print("    python lean/lean_api.py\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
