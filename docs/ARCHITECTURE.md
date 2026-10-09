# Architecture — Memory Topology as Cosmic Topology

## The observation

When a semantic memory field of sufficient size is projected via UMAP dimensionality
reduction, the resulting geometry is not random. It forms **hubs, filaments, and voids** —
a scale-free network topology that appears at every zoom level.

This is the same topology as the cosmic web.

Not metaphorically. Measurably. The statistical properties — degree distribution,
clustering coefficient, filamentary connectivity — match across scales:

| System | Scale | Topology |
|---|---|---|
| Fruit fly mushroom body | 10⁻⁶ m | Expansion-compression, hub-spoke |
| Human cerebellar connectome | 10⁻² m | Granule-layer expansion, Purkinje integration |
| Semantic memory field | — | Hub clusters, filament bridges, void regions |
| Cosmic web | 10²⁵ m | Dark matter filaments, galaxy cluster nodes, supervoids |

For space scientists and engineers, this is not an abstraction.
Your knowledge of the universe has the same topological structure as the universe it describes.
The retrieval geometry of your memory field is isomorphic to the physical geometry of what you study.

---

## The memory architecture

```
Your documents (PDFs, reports, procedures, papers)
        │
        ▼
nomic-embed-text-v1.5 (768-dim vectors via llama-server :8082)
        │
        ▼
LanceDB (local columnar vector store — append-only, versioned)
        │
        ▼
lean_api :8018  (search / write / embed — FastAPI)
        │
        ├─── /search   →  ANN over 768-dim vectors → top-k results
        ├─── /write    →  embed + append to LanceDB
        └─── /health   →  stack health check
```

This is the v0.1 path. It is a semantic memory retrieval system.
It does not generate responses. It finds the most relevant passages in your corpus.

---

## Domain stacks — the thalamic routing layer

The domain specialist pattern mirrors the thalamic routing function in the CBGT circuit:

```
Query (text)
    │
    ▼
Domain router (which knowledge area is this?)
    │
    ├─── telemetry    :18001  LanceDB_telemetry
    ├─── procedures   :18002  LanceDB_procedures
    ├─── fmea         :18003  LanceDB_fmea
    ├─── propulsion   :18004  LanceDB_propulsion
    ├─── astrodynamics:18005  LanceDB_astrodynamics
    ├─── life_support :18006  LanceDB_life_support
    ├─── comms        :18007  LanceDB_comms
    ├─── science      :18008  LanceDB_science
    ├─── regulations  :18009  LanceDB_regulations
    └─── planetary    :18010  LanceDB_planetary
```

Each domain is a separate LanceDB with its own lean_api instance.
The separation matters: a query about CO2 scrubber anomalies routes to `life_support`,
not the full corpus — tighter signal, lower noise.

The Godot 3D visualisation (`godot/MemoryGenesis.gd`) makes this routing visible.
Each domain cluster is a node in the memory field. Thought bursts show which domain
is being queried and what it returns, in real time.

---

## Why LanceDB

- **Local** — no server process, no cloud, no network
- **Append-only** — no corruption on crash; interrupted writes leave orphan deltas, existing data is never touched
- **Columnar** — metadata filters (`WHERE source = 'nasa_tm_123'`) are fast column scans
- **Versioned** — every write creates a new version; older versions are recoverable

For mission-critical document stores, the append-only guarantee matters.
LanceDB is safe to run continuously. It cannot corrupt itself mid-write.

---

## The embedding model

**nomic-embed-text-v1.5** — 768-dimensional text embedding model.
Runs locally via `llama-server` (from llama.cpp). No external API calls.

The 768-dim space is the geometry of your memory field.
Similar documents cluster together. Queries find their nearest neighbours.
The topology that emerges — given enough documents — is the cosmic web.

Alternative models (set `EMBED_MODEL` and `EMBED_DIM` in `.env`):
- `mxbai-embed-large-v1` — 1024-dim, higher accuracy, more RAM
- `snowflake-arctic-embed-m` — 768-dim, strong retrieval

---

## What the full architecture adds (not in this repo)

The production system this framework is derived from extends the retrieval chain:

```
lean_api /search results
    │
    ▼
RWKV working memory blend     [shifts retrieval based on conversation context]
    │
    ▼
ONNX Conductor                [routes query to the right domain and inference path]
    │
    ▼
Mamba LTC voice               [timing, pattern completion, cognitive signal]
    │
    ▼
GGUF generation               [produces the actual response text]
```

These components — RWKV, ONNX Conductor, Mamba CORE — require their own trained
model weights and considerable setup. They are documented here as the complete
architecture so you understand what this framework is the foundation of.

The ONNX Conductor is particularly relevant at mission scale: rather than a human
typing queries, the conductor routes signals automatically — telemetry alerts,
anomaly detections, engineer queries — to the right domain corpus at the right moment.
That is the thalamic function made computational.

---

## The one-engineer principle

This framework is designed for one person. A single engineer or scientist.

The value of a personal memory field comes from its specificity to one person's
knowledge, one mission's documents, one research programme's literature.
It is not designed to be shared across a team or organisation.

That is a feature. A field built from one engineer's years of mission experience
retrieves differently — more accurately, more contextually — than a shared database
built from everyone's documents averaged together.

Build your own field. Keep it yours.
