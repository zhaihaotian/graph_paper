# Argument Graph Fingerprinting — AI vs Human-Written Papers

A static site that lets you browse 80 paper introductions (40 AI-generated, 40 human-written) as **typed argument graphs** alongside the original PDFs.

**Live demo**: https://zhaihaotian.github.io/graph_paper/

**Tooling + handoff notes**: see [HANDOVER.md](HANDOVER.md)

## Local viewing

```bash
python3 -m http.server 8765
# open http://localhost:8765/index.html
```

## Folder structure

- `ai/` — 40 AI-generated paper graphs (JSON + SVG)
- `human/` — 40 human-written paper graphs (JSON + SVG)
- `pdfs/ai/`, `pdfs/human/` — original PDFs
- `intros/` — extracted intro text per paper
- `skill/` — bundled extraction toolchain
- `index.html` — single-page viewer (sidebar + split SVG/PDF panels)
- `make_site.py` — regenerates `index.html` from JSON + PDFs
- `metrics.csv` — per-paper structural metrics
- `metrics_plots.png` — 6-metric boxplot
