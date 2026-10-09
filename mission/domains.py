"""
domains.py — Launch and manage mission domain stacks
=====================================================
Starts lean_api instances for each pre-configured space domain.
Each domain is a separate LanceDB on its own port.

Usage:
  # Start all 10 domain stacks
  python mission/domains.py --start-all

  # Start specific domains
  python mission/domains.py --start telemetry fmea astrodynamics

  # Check domain status
  python mission/domains.py --status

  # List all domains
  python mission/domains.py --list
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

# Add project root to path so we can import domains package
sys.path.insert(0, str(Path(__file__).parent.parent))
from domains.space_domains import DOMAINS

ROOT    = Path(__file__).parent.parent
LEAN_PY = ROOT / "lean" / "lean_api.py"
LOGS    = ROOT / "logs"
LOGS.mkdir(exist_ok=True)

_procs: dict[str, subprocess.Popen] = {}


def start_domain(name: str) -> subprocess.Popen | None:
    if name not in DOMAINS:
        print(f"  Unknown domain: {name}")
        return None

    d = DOMAINS[name]
    lancedb_path = str(ROOT / d["lancedb"].lstrip("./"))
    Path(lancedb_path).mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["LANCE_DB_PATH"] = lancedb_path
    env["LEAN_PORT"]     = str(d["port"])
    env["EMBED_URL"]     = env.get("EMBED_URL", "http://127.0.0.1:8082")

    log_out = open(LOGS / f"domain_{name}_out.log", "a")
    log_err = open(LOGS / f"domain_{name}_err.log", "a")

    proc = subprocess.Popen(
        [sys.executable, str(LEAN_PY)],
        env=env,
        stdout=log_out,
        stderr=log_err,
    )
    print(f"  STARTED  {name:<15}  :{d['port']}  pid={proc.pid}")
    return proc


def check_domain(name: str) -> bool:
    """Return True if domain lean_api is responding."""
    d = DOMAINS.get(name, {})
    port = d.get("port")
    if not port:
        return False
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as r:
            return json.loads(r.read()).get("status") == "ok"
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="Mission domain stack manager")
    parser.add_argument("--start-all",  action="store_true")
    parser.add_argument("--start",      nargs="+", choices=list(DOMAINS.keys()))
    parser.add_argument("--status",     action="store_true")
    parser.add_argument("--list",       action="store_true")
    args = parser.parse_args()

    if args.list:
        print("\nPre-configured mission domains:\n")
        print(f"  {'Name':<15} {'Port':<8} {'Description'}")
        print("  " + "─" * 70)
        for name, d in DOMAINS.items():
            print(f"  {name:<15} :{d['port']:<7} {d['description']}")
        print()
        return

    if args.status:
        print("\nDomain status:\n")
        for name, d in DOMAINS.items():
            up = check_domain(name)
            status = "\033[32mUP  \033[0m" if up else "\033[90mn/a \033[0m"
            print(f"  {status}  {name:<15}  :{d['port']}  {d['description'][:50]}")
        print()
        return

    targets = list(DOMAINS.keys()) if args.start_all else (args.start or [])
    if not targets:
        parser.print_help()
        return

    print(f"\nStarting {len(targets)} domain stack(s)...\n")
    for name in targets:
        proc = start_domain(name)
        if proc:
            _procs[name] = proc

    if not _procs:
        return

    # Wait for them to come up
    print("\nWaiting for domains to be ready...")
    time.sleep(3)
    all_up = True
    for name in targets:
        if check_domain(name):
            d = DOMAINS[name]
            print(f"  UP    {name:<15}  :{d['port']}")
        else:
            print(f"  WAIT  {name:<15}  (still starting — check logs/domain_{name}_err.log)")
            all_up = False

    print()
    if all_up:
        print("All domains running.")
    else:
        print("Some domains still starting. Re-run --status in a few seconds.")

    print("\nDomains run in background — processes will continue after this script exits.")
    print(f"Logs: {LOGS}/")
    print(f"\nSearch a domain:")
    ex = list(targets)[0]
    ex_port = DOMAINS[ex]["port"]
    print(f"  curl -X POST http://127.0.0.1:{ex_port}/search \\")
    print(f"       -H 'Content-Type: application/json' \\")
    print(f"       -d '{{\"query\": \"{DOMAINS[ex]['queries'][0]}\", \"k\": 10}}'")


if __name__ == "__main__":
    main()
