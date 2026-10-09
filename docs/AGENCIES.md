# Agency-Specific Document Sources

A guide to public document sources for engineers and scientists at each major space agency.

---

## NASA (United States)

**NASA Technical Reports Server (NTRS)**
- URL: https://ntrs.nasa.gov
- Access: Public, no authentication
- Built-in tool: `python mission/ingest_ntrs.py --query "your topic"`
- Covers: NASA technical memoranda, contractor reports, conference papers

**NASA ADS (Astrophysics Data System)**
- URL: https://ui.adsabs.harvard.edu
- Access: Free API key required — register at https://ui.adsabs.harvard.edu/user/settings/token
- Built-in tool: `python mission/ingest_ads.py --query "your topic"`
- Covers: Astrophysics, planetary science, space physics, NASA technical reports

**NASA Open Data Portal**
- URL: https://data.nasa.gov
- Access: Public
- Content: Datasets, APIs, mission data — download and ingest PDFs/CSVs manually

**NASA Lessons Learned Information System (LLIS)**
- URL: https://llis.nasa.gov
- Access: Public (some content restricted to NASA personnel)
- Ingest: Download PDFs and use `python mission/ingest_papers.py --ingest --dir llis/`

**NASA Technical Standards (NASA-STD)**
- URL: https://standards.nasa.gov
- Access: Public
- Ingest: Download PDFs manually — ingest into `regulations` domain

---

## ESA (Europe)

**ESA Publication Server (ESAC)**
- URL: https://www.cosmos.esa.int/web/esdc
- Access: Public for published papers; mission data may require registration

**ESA Technical Reports**
- URL: https://esamultimedia.esa.int/multimedia/publications/
- Access: Public
- Ingest: Download PDFs, use `python mission/ingest_papers.py`

**ECSS Standards (European Cooperation for Space Standardization)**
- URL: https://ecss.nl/standards/
- Access: Public (free registration for downloads)
- Ingest into `regulations` domain: `python mission/ingest_papers.py --ingest --dir ecss/`

**ESA Sky (astronomical data)**
- URL: https://sky.esa.int
- FITS data: Download and use `python mission/fits_metadata.py`

---

## JAXA (Japan)

**JAXA Repository (JAXA Repository and e-Library)**
- URL: https://repository.exst.jaxa.jp/
- Access: Public
- Ingest: Download PDFs, ingest manually

**J-STAGE (Japan Science and Technology Agency)**
- URL: https://www.jstage.jst.go.jp
- Access: Public (many papers open access)
- Search and download PDFs relevant to your domain

---

## ISRO (India)

**ISRO Publications**
- URL: https://www.isro.gov.in/publications.html
- Access: Public
- Ingest: Download PDFs and ingest manually

**Indian Journal of Radio and Space Physics**
- Available via J-Gate and NISCAIR
- Ingest: Download PDFs

---

## CNSA (China)

**Chinese Space Science Data Center**
- URL: https://www.nssdc.ac.cn/en/
- Access: Registration required for data; some publications public

**Space Science Letters (Chinese)**
- Available via ScienceDirect and CNKI

---

## CSA (Canada)

**CSA Publications**
- URL: https://www.asc-csa.gc.ca/eng/publications/
- Access: Public
- Ingest: Download PDFs manually

---

## ROSCOSMOS (Russia)

**Space Research Institute (IKI)**
- URL: https://www.iki.rssi.ru/eng/
- Access: Public for published papers

---

## Multi-agency sources

**arXiv (all agencies)**
- Built-in tool: `python mission/ingest_arxiv_space.py`
- Relevant categories: astro-ph, astro-ph.EP, gr-qc, physics.space-ph
- No authentication, fully open access

**IAC Proceedings (International Astronautical Congress)**
- URL: https://iafastro.directory/iac/
- Some papers open access, some require IAF membership
- Ingest: Download available PDFs

**AIAA (American Institute of Aeronautics and Astronautics)**
- URL: https://arc.aiaa.org
- Access: Institutional subscription or pay-per-paper
- Many conference papers become open access after 12 months

---

## Ingest workflow for any agency

```bash
# 1. Download PDFs to a directory
mkdir agency_docs/

# 2. Dry run to preview
python mission/ingest_papers.py --dry-run --dir agency_docs/

# 3. Export your reference library as BibTeX (from Zotero/Mendeley)
# File -> Export Library -> BibTeX -> save as library.bib

# 4. Ingest with metadata
python mission/ingest_papers.py --ingest --dir agency_docs/ --bib library.bib

# 5. Or ingest directly into a domain stack
python mission/ingest_papers.py --ingest --dir regulations_docs/ \
    --lean-url http://127.0.0.1:18009

# 6. Verify
python scripts/health_check.py
```

---

## FITS data sources

| Source | URL | FITS format |
|---|---|---|
| HST/JWST (MAST) | https://mast.stsci.edu | Standard FITS |
| Chandra | https://cxc.harvard.edu/cda/ | FITS event files |
| XMM-Newton | https://www.cosmos.esa.int/web/xmm-newton/xsa | FITS |
| TESS | https://mast.stsci.edu/portal/Mashup/Clients/Mast/Portal.html | FITS |
| Kepler/K2 | https://mast.stsci.edu | FITS |
| Herschel | https://www.cosmos.esa.int/web/herschel/science-archive | FITS |

Use `python mission/fits_metadata.py --dir fits_downloads/ --ingest` for all of these.
