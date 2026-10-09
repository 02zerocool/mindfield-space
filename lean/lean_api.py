"""
lean_api.py — Memory access layer  :8018 (default)
===================================================
Search, write, and embed against a local LanceDB corpus.

Endpoints:
  POST /search   {"query":"...", "k":20, "where":"...", "chat_id":"..."}
  POST /write    {"content":"...", "source":"...", "tags":[]}
  POST /embed    {"text":"..."}
  GET  /health
  GET  /stats

Config (env vars or .env):
  LANCE_DB_PATH   path to LanceDB directory         default: ./lancedb
  LEAN_PORT       port to listen on                 default: 8018
  EMBED_URL       embedding server base URL         default: http://127.0.0.1:8082
  EMBED_MODEL     model name sent to /v1/embeddings default: nomic-embed-text-v1.5
  EMBED_DIM       embedding vector dimension        default: 768

Start:
  python lean/lean_api.py
  # or via docker-compose: see docker-compose.yml
"""

import os, sys, time, json, uuid
from pathlib import Path
from typing import Optional, List

# ── Offline lock — never call HuggingFace Hub ────────────────────────────────
os.environ["HF_HUB_OFFLINE"]      = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"]  = "1"

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests as _requests
import lancedb
import pyarrow as pa

# ── Config ────────────────────────────────────────────────────────────────────
LANCE_PATH  = os.environ.get("LANCE_DB_PATH", str(Path(__file__).parent.parent / "lancedb"))
PORT        = int(os.environ.get("LEAN_PORT", "8018"))
EMBED_BASE  = os.environ.get("EMBED_URL", "http://127.0.0.1:8082")
EMBED_URL   = f"{EMBED_BASE}/v1/embeddings"
EMBED_MODEL = os.environ.get("EMBED_MODEL", "nomic-embed-text-v1.5")
DIM         = int(os.environ.get("EMBED_DIM", "768"))
TABLE_NAME  = "memory"

# ── Embedding model reference ──────────────────────────────────────────────────
# Default: nomic-embed-text-v1.5 — 768-dim, runs on CPU via llama-server
#
# Other compatible models (adjust EMBED_DIM to match):
#   mxbai-embed-large-v1     1024-dim   higher accuracy, more RAM
#   all-MiniLM-L6-v2          384-dim   fastest, lowest RAM, good for short text
#   snowflake-arctic-embed-m  768-dim   strong retrieval accuracy
#   bge-large-en-v1.5        1024-dim   strong English retrieval
#
# Any OpenAI-compatible /v1/embeddings endpoint works — local or remote.
# Change EMBED_MODEL and EMBED_DIM to match your chosen model.
# WARNING: changing DIM on an existing table requires a full re-ingest.

# ── LanceDB setup ─────────────────────────────────────────────────────────────
_db    = lancedb.connect(LANCE_PATH)
_table = None   # created/opened on first write or search


def _get_table():
    global _table
    if _table is not None:
        return _table
    if TABLE_NAME in _db.list_tables():
        _table = _db.open_table(TABLE_NAME)
    else:
        # Create empty table with schema on first access
        schema = pa.schema([
            pa.field("id",      pa.string()),
            pa.field("content", pa.string()),
            pa.field("source",  pa.string()),
            pa.field("tags",    pa.string()),     # JSON-encoded list
            pa.field("ts",      pa.float64()),
            pa.field("vector",  pa.list_(pa.float32(), DIM)),
        ])
        _table = _db.create_table(TABLE_NAME, schema=schema)
        print(f"[lean] created new LanceDB table '{TABLE_NAME}' at {LANCE_PATH}", flush=True)
    return _table


# ── Embedder (nomic-embed-text-v1.5 via llama-server :8082) ──────────────────
_embed_session = _requests.Session()

def embed(text: str, task: str = "search_document") -> list:
    """Embed text via nomic-embed-text-v1.5. Returns 768-dim float list."""
    safe = (text or "").strip() or "empty"
    if not safe.startswith(("search_query:", "search_document:")):
        safe = f"{task}: {safe}"
    safe = safe[:3000]
    try:
        r = _embed_session.post(EMBED_URL, json={"model": EMBED_MODEL, "input": safe}, timeout=15)
        r.raise_for_status()
        return r.json()["data"][0]["embedding"]
    except Exception as e:
        raise RuntimeError(f"[embed] :8082 failed: {e}") from e


# ── FastAPI ───────────────────────────────────────────────────────────────────
app = FastAPI(title="Lean Memory API", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ── Request models ────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query:   str
    k:       int = 20
    where:   Optional[str] = None    # LanceDB SQL predicate e.g. "source = 'my_book'"
    chat_id: Optional[str] = None    # reserved for working memory extension

class WriteRequest(BaseModel):
    content: str
    source:  str = ""
    tags:    List[str] = []

class EmbedRequest(BaseModel):
    text: str


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "port": PORT, "lancedb_path": LANCE_PATH}


@app.get("/stats")
def stats():
    try:
        t = _get_table()
        n = t.count_rows()
    except Exception:
        n = 0
    return {"memory": n, "lancedb_path": LANCE_PATH}


@app.post("/search")
def search(req: SearchRequest):
    """Semantic search. Returns top-k results ordered by cosine similarity."""
    try:
        vec = embed(req.query, task="search_query")
        t   = _get_table()
        q   = t.search(vec).limit(req.k)
        if req.where:
            q = q.where(req.where)
        rows = q.to_list()
        results = []
        for row in rows:
            dist = float(row.get("_distance", 1.0))
            results.append({
                "id":         row.get("id", ""),
                "content":    row.get("content", ""),
                "source":     row.get("source", ""),
                "tags":       json.loads(row.get("tags", "[]")),
                "distance":   round(dist, 4),                        # lower = more similar
                "similarity": round(max(0.0, 1.0 - dist), 4),   # higher = more similar, clamped [0,1]
            })
        return {"results": results, "count": len(results), "query": req.query}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/write")
def write(req: WriteRequest):
    """Write a memory chunk. Embeds content and appends to LanceDB."""
    if not req.content.strip():
        raise HTTPException(400, "content cannot be empty")
    try:
        vec = embed(req.content, task="search_document")
        t   = _get_table()
        t.add([{
            "id":      str(uuid.uuid4()),
            "content": req.content[:8000],
            "source":  req.source or "manual",
            "tags":    json.dumps(req.tags),
            "ts":      time.time(),
            "vector":  vec,
        }])
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/embed")
def embed_endpoint(req: EmbedRequest):
    """Embed text — returns raw 768-dim vector."""
    try:
        vec = embed(req.text)
        return {"vector": vec, "dim": len(vec)}
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"[lean] starting on :{PORT} — LanceDB at {LANCE_PATH}", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=PORT)
