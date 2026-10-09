"""Prove lean can write the synthetic rows and search them. Exits 1 if empty."""
import json, sys, urllib.request
from pathlib import Path
LEAN = "http://127.0.0.1:8018"
FIXTURE = Path(__file__).parent.parent / "fixtures" / "synthetic_memory.jsonl"

def post(path, payload):
    req = urllib.request.Request(LEAN+path, data=json.dumps(payload).encode(), headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())

def main():
    try:
        with urllib.request.urlopen(LEAN+"/health", timeout=3) as r:
            if json.loads(r.read()).get("status") != "ok":
                return 1
    except Exception as e:
        print(f"lean down: {e}")
        return 1
    n = 0
    for line in FIXTURE.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        post("/write", {"content": row["content"], "source": row["source"], "tags": row["tags"]})
        n += 1
    found = post("/search", {"query": "synthetic reserved fields", "k": 3})
    results = found.get("results") or []
    print(f"wrote {n}, search {len(results)}")
    return 0 if results else 1

if __name__ == "__main__":
    sys.exit(main())
