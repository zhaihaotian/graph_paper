#!/usr/bin/env python3
"""
make_site.py — generate a static single-page viewer for the 40 argument graphs.

Layout:
  - Top: filter bar (All / AI only / Human only)
  - Left: paper list (sortable by group)
  - Main (split): rendered SVG | original PDF, side-by-side

Output: index.html in argument_graphs_final/. Open via:
    cd argument_graphs_final && python3 -m http.server 8765
    # then visit http://localhost:8765/index.html
"""

import json
import os


HERE = os.path.dirname(os.path.abspath(__file__))


def load_papers():
    papers = []
    for label in ("ai", "human"):
        d = os.path.join(HERE, label)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".json"):
                continue
            with open(os.path.join(d, fn)) as f:
                j = json.load(f)
            stem = fn[:-5]
            pdf_rel = f"pdfs/{label}/{stem}.pdf"
            pdf_exists = os.path.exists(os.path.join(HERE, pdf_rel))
            papers.append({
                "label": label,
                "file": fn,
                "paper_id": j.get("paper_id", stem),
                "topic": j.get("paper_topic", ""),
                "anchor_paper": j.get("anchor_paper") or "",
                "nodes": len(j.get("nodes", [])),
                "edges": len(j.get("edges", [])),
                "svg_path": f"{label}/{stem}.svg",
                "pdf_path": pdf_rel if pdf_exists else "",
            })
    return papers


def build_html(papers):
    payload_json = json.dumps(papers, ensure_ascii=False)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Argument Graph Viewer · AI vs Human Papers</title>
