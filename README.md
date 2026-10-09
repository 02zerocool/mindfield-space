# Mindfield — Space

**A semantic memory field for space engineers and scientists.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](https://python.org)
[![LanceDB](https://img.shields.io/badge/Memory-LanceDB-orange)](https://lancedb.com)
[![Agencies](https://img.shields.io/badge/For-NASA%20·%20ESA%20·%20JAXA%20·%20ISRO%20·%20CSA%20·%20CNSA%20·%20ROSCOSMOS-blue)]()

---

> *"The universe's dark matter filaments connect galaxy clusters in a scale-free network —
> hubs, spokes, voids. When you project a semantic memory field of sufficient size through
> UMAP, you see the same topology. Your knowledge of the cosmos has the same shape as the
> cosmos itself."*

---

## The observation behind this project

When a personal memory field of hundreds of thousands of records is projected via UMAP
dimensionality reduction, the resulting geometry is not random. It shows **hubs, filaments,
and voids** — a scale-free topology that appears at every zoom level.

This is the same topology as:

- **The fruit fly mushroom body** — the insect's associative memory, compressed sensory projections
- **The human cerebellar connectome** — Purkinje cells integrating ~200,000 inputs each
- **The cosmic web** — dark matter filaments connecting galaxy clusters across megaparsecs

Three systems, nine orders of magnitude in scale, same statistical structure.

For space engineers and scientists, this is not an abstraction. Your knowledge of the
universe — missions, telemetry, orbital mechanics, planetary science — **has the same
topology as the universe it describes**. The retrieval geometry mirrors the physical geometry.

This project makes that visible and searchable.

---

## What this is

A local, offline semantic memory system for individual space engineers and scientists.

You store your technical documents — NASA technical reports, mission procedures, FMEA logs,
research papers, ESA standards, experimental write-ups — and search them by meaning, not keyword.

A query like `"ECLSS water recovery anomaly thermal loop"` finds the relevant passages
across thousands of documents regardless of the exact words used, because the search is
semantic — it understands what you mean, not just what you typed.

---

## What this is not

- Not a chatbot. It does not generate responses.
- Not a shared database. One person, one field, full stop.
- Not cloud-dependent. Zero external services required for core operation.
- Not a replacement for official mission document management systems. A personal knowledge
  layer that runs alongside them.

---

## Supported agencies and document sources

| Agency | Document source | Built-in support |
|---|---|---|
| NASA | NTRS (Technical Reports Server) | ✅ `mission/ingest_ntrs.py` |
| NASA | arXiv astro-ph, gr-qc | ✅ `mission/ingest_arxiv_space.py` |
| NASA / All | NASA ADS (Astrophysics Data System) | ✅ `mission/ingest_ads.py` (free API key) |
| ESA | ESAC / ESA publications | 📄 PDF ingest via `ingest_papers.py` |
| JAXA | JAXA Repository (J-STAGE) | 📄 PDF ingest |
| ISRO | ISRO publications | 📄 PDF ingest |
| All | Local PDF, TXT, MD, IPYNB | ✅ Built-in |
| All | BibTeX libraries (Zotero, Mendeley) | ✅ Built-in |

All NASA Technical Reports are public domain. NTRS requires no authentication.
NASA ADS requires a free API key (registration at ui.adsabs.harvard.edu).

---

## Pre-configured mission domains

The system ships with domain stacks pre-configured for the major knowledge areas
of a space mission. Each is a separate LanceDB with its own lean_api instance.

```
mindfield-space domains:

  telemetry        :18001   Sensor logs, anomaly reports, system health data
  procedures       :18002   Mission procedures, checklists, crew protocols
  fmea             :18003   Failure modes, fault trees, anomaly investigations
  propulsion       :18004   Propulsion systems, propellant chemistry, burn data
  astrodynamics    :18005   Orbital mechanics, trajectory design, navigation
  life_support     :18006   ECLSS, environmental control, human factors
  comms            :18007   Communications, link budgets, RF systems
  science          :18008   Mission science objectives, instrument specifications
  regulations      :18009   NASA-STD, ECSS standards, safety requirements
  planetary        :18010   Planetary geology, atmospheres, surface science
```

Launch all domains:
```bash
python mission/domains.py --start-all
```

Or individual domains:
```bash
python mission/domains.py --start telemetry
python mission/domains.py --start astrodynamics
```

---

## Quick start

```bash
# 1. Clone
git clone https://github.com/02zerocool/mindfield-space
cd mindfield-space

# 2. Setup
python setup.py

# 3. Download embedding model (~300MB)
wget -P models/ https://huggingface.co/nomic-ai/nomic-embed-text-v1.5-GGUF/resolve/main/nomic-embed-text-v1.5.Q8_0.gguf

# 4. Start the embedding server
llama-server --model models/nomic-embed-text-v1.5.Q8_0.gguf \
             --port 8082 --host 127.0.0.1 --embedding

# 5. Start the main memory API
python lean/lean_api.py

# 6. Ingest NASA technical reports on a topic
python mission/ingest_ntrs.py --query "orbital debris mitigation" --k 20 --ingest

# 7. Ingest your own PDFs
python mission/ingest_papers.py --ingest --dir my_papers/ --bib library.bib

# 8. Search
curl -X POST http://127.0.0.1:8018/search \
     -H "Content-Type: application/json" \
     -d '{"query": "debris mitigation passivation requirements", "k": 10}'
```

---

## Corpus strategy for space work

The same principle applies here as anywhere: **signal density beats volume**.

**High signal:**
- NASA technical reports directly relevant to your mission or research area
- Mission anomaly reports and lessons-learned documents
- Your own analysis notes and experimental write-ups
- Standards and procedures you actually work with (NASA-STD-8719, ECSS-E-ST-10C, etc.)
- Papers you have read and found significant

**Low signal:**
- Full NTRS bulk downloads without filtering
- Superseded document versions (keep only current)
- Documents from unrelated mission types

Start narrow and deep. A field of 2,000 highly relevant documents will outperform
20,000 tangentially related ones for your actual queries.

---

## FITS file support

Astronomical FITS files carry rich header metadata — instrument parameters, observation
targets, coordinates, exposure times, processing provenance. The FITS metadata extractor
reads headers and writes them as searchable memory records.

```bash
python mission/fits_metadata.py --dir observations/ --ingest
```

The FITS data arrays themselves are not stored — only the human-readable metadata.
This keeps the memory field lightweight while making your observation archive searchable.

---

## Project structure

```
mindfield-space/
├── README.md
├── docs/
│   ├── ARCHITECTURE.md          ← the pattern: memory topology = cosmic topology
│   └── AGENCIES.md              ← agency-specific document source guide
├── lean/
│   ├── lean_api.py              ← memory access layer (search/write/embed)
│   ├── requirements.txt
│   ├── Dockerfile
│   └── domain_lean.py.template
├── ingest/
│   ├── ingest_bulk_memory.py    ← generic file ingest
│   └── ingest_queue/
├── mission/                     ← space-specific ingest tools
│   ├── README.md
│   ├── domains.py               ← launch/manage domain stacks
│   ├── ingest_ntrs.py           ← NASA Technical Reports Server
│   ├── ingest_ads.py            ← NASA ADS astrophysics literature
│   ├── ingest_arxiv_space.py    ← arXiv space categories
│   ├── ingest_papers.py         ← general academic papers + BibTeX
│   └── fits_metadata.py         ← FITS header extraction
├── domains/                     ← pre-configured domain definitions
│   └── space_domains.py
├── godot/
│   ├── MemoryGenesis.gd         ← 3D memory burst engine (Godot 4)
│   └── README.md
├── scripts/
│   └── health_check.py
├── services/
│   └── install.ps1
├── docker-compose.yml
├── setup.py
└── .env.example
```

---

## The architecture — why this topology matters for space

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full technical rationale.

The short version: the same scale-free topology that appears in the cosmic web
appears in any sufficiently large semantic memory field. For space scientists,
this means the retrieval structure of your knowledge base is isomorphic to the
physical structure of what you study. Queries propagate through the memory field
the same way signal propagates through a network of galaxy filaments.

This is not a metaphor. It is a measurable topological property.

---

## Built with

- **[Anthropic / Claude](https://anthropic.com)** — Claude was the reasoning partner throughout
  the design and build of the system this framework is derived from.
- **[LanceDB](https://lancedb.com)** — local columnar vector database
- **[nomic-embed-text-v1.5](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5-GGUF)** by Nomic AI
- **[llama.cpp](https://github.com/ggerganov/llama.cpp)** by Georgi Gerganov
- **[Godot Engine](https://godotengine.org)** — 3D memory visualisation
- **[FastAPI](https://fastapi.tiangolo.com)** by Sebastián Ramírez
- **[NASA NTRS](https://ntrs.nasa.gov)** — public domain technical reports
- **[NASA ADS](https://ui.adsabs.harvard.edu)** — astrophysics literature database

---

## Licence

MIT. The cosmos is public domain.

---

*"We are made of star stuff, and we are a way for the cosmos to know itself."*
*— Carl Sagan*

*Your memory of the cosmos has the same shape as the cosmos.*
*That is what this framework makes searchable.*
