# Mission tools

Space-specific ingest and data tools for Mindfield-Space.

| Tool | What it does |
|---|---|
| `domains.py` | Launch and manage all 10 domain lean_api stacks |
| `ingest_ntrs.py` | NASA Technical Reports Server — search and ingest by topic |
| `ingest_arxiv_space.py` | arXiv space categories — astro-ph, gr-qc, physics.space-ph |
| `ingest_ads.py` | NASA ADS astrophysics database (free API key required) |
| `ingest_papers.py` | General PDF/notebook ingest with BibTeX metadata support |
| `fits_metadata.py` | FITS header extraction — makes your observation archive searchable |

## Quick reference

```bash
# Start all 10 domain stacks
python mission/domains.py --start-all

# Ingest NASA reports on a topic
python mission/ingest_ntrs.py --query "Mars entry descent landing" --k 20 --ingest

# Ingest into a specific domain
python mission/ingest_ntrs.py --query "CO2 scrubber anomaly" --k 10 --ingest \
    --domain-url http://127.0.0.1:18006

# Fetch recent astro-ph.EP papers
python mission/ingest_arxiv_space.py --category astro-ph.EP --k 20 --ingest

# Ingest your own PDFs with BibTeX metadata
python mission/ingest_papers.py --ingest --dir papers/ --bib library.bib

# Make FITS observations searchable
python mission/fits_metadata.py --dir fits_data/ --ingest

# Write a note
python mission/ingest_papers.py --note "Anomaly on 2026-10-09: TCS sensor 4B out of limit" \
    --source "ops_notes"
```

## Domain routing

Each domain runs a separate lean_api pointing at its own LanceDB:

```
Query → domain router → telemetry    :18001 → LanceDB_telemetry
                      → procedures   :18002 → LanceDB_procedures
                      → fmea         :18003 → LanceDB_fmea
                      → propulsion   :18004 → LanceDB_propulsion
                      → astrodynamics:18005 → LanceDB_astrodynamics
                      → life_support :18006 → LanceDB_life_support
                      → comms        :18007 → LanceDB_comms
                      → science      :18008 → LanceDB_science
                      → regulations  :18009 → LanceDB_regulations
                      → planetary    :18010 → LanceDB_planetary
```

For agency document sources, see [docs/AGENCIES.md](../docs/AGENCIES.md).
