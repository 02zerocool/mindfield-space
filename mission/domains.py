"""
domains.py — Launch and manage mission domain stacks
=====================================================
Starts lean_api instances for each pre-configured space domain.
Each domain is a separate LanceDB on its own port.

Usage:
  python mission/domains.py --start-all
  python mission/domains.py --start telemetry fmea
  python mission/domains.py --status
  python mission/domains.py --stop
  python mission/domains.py --list
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from domains.space_domains import DOMAINS

ROOT = Path(__file__).parent.parent
LEAN_PY = ROOT / "lean" / "lean_api.py"
LOGS = ROOT / "logs"
LOGS.mkdir(exist_ok=True)
PID_FILE = LOGS / "domain_pids.json"


def start_domain(name: str) -> subprocess.Popen | None:
    if name not in DOMAINS:
        print(f"  Unknown domain: {name}")
        return None

    d = DOMAINS[name]
    lancedb_path = str(ROOT / d["lancedb"].lstrip("./"))
    Path(lancedb_path).mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["LANCE_DB_PATH"] = lancedb_path
    env["LEAN_PORT"] = str(d["port"])
    env["EMBED_URL"] = env.get("EMBED_URL", "http://127.0.0.1:8082")

    log_out = open(LOGS / f"domain_{name}_out.log", "a")
    log_err = open(LOGS / f"domain_{name}_err.log", "a")
    proc = subprocess.Popen(
        [sys.executable, str(LEAN_PY)],
        env=env,
        stdout=log_out,
        stderr=log_err,
        start_new_session=True,
    )
    print(f"  STARTED  {name:<15}  :{d['port']}  pid={proc.pid}")
    return proc


def check_domain(name: str) -> bool:
    d = DOMAINS.get(name, {})
    port = d.get("port")
    if not port:
        return False
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as r:
            return json.loads(r.read()).get("status") == "ok"
    except Exception:
        return False


def load_pids() -> dict:
    if not PID_FILE.exists():
        return {}
    return json.loads(PID_FILE.read_text())


def save_pids(pids: dict) -> None:
    PID_FILE.write_text(json.dumps(pids, indent=2))


def stop_domains() -> None:
    pids = load_pids()
    if not pids:
        print("no pid file — nothing to stop")
        return
    for name, pid in pids.items():
        try:
            os.kill(pid, signal.SIGTERM)
            print(f"  STOPPED  {name:<15}  pid={pid}")
        except ProcessLookupError:
            print(f"  GONE     {name:<15}  pid={pid}")
        except PermissionError as e:
            print(f"  FAIL     {name:<15}  {e}")
    PID_FILE.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description="Mission domain stack manager")
    parser.add_argument("--start-all", action="store_true")
    parser.add_argument("--start", nargs="+", choices=list(DOMAINS.keys()))
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--stop", action="store_true")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

    if args.list:
        print(f"\n  {'Name':<15} {'Port':<8} Description")
        for name, d in DOMAINS.items():
            print(f"  {name:<15} :{d['port']:<7} {d['description']}")
        return

    if args.stop:
        stop_domains()
        return

    if args.status:
        for name, d in DOMAINS.items():
            up = check_domain(name)
            status = "UP " if up else "n/a"
            print(f"  {status}  {name:<15}  :{d['port']}")
        return

    targets = list(DOMAINS.keys()) if args.start_all else (args.start or [])
    if not targets:
        parser.print_help()
        return

    pids = load_pids()
    for name in targets:
        proc = start_domain(name)
        if proc:
            pids[name] = proc.pid
    save_pids(pids)

    time.sleep(3)
    for name in targets:
        mark = "UP  " if check_domain(name) else "WAIT"
        print(f"  {mark}  {name:<15}  :{DOMAINS[name]['port']}")
    print(f"pids: {PID_FILE}")
    print("route: python mission/route.py \"your query\"")


if __name__ == "__main__":
    main()
