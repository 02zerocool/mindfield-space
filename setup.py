"""
setup.py — First-run setup for Mindfield
=========================================
Run once after cloning. Creates directories, checks Python version,
installs deps, validates the embedding server.

Usage:
  python setup.py
  python setup.py --with-model
"""

import argparse
import subprocess
import sys
import os
import urllib.request
from pathlib import Path

MODEL_URL = "https://huggingface.co/nomic-ai/nomic-embed-text-v1.5-GGUF/resolve/main/nomic-embed-text-v1.5.Q8_0.gguf"
MODEL_NAME = "nomic-embed-text-v1.5.Q8_0.gguf"

ROOT = Path(__file__).parent

def run(cmd: list, check=True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, capture_output=True, text=True)

def step(msg: str):
    print(f"\n{'─'*60}")
    print(f"  {msg}")
    print('─'*60)

def ok(msg: str):   print(f"  ✓  {msg}")
def warn(msg: str): print(f"  ⚠  {msg}")
def fail(msg: str): print(f"  ✗  {msg}")


def check_python():
    step("Python version")
    v = sys.version_info
    if v >= (3, 11):
        ok(f"Python {v.major}.{v.minor}.{v.micro}")
    else:
        fail(f"Python {v.major}.{v.minor} — requires 3.11+")
        sys.exit(1)


def create_dirs():
    step("Creating directories")
    dirs = [
        "lancedb",
        "models",
        "ingest/ingest_queue",
        "ingest/ingest_done",
        "logs",
    ]
    for d in dirs:
        p = ROOT / d
        p.mkdir(parents=True, exist_ok=True)
        ok(d)


def install_deps():
    step("Installing Python dependencies")
    req = ROOT / "lean" / "requirements.txt"
    r = run([sys.executable, "-m", "pip", "install", "-r", str(req)], check=False)
    if r.returncode == 0:
        ok("lean dependencies installed")
    else:
        warn(f"pip returned {r.returncode} — {r.stderr[:200]}")

    # Optional PDF support
    r2 = run([sys.executable, "-m", "pip", "install", "pypdf"], check=False)
    if r2.returncode == 0:
        ok("pypdf installed (PDF ingest support)")
    else:
        warn("pypdf not installed — PDF ingest will be skipped")



def fetch_model():
    step("Embedding model")
    dest = ROOT / "models" / MODEL_NAME
    if dest.exists() and dest.stat().st_size > 1_000_000:
        ok(f"already present ({dest.stat().st_size} bytes)")
        return
    print(f"  downloading {MODEL_NAME}")
    try:
        urllib.request.urlretrieve(MODEL_URL, dest)
    except Exception as e:
        fail(f"download failed: {e}")
        sys.exit(1)
    if dest.stat().st_size < 1_000_000:
        fail("model file is empty")
        sys.exit(1)
    ok(f"saved {dest}")

def copy_env():
    step(".env setup")
    env_example = ROOT / ".env.example"
    env_file    = ROOT / ".env"
    if env_file.exists():
        ok(".env already exists — not overwriting")
    elif env_example.exists():
        import shutil
        shutil.copy(env_example, env_file)
        ok(".env created from .env.example — edit to configure")
    else:
        warn(".env.example not found")


def check_docker():
    step("Docker (optional)")
    r = run(["docker", "--version"], check=False)
    if r.returncode == 0:
        ok(r.stdout.strip())
        r2 = run(["docker", "compose", "version"], check=False)
        if r2.returncode == 0:
            ok(r2.stdout.strip())
        else:
            warn("docker compose not found — use 'docker-compose' (v1) or install Compose V2")
    else:
        warn("Docker not found — you can still run lean_api.py directly without Docker")


def print_next_steps():
    step("Setup complete")
    print("""
  Next steps:
  ──────────────────────────────────────────────────────
  1. Download the embedding model (required):
     wget https://huggingface.co/nomic-ai/nomic-embed-text-v1.5-GGUF/resolve/main/nomic-embed-text-v1.5.Q8_0.gguf
     mv nomic-embed-text-v1.5.Q8_0.gguf models/

  2. Add your documents to  ingest/ingest_queue/
     (See ingest/ingest_queue/README.md for what makes a good corpus)

  3. Start the stack:
     docker-compose up nomic-embed lean     # Docker (these two only — not 'up -d')
     OR
     llama-server --model models/nomic-embed-text-v1.5.Q8_0.gguf --port 8082 --host 127.0.0.1 --embedding &
     python lean/lean_api.py               # lean API

  4. Ingest your documents:
     python ingest/ingest_bulk_memory.py --dry-run
     python ingest/ingest_bulk_memory.py --ingest

  5. Verify it works:
     python scripts/health_check.py
     curl http://127.0.0.1:8018/stats

  ──────────────────────────────────────────────────────
  Note: a web frontend (:8008) is not included in v0.1.
  The deliverable is the memory API at :8018 + ingest pipeline.

  For the embedding server (needed before lean_api):
    llama-server --model models/nomic-embed-text-v1.5.Q8_0.gguf --port 8082 --embedding
    (or: docker-compose up nomic-embed)
""")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--with-model", action="store_true")
    args = parser.parse_args()
    print("\nMindfield — Extended Mind Framework")
    print("Setup\n")
    check_python()
    create_dirs()
    install_deps()
    copy_env()
    check_docker()
    if args.with_model:
        fetch_model()
    print_next_steps()
