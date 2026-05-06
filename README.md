# Argument Graph Fingerprinting — AI vs Human-Written Papers

A static site that lets you browse 40 paper introductions (20 AI-generated, 20 human-written) as **typed argument graphs** alongside the original PDFs.

**Live demo**: enable GitHub Pages on this repo → `https://<username>.github.io/<repo>/`

**Project narrative + metrics**: see [REPORT.md](REPORT.md)
**Tooling + handoff notes**: see [HANDOVER.md](HANDOVER.md)

## Local viewing

```bash
python3 -m http.server 8765
# open http://localhost:8765/index.html
```

## Folder structure

- `ai/` — 20 AI-generated paper graphs (JSON + SVG)
- `human/` — 20 human-written paper graphs (JSON + SVG)
- `pdfs/ai/`, `pdfs/human/` — original PDFs
- `index.html` — single-page viewer (sidebar + split SVG/PDF panels)
- `make_site.py` — regenerates `index.html` from JSON + PDFs
- `metrics.csv` — per-paper structural metrics
- `REPORT.md` — methodology + 10-metric comparison report