<style>
  * {{ box-sizing: border-box; }}
  html, body {{ height: 100%; }}
  body {{
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", Helvetica, Arial, sans-serif;
    background: #f5f3ec;
    color: #222;
  }}
  header {{
    background: #2b2b2b;
    color: #f5f3ec;
    padding: 12px 22px;
    display: flex;
    align-items: center;
    gap: 16px;
    height: 50px;
  }}
  header h1 {{ margin: 0; font-size: 16px; font-weight: 700; }}
  header .subtitle {{ font-size: 12px; color: #aaa; }}
  header .filters {{ margin-left: auto; display: flex; gap: 8px; }}
  header .filters button {{
    background: #444; color: #ddd; border: 1px solid #555;
    padding: 5px 12px; font-size: 12px; cursor: pointer; border-radius: 4px;
  }}
  header .filters button.active {{
    background: #c4502e; color: #fff; border-color: #c4502e;
  }}

  #app {{
    display: grid;
    grid-template-columns: 260px 1fr;
    height: calc(100vh - 50px);
  }}

  aside {{
    background: #ece7d8;
    border-right: 1px solid #d6cfb8;
    overflow-y: auto;
  }}
  aside .group-label {{
    padding: 12px 16px 6px;
    font-size: 11px;
    font-weight: 700;
    color: #888;
    letter-spacing: 1px;
    text-transform: uppercase;
  }}
  aside ul {{ list-style: none; margin: 0; padding: 0; }}
  aside li {{
    padding: 7px 16px;
    cursor: pointer;
    font-size: 13px;
    border-left: 3px solid transparent;
  }}
  aside li:hover {{ background: #ddd6c0; }}
  aside li.active {{
    background: #fffaf0;
    border-left-color: #c4502e;
    font-weight: 600;
  }}
  aside li .meta {{
    display: block;
    font-size: 10.5px;
    color: #888;
    margin-top: 2px;
  }}
  aside li .badge {{
    display: inline-block;
    color: #fff;
    font-size: 9px;
    padding: 1px 5px;
    border-radius: 3px;
    margin-right: 5px;
    font-weight: 700;
    letter-spacing: 0.4px;
  }}
  aside li.ai .badge {{ background: #c4502e; }}
  aside li.human .badge {{ background: #3a8a7e; }}

  main {{
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }}

  .paper-header {{
    padding: 14px 22px 10px;
    background: #fffaf0;
    border-bottom: 1px solid #d6cfb8;
  }}
  .paper-header h2 {{ margin: 0 0 4px 0; font-size: 16px; }}
  .paper-header h2 .label-tag {{
    color: #999; font-size: 11px; font-weight: normal; margin-left: 8px;
  }}
  .paper-header .topic {{ color: #555; font-size: 12px; line-height: 1.4; }}
  .paper-header .anchor {{ margin-top: 4px; color: #888; font-size: 11px; }}
  .paper-header .anchor strong {{ color: #555; }}

  .split {{
    flex: 1;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1px;
    background: #d6cfb8;
    overflow: hidden;
  }}
  .pane {{
    background: #fdfcf6;
    overflow: auto;
    display: flex;
    flex-direction: column;
  }}
  .pane .pane-title {{
    padding: 6px 14px;
    font-size: 11px;
    font-weight: 700;
    color: #888;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    background: #f0ebd9;
    border-bottom: 1px solid #d6cfb8;
    flex-shrink: 0;
  }}
  .pane .pane-body {{
    flex: 1;
    overflow: auto;
    padding: 8px;
  }}
  .pane object, .pane embed, .pane iframe {{
    width: 100%;
    height: 100%;
    border: none;
    display: block;
  }}
  .pane .svg-host object {{
    width: 100%;
    height: auto;
    min-height: 100%;
  }}
  .pane .pdf-host {{
    width: 100%;
    height: 100%;
  }}
  .empty {{
    color: #999;
    font-style: italic;
    text-align: center;
    padding: 60px;
  }}
  .missing-pdf {{
    color: #c4502e;
    text-align: center;
    padding: 40px;
    font-size: 13px;
  }}
</style>
</head>
<body>

<header>
  <h1>Argument Graph Viewer</h1>
  <span class="subtitle">AI vs Human-Written Papers · n=40</span>
  <div class="filters">
    <button data-filter="all" class="active">All (40)</button>
    <button data-filter="ai">AI only (20)</button>
    <button data-filter="human">Human only (20)</button>
  </div>
</header>

<div id="app">
  <aside id="sidebar"></aside>
  <main id="main">
    <div class="empty">Select a paper from the left.</div>
  </main>
</div>

<script>
const PAPERS = {payload_json};
const sidebar = document.getElementById('sidebar');
const main = document.getElementById('main');
let currentFilter = 'all';
let currentFile = null;

function renderSidebar() {{
  sidebar.innerHTML = '';
  const groups = {{ ai: [], human: [] }};
  PAPERS.forEach(p => groups[p.label].push(p));
  for (const label of ['ai', 'human']) {{
    if (currentFilter !== 'all' && currentFilter !== label) continue;
    const labelText = label === 'ai' ? 'AI-Generated (FARS)' : 'Human-Written';
    sidebar.insertAdjacentHTML('beforeend',
      `<div class="group-label">${{labelText}} (${{groups[label].length}})</div>`);
    const ul = document.createElement('ul');
    for (const p of groups[label]) {{
      const li = document.createElement('li');
      li.className = label;
      if (p.file === currentFile) li.classList.add('active');
      li.innerHTML = `
        <span class="badge">${{label.toUpperCase()}}</span>${{p.paper_id}}
        <span class="meta">${{p.nodes}}n · ${{p.edges}}e</span>
      `;
      li.addEventListener('click', () => selectPaper(p));
      ul.appendChild(li);
    }}
    sidebar.appendChild(ul);
  }}
}}

function selectPaper(p) {{
  currentFile = p.file;
  document.querySelectorAll('aside li').forEach(li => li.classList.remove('active'));
  for (const li of sidebar.querySelectorAll('li')) {{
    if (li.textContent.includes(p.paper_id)) {{
      li.classList.add('active');
      break;
    }}
  }}
  renderMain(p);
}}

function renderMain(p) {{
  const anchorHtml = p.anchor_paper
    ? `<div class="anchor"><strong>Anchor paper:</strong> ${{escapeHtml(p.anchor_paper)}}</div>`
    : '';
  const pdfHtml = p.pdf_path
    ? `<div class="pdf-host"><object data="${{p.pdf_path}}#view=FitH" type="application/pdf">
        <p class="missing-pdf">Browser cannot display PDF inline.
        <a href="${{p.pdf_path}}" target="_blank">Open in new tab</a>.</p>
      </object></div>`
    : `<div class="missing-pdf">No PDF available for this paper.</div>`;
  main.innerHTML = `
    <div class="paper-header">
      <h2>${{p.paper_id}} <span class="label-tag">${{p.label}}</span></h2>
      <div class="topic">${{escapeHtml(p.topic)}}</div>
      ${{anchorHtml}}
    </div>
    <div class="split">
      <div class="pane">
        <div class="pane-title">Argument Graph</div>
        <div class="pane-body svg-host">
          <object type="image/svg+xml" data="${{p.svg_path}}"></object>
        </div>
      </div>
      <div class="pane">
        <div class="pane-title">Original PDF</div>
        <div class="pane-body" style="padding:0;">
          ${{pdfHtml}}
        </div>
      </div>
    </div>
  `;
}}

function escapeHtml(s) {{
  if (!s) return '';
  return String(s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}}

document.querySelectorAll('header .filters button').forEach(btn => {{
  btn.addEventListener('click', () => {{
    document.querySelectorAll('header .filters button').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentFilter = btn.dataset.filter;
    renderSidebar();
  }});
}});

renderSidebar();
if (PAPERS.length > 0) selectPaper(PAPERS[0]);
</script>
</body>
</html>
"""


def main():
    papers = load_papers()
    if not papers:
        print("No papers found.")
        return
    html = build_html(papers)
    out = os.path.join(HERE, "index.html")
    with open(out, "w") as f:
        f.write(html)
    n_pdf = sum(1 for p in papers if p["pdf_path"])
    print(f"Wrote {out}  ({len(papers)} papers, {n_pdf} with PDF)")


if __name__ == "__main__":
    main()
