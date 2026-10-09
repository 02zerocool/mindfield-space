"""
route.py — pick a mission domain without pretending to be the Conductor
=======================================================================
Scores the query against each domain's seed queries by token overlap.
Optional --post sends /search to the winning port.

Usage:
  python mission/route.py "CO2 scrubber anomaly"
  python mission/route.py "CO2 scrubber anomaly" --post
"""

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from domains.space_domains import DOMAINS

TOKEN = re.compile(r"[a-z0-9][a-z0-9\-]+")


def tokens(text: str) -> set[str]:
    return set(TOKEN.findall(text.lower()))


def rank(query: str):
    q = tokens(query)
    df, bags = {}, {}
    for name, d in DOMAINS.items():
        bag = tokens(" ".join(d["queries"]) + " " + d["description"])
        bags[name] = bag
        for tok in bag:
            df[tok] = df.get(tok, 0) + 1
    scored = []
    for name, bag in bags.items():
        hit = q & bag
        rare = sum(1 for tok in hit if df.get(tok, 9) == 1)
        scored.append((name, len(hit), rare))
    scored.sort(key=lambda item: (item[1], item[2]), reverse=True)
    return scored


def main() -> int:
    parser = argparse.ArgumentParser(description="Keyword router for mission domains")
    parser.add_argument("query")
    parser.add_argument("--post", action="store_true", help="POST /search to the winner")
    parser.add_argument("--k", type=int, default=10)
    args = parser.parse_args()

    scored = rank(args.query)
    winner, score, rare = scored[0]
    if score == 0:
        print("no domain overlap — stay on main lean :8018")
        return 2

    d = DOMAINS[winner]
    print(f"route  {winner}  :{d['port']}  overlap={score} rare={rare}")
    for name, s, r in scored[:3]:
        print(f"  overlap={s} rare={r}  {name}")

    if not args.post:
        return 0

    payload = json.dumps({"query": args.query, "k": args.k}).encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{d['port']}/search",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            sys.stdout.write(r.read().decode())
            sys.stdout.write("\n")
        return 0
    except Exception as e:
        print(f"post failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
