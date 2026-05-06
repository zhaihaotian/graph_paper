# Argument-Graph Fingerprinting — Handover

## 1. Schema — the argument graph

Directed graph. Nodes = claims (one sentence ≈ one node). Edges = logical relations between claims.

### 1.1 Node types (7)

| Type | Definition | Example |
|---|---|---|
| **Context** | Field/problem framing. Includes "However X has issue Y" at the field level. | "LLMs undergo extensive alignment training" |
| **Prior_Work** | Neutral description of what a specific prior method did. Subject is a named system / cited paper. | "SafeLoRA projects LoRA updates to preserve safety directions (Hsu 2024)" |
| **Limitation** | Evaluative critique of a SPECIFIC named Prior_Work falling short. NOT a generic field-level "However" — those stay Context. | "However, SafeLoRA uses fixed parameters, suboptimal when EM risk varies" |
| **Method** | The paper's proposed method or component. | "We propose canary-controlled adaptive interleaving" |
| **Result** | This paper's experimental outcome / number / ablation. | "5.39% misalignment vs 7.15% baseline (25% reduction)" |
| **Proof** | Pointer to in-paper supporting material (Figure / Table / Appendix). | "as shown in Fig. 1 (bottom)" |
| **Contribution** | High-level claimed contribution. End-of-intro bullets. | "We introduce Abstain-Test benchmark" |

Subtypes are allowed via `Main: subtype` (e.g., `Method: component`, `Contribution: Finding 1`).

**Tie-breaker priority**: `Contribution > Method > Result > Limitation > Prior_Work > Context`.

### 1.2 Edge kinds (5 — strict whitelist)

| Kind | Meaning | Hard rule |
|---|---|---|
| **elaboration** | Specification / unpacking; default fallback. | Used when no marker matches. |
| **contrast** | A is positive/baseline, B reverses it. | Marker required: However / Yet / But / Nevertheless / By contrast / Unlike / Instead / 然而 / 但是 / 反之 / 而 |
| **consequence** | B is a causal/logical follow-up of A. | Marker required: Therefore / As a result / Hence / Consequently / Thus / This raises / To address this / To this end / motivates / 因此 / 所以 / 导致 / 为此 / 为了 |
| **evidence** | B is a Result / Proof supporting A. | Target type ∈ {Result, Proof}. |
| **addresses** | A Method/Contribution explicitly resolves a named Limitation. | Cross-segment + the two endpoints share a **distinctive** technical term ("diversity collapse", "calibrated signal"). Common words don't qualify. Direction: Method/Contribution → Limitation. |

**Retired kinds** (validator rejects): `fork`, `join`, `critique`, `motivates`, `back_reference`. `fork` and `join` are computed from topology (`out_degree ≥ 2` / `in_degree ≥ 2`); the renderer auto-draws dashed group boxes.

### 1.3 Special constraints

- **Contribution outgoing edges** are restricted to two kinds:
  - `addresses` → Limitation (back-reference to a stated gap)
  - `elaboration` → another Contribution (parent → sub-claim hierarchy; e.g., "Contribution 3" → "3a / 3b / 3c")
  - All other outgoing kinds from Contribution are forbidden.
- **Limitation incoming source** (Pass 3): every Limitation must have at least one incoming edge from a Prior_Work or another Limitation (excluding `addresses` back-references). Otherwise the node is most likely mis-typed Context, or a Prior_Work is buried inside the Limitation sentence and needs to be split out.
- **Side-enum chips** (auto, no JSON field): a fork-parent whose same-zone children are all leaves (out_degree = 0) with short labels (≤ 30 chars) and parent zone is not Contribution → renderer draws them as small chips beside the parent rather than full nodes. Keeps "for example: A, B, C" enumerations off the main spine.
- **Verbatim text required**: every node's `text` field must be a verbatim slice from the source intro. Use `…` ellipsis for OCR damage; never invent words or paraphrase.

---

## 2. The Claude Skill

The pipeline is bundled in this repo at `./skill/` so that anyone who clones the project gets the full toolchain. The same files are also mirrored at `~/.claude/skills/argument-graph-extractor/` so Claude Code recognises it as an installable skill — keep the two copies in sync (any change in one should be `cp -r`'d to the other).

Files (identical in both locations):

- `SKILL.md` — the rules below (read this first when extracting any paper)
- `EXAMPLE.json` + `EXAMPLE.svg` — canonical reference (FA0013, current v2 schema)
- `render_graph.py` — deterministic SVG renderer
- `validate_graph.py` — schema validator
- `coverage_check.py` — sentence-coverage validator vs source PDF (≥85% required)
- `compute_metrics.py` — corpus-level metric extraction → CSV
- `plot_metrics.py` — 6-metric boxplot with Mann-Whitney U p-values
- `classify_papers.py` — Logistic Regression + Random Forest classifier with 5-fold CV

All command examples below assume `cwd = argument_graphs_final/` (the repo root) and use `skill/`. If you've installed the skill globally and prefer to invoke it that way, swap `skill/` for `~/.claude/skills/argument-graph-extractor/`.

### 2.1 Per-paper extraction (single-paper workflow)

```bash
# 1. Extract intro from PDF
pdftotext -layout PAPER.pdf - | sed -n '/^1[. ]\+I[Nn][Tt]/,/^2[. ]/p' > intro.md

# 2. Build FAxxxx.json by following SKILL.md Stages 1–3 (sentence segmentation,
#    node typing, edge extraction with the two-pass + Pass-3 fix)

# 3. Schema validation
python3 skill/validate_graph.py FAxxxx.json

# 4. Sentence-coverage validation (≥85% required)
python3 skill/coverage_check.py PAPER.pdf FAxxxx.json

# 5. Render
python3 skill/render_graph.py FAxxxx.json
```

### 2.2 Corpus-level analysis (after many papers)

```bash
cd /Users/zhaihaotian/PycharmProjects/argument_graphs_final

# Compute fingerprint metrics over ai/ + human/
python3 skill/compute_metrics.py ai/ human/ -o metrics.csv

# 6-metric boxplot with p-values
python3 skill/plot_metrics.py metrics.csv -o metrics_plots.png

# AI-vs-Human classifier (LR + RF, 5-fold CV)
python3 skill/classify_papers.py metrics.csv

# Regenerate viewer site
python3 make_site.py
```

### 2.3 SKILL.md (verbatim, included for self-containedness)

> Below is the skill specification as currently shipped. Anything that contradicts this section in older notes is wrong — this is the authoritative version.

````markdown
---
name: argument-graph-extractor
description: Use this skill when the user wants to extract the argument structure of a research paper's introduction — i.e. parse the intro sentence-by-sentence into a typed graph (Context / Prior_Work / Limitation / Method / Result / Proof / Contribution) with logical edges between claims, and render it as an SVG visualization. Triggers include: "extract argument graph", "parse paper intro into claims", "visualize paper argument structure", "build a claim graph", "analyze the logical structure of this paper", "AI-paper fingerprint detection", "turn this intro into a graph". Produces a verifiable JSON + SVG + observations triple. Does NOT score papers or make quality judgments — only extracts structure.
---

# Argument Graph Extractor

Extract a paper introduction into a typed claim graph. Two layers:

1. **Edges** = local connection between adjacent claims, decided by a discourse marker (or `elaboration` as fallback).
2. **Topology** = `fork` / `join` are NOT edge labels; they are computed from the graph's `out_degree` / `in_degree`. The renderer auto-draws dashed grouping boxes around them.

## Hard constraints (do not violate)

1. **No scoring.** Never output numerical ratings, "quality: high/low", or "novelty: 3/5". Structure only.
2. **No LLM judgment-as-JSON.** Banned fields: `intellectual_move`, `novelty`, `anything_score`. You classify by lexical/discourse cues, not paper-level judgment.
3. **No hand-written SVG coordinates.** Layout is done by `render_graph.py`. Your job is the JSON.
4. **Verbatim node text.** Every `text` field must be a verbatim quote from the intro. `display_label` is a short label you write for the visible SVG box.
5. **Never author `fork` / `join` / `critique` / `motivates` / `back_reference` as edge kinds.** They were removed. Use the 5 canonical kinds below.

## Pipeline (5 stages)

### Stage 1 — Sentence segmentation

Read the intro. Split on `.` `?` `!` `。` `？` `！`. Ignore citation brackets `[1,2]` and decimals.

A sentence usually = 1 claim. Split into 2 only if a semicolon or "but"/"yet" joins two independent clauses with different argumentative roles (e.g., one Prior_Work + one Limitation in the same sentence).

**Sub-claim expansion**: when a single sentence enumerates parallel items (e.g., "harms include A, B, and C" or "two categories: X and Y"), you MAY split into a parent node + lettered children (`N4`, `N4a`, `N4b`) with `elaboration` edges from parent to each child. This makes `N4` a fork node by topology — no special type or edge kind needed.

### Stage 2 — Claim classification

Assign each claim exactly ONE main `type`. Optionally append a free-form `: subtype` (e.g., `Method: main`, `Method-component`, `Result: ablation`, `Contribution: Finding 1`).

| Main type | Definition | Cues |
|---|---|---|
| `Context` | Field/problem setting. Why the area matters. | "X has emerged as", "X is a critical", opening field-level statements |
| `Prior_Work` | What prior methods DID (neutral, not evaluative). Subject is a named method or cited paper. | Subject is a named system / cited paper; describes what it does |
| `Limitation` | Where prior work falls short, research gap, hypotheses under investigation. | "However", "fails to", "limited by", "remains unclear", "two limitations" |
| `Method` | The paper's proposed method, scheme, or component. | "We propose", "We introduce", "Our approach" |
| `Result` | This paper's experimental outcome / number / ablation / empirical finding. May simultaneously serve as `evidence` for an earlier claim. | Mid-intro numbers, "we observe", "ASR drops to X%", ablation results |
| `Proof` | Pointer to in-paper supporting material that exists outside the prose: a Figure, Table, or Appendix reference. Use sparingly. | "as shown in Fig. 1", "see Appendix H", "Table 2 reports..." |
| `Contribution` | High-level claimed contribution. For a benchmark/dataset paper, the "Findings" list belongs here (use subtype `Contribution: Finding 1`). | End-of-intro bullet list, "Our contributions are:" |

**Tie-breakers**:
- `Contribution > Method > Result > Limitation > Prior_Work > Context`
- For a benchmark paper, "Finding N" → Contribution. For a method paper, "Finding N" → Result.
- A sentence that both states a number AND advances a contribution → Contribution (the number is summary, not raw result).

**Prior_Work vs Limitation — key distinction**: Prior_Work describes WHAT a prior method does (neutral). Limitation describes WHY it is insufficient (evaluative). Do not conflate.

**Context vs Limitation — also critical**: A "However"/"concerning phenomenon"/"problem" sentence is NOT automatically a Limitation. Context can include problem-framing at the field level — sentences like "However, fine-tuning causes broad misalignment" or "However, agents can be misled to harmful actions" are still **Context** when they describe a problem with the field at large, not a critique of any specific named Prior_Work method. Limitation requires a target — a specific prior method/category being critiqued for falling short. Rule of thumb:
- "Field X has problem Y" (no named methods being critiqued yet) → **Context**
- "Method M (or category C of methods) fails on Y because Z" (specific Prior_Work being critiqued) → **Limitation**

In practice, the first paragraph of an intro is almost always entirely Context, even if it pivots on "However" — that pivot is field-level problem framing, not method critique. Limitation typically appears AFTER Prior_Work has been introduced, calling out specific shortcomings.

**Paper-theme alignment (strong signal)**: When the "However" in para 1 introduces the very phenomenon the paper itself is studying (e.g., a safety/security paper introducing the safety risk it will address; an alignment paper introducing the misalignment phenomenon it will defend against), that "However" is ALMOST CERTAINLY Context — it's the paper's topic-of-study being framed. Look at the paper's title/abstract: if the topic IS the problem named after "However", treat it as Context.

Examples:
- Title: "Defenses against Emergent Misalignment". Para 1: "However, fine-tuning causes broad misalignment" → Context (the paper IS about EM)
- Title: "Safe Computer-Use Agents". Para 1: "However, agents can be misled to harmful actions" → Context (the paper IS about CUA harm)
- Title: "Faster Sampling Algorithm". Para 1: "However, MCMC method M of Smith 2024 has variance V" → Limitation (specific method M being critiqued)

**Per-node fields**:
- `id` — `N1`, `N2`, ..., or hierarchical `N4`, `N4a`, `N4b` for parent + sub-claims
- `type` — main type, optionally `Main: subtype`
- `text` — verbatim quote (use the exact quoted slice if you split a sentence)
- `display_label` — 4-10 word short label you write
- `citations` — integer count of `[n]` brackets in the verbatim slice
- `anchor` — boolean, set true only if this Prior_Work is THE single anchor paper the whole method builds on

### Stage 3 — Edge extraction

Only 5 canonical `kind` values:

| `kind` | When to use | Required marker |
|---|---|---|
| `contrast` | A says positive/baseline, B reverses it | One of: However, Yet, But, Nevertheless, By contrast, Unlike, Instead, 然而, 但是, 反之, 而 |
| `consequence` | B is a causal/logical follow-up of A; or A's gap motivates B's method | Therefore, As a result, Hence, Consequently, This raises, To address this, To this end, Thus, motivates, 因此, 所以, 导致, 为此, 为了 |
| `evidence` | B is a Result / Proof / Figure-pointer that supports the claim A | Numbers, %, "as shown in Fig.", "Table N", "Appendix X", "we observe", experimental data |
| `addresses` | A Method (or Method-component) explicitly resolves a specific named Limitation. **Cross-segment** + lexical overlap required. | Both nodes share a distinctive term (e.g., both say "diversity collapse" or "calibrated signal") |
| `elaboration` | **Fallback.** No marker matches; B specifies / quantifies / unpacks A. | — |

**Two-pass edge extraction:**

**Pass 1 — adjacent-pair (sentence flow):** For each consecutive (A, B) pair in the intro:
```
if marker(B) ∈ contrast_markers: edge = contrast
elif marker(B) ∈ consequence_markers: edge = consequence
elif B is Result/Proof and explicitly supports A: edge = evidence
else: edge = elaboration
```
Always draw an edge between logically adjacent claims. No "skip if unsure" — default to `elaboration`.

**Pass 2 — cross-pair scan (long-distance back-references):** After Pass 1, scan ALL pairs (A, B) where A and B are not adjacent and not already connected, looking for `addresses` relationships. Focus on these zone combinations:
- **Method ↔ Limitation** (does this method component resolve a specific named limitation?)
- **Method-component ↔ Limitation** (each component may target one specific limitation)
- **Contribution ↔ Limitation** (does this claimed contribution explicitly answer a stated gap?)
- **Result ↔ Prior_Work** (does this result refute a prior claim?)

Add an `addresses` edge ONLY if both nodes share a distinctive technical term (not common words).

**Pass 3 — Limitation source check (REQUIRED):** After Pass 1 + Pass 2, every `Limitation` node MUST have at least one incoming edge from `Prior_Work` or another `Limitation` (excluding `addresses` back-references which come from Method/Contribution). Rationale: a Limitation is by definition a critique of prior work, so its argumentative source must trace back to a Prior_Work node — either directly, or via a Limitation-cluster sub-claim chain whose head receives from Prior_Work.

For each Limitation `L`:
1. Compute `sources = {(s, k) : edge s→L exists, kind k ≠ addresses}`
2. Compute `source_types = {type(s) for (s, _) in sources}`
3. **If `source_types ∩ {Prior_Work, Limitation} == ∅`**, ACTION REQUIRED. Pick one:
   - **(a) Re-type L → Context.** If L's source sentence frames a field-level problem the paper itself studies, and no specific named Prior_Work is being critiqued, then L is actually Context. Edges into and out of L stay valid.
   - **(b) Add a PW → L edge.** If a relevant Prior_Work node already exists upstream and L critiques it (lexical match), add an edge `PW → L` with kind `contrast` (if L has a "However" marker referring to the PW's subject) or `elaboration`.
   - **(c) Split out a buried PW.** If L's verbatim text contains a description of a method (with citation) that's being critiqued, split the sentence: extract the method-description clause as a new `Prior_Work` node, shrink L's text to just the critique clause.

**Reasoning hint for (b)**: when a Limitation begins with "However, its / their / this method's …", the pronoun usually refers back to the most recent Prior_Work in the discourse, NOT to the immediately preceding sentence (which may be a Result of that PW). Pass 1 will incorrectly attribute the contrast marker to the adjacent Result; Pass 3 should re-route.

**Topology — DO NOT author these as edges, they are computed:**
- A node with `out_degree ≥ 2` is a `fork` node (renderer draws a dashed group box around its children, grouped by destination zone).
- A node with `in_degree ≥ 2` is a `join` node (renderer draws a dashed group box around its parents) — UNLESS any two parents have an ancestor-descendant relationship, in which case the renderer suppresses the box.

**Side-enum rule — automatic, no JSON field needed:**
- A fork-parent whose same-zone children ALL have `out_degree == 0` (pure leaves) gets its children rendered as small chips on the right side of the parent, in a mini dashed enumeration container.
- If even ONE same-zone child has any outgoing edge, ALL children stay in the main spine sub-row.

### Stage 4 — Render to SVG

Write JSON to `FAxxxx.json`:

```json
{
  "paper_id": "FAxxxx",
  "paper_topic": "short description",
  "anchor_paper": "name or null",
  "nodes": [
    {"id": "N1", "type": "Context", "text": "verbatim quote",
     "display_label": "short label", "citations": 2},
    {"id": "N4", "type": "Prior_Work", "text": "...",
     "display_label": "two categories of prior eval", "citations": 0},
    {"id": "N4a", "type": "Prior_Work: category-1", "text": "...",
     "display_label": "explicit misuse", "citations": 3},
    {"id": "N5a", "type": "Limitation", "text": "...",
     "display_label": "ignores unintentional cases", "citations": 0},
    {"id": "P5a", "type": "Proof", "text": "As shown in Fig. 1 (bottom)...",
     "display_label": "Fig. 1: ASR drops on rewrite", "citations": 0}
  ],
  "edges": [
    {"from": "N2", "to": "N3", "kind": "contrast", "connective": "however"},
    {"from": "N4", "to": "N4a", "kind": "elaboration"},
    {"from": "N4", "to": "N4b", "kind": "elaboration"},
    {"from": "P5a", "to": "N5a", "kind": "evidence"},
    {"from": "N18", "to": "N22", "kind": "addresses"}
  ],
  "observations": "3-5 short paragraphs — narrative arc, fork/join structure, anchor paper, notable features. NO SCORING."
}
```

Then render: `python3 render_graph.py FAxxxx.json`.

### Stage 5 — Self-validate

**REQUIRED: run BOTH validators before declaring done.**

```bash
python3 validate_graph.py FAxxxx.json
python3 coverage_check.py PAPER.pdf FAxxxx.json   # if source PDF available
```

`validate_graph.py` checks: type / kind whitelists, node-id references, Contribution outgoing rules, Pass 3 Limitation-source rule. Reports fork/join counts.

`coverage_check.py` catches the **#1 source of extraction errors** — silently dropping source sentences. Default threshold: **85% coverage required**. If it fails, you MUST add the missing sentences as nodes.

Compression-bug signatures the coverage check catches:
- Dense methodology paragraphs with multiple "we propose / we use / we sample / we optimize" verb-clauses → should be 4-6 nodes, often gets compressed into 1
- Worked examples with formulas → typically 2-4 sentences, often skipped entirely
- Parallel-structure paragraphs ("In X..., In Y...") → each clause should be its own node

#### Self-audit checklist (each = pass/fail)

**Type accuracy:**
- [ ] **Para-1 "However" check.** For each `Limitation`: was its source sentence in para 1, before any Prior_Work was introduced? If yes → almost certainly **Context**.
- [ ] **Theme alignment check.** If the paper's title/abstract is about phenomenon X, and a "However" sentence introduces phenomenon X → **Context**.
- [ ] **Limitation has a target.** Each `Limitation` node should critique a specific named Prior_Work method or category.
- [ ] **Result vs Contribution.** Mid-intro numbers → `Result`. End-of-intro bullet list → `Contribution`.

**Edge accuracy (the marker test):**
- [ ] **`contrast` requires marker.** If no marker → fall back to `elaboration`.
- [ ] **`consequence` requires marker.**
- [ ] **`evidence` direction and target.** Edge goes FROM the claim TO the supporting evidence node. Target must be `Result` or `Proof`.
- [ ] **`addresses` lexical test.** Both endpoints must share a **distinctive** technical term. Common words don't count.
- [ ] **`addresses` direction.** Method / Method-component / Contribution → Limitation. Never reversed.

**Structural integrity:**
- [ ] **Contribution outgoing.** Only `addresses` → Limitation, or `elaboration` → another Contribution.
- [ ] **Sub-claim contributions.** 4 main × 3 sub ≠ 14 flat siblings — wire sub-bullets as elaborations of their parent.
- [ ] **Contribution incoming.** Every Contribution has at least one incoming edge.
- [ ] **Limitation source.** Every Limitation has incoming from Prior_Work or another Limitation.
- [ ] **Verbatim text.** No `[bracketed paraphrase]`. Use `…` for OCR damage.
- [ ] **Sentence coverage.** Roughly 1 node per source sentence (±2 for splits/sub-claims). No invented or silently-dropped sentences.
- [ ] **Citation counts.** Each node's `citations` integer matches the count of references in its verbatim slice.

If any check fails, fix and re-render. Do NOT deliver until all pass.
````

(End of embedded SKILL.md.)

---

## 3. Data corpus

```
argument_graphs_final/
├── ai/                          ← 40 AI-generated paper graphs (FA series; JSON + SVG each)
├── human/                       ← 40 human-written paper graphs (anchor / ICLR Oral / ICLR Poster)
├── pdfs/
│   ├── ai/                      ← 40 source PDFs
│   └── human/                   ← 40 source PDFs
├── intros/                      ← extracted intro text (per paper)
├── skill/                       ← bundled extraction toolchain (mirrors ~/.claude/skills/argument-graph-extractor/)
│   ├── SKILL.md
│   ├── EXAMPLE.json + EXAMPLE.svg
│   ├── render_graph.py
│   ├── validate_graph.py
│   ├── coverage_check.py
│   ├── compute_metrics.py
│   ├── plot_metrics.py
│   └── classify_papers.py
├── metrics.csv                  ← per-paper feature table (80 rows × ~37 columns)
├── metrics_plots.png            ← 6-metric boxplot figure
├── make_site.py                 ← regenerates index.html from ai/ + human/ + pdfs/
├── index.html                   ← single-page viewer (auto-generated)
├── README.md
└── HANDOVER.md                  ← this file
```

### Source PDFs (for re-extraction / coverage check)

- **AI papers (FA series)**:
  - `selected_15` PDFs: `~/PycharmProjects/analemma_fars_papers/manual_review_workspace_2026-03-25/selected_15_pdfs/`
  - 25 additional FA PDFs: `~/PycharmProjects/analemma_fars_papers/rag_novelty_workspace_2026-03-19/fars_30_sample/original_en/`

- **Anchor PDFs** (real papers cited as anchor by FA series):
  - `~/PycharmProjects/analemma_fars_papers/manual_review_workspace_2026-03-25/section_extractions/FA####_*/##_<title>_<arxiv-id>.pdf`

- **ICLR 2025 Oral PDFs**:
  - `~/PycharmProjects/analemma_fars_papers/rag_novelty_workspace_2026-03-19/iclr_oral_9_papers/original_en/`

- **ICLR 2025 Poster PDFs**:
  - `~/PycharmProjects/analemma_fars_papers/rag_novelty_workspace_2026-03-19/iclr25_30_sample/`

### Static viewer

```bash
cd /Users/zhaihaotian/PycharmProjects/argument_graphs_final
python3 -m http.server 8765   # http://localhost:8765/index.html
```

Layout: filter buttons (All / AI / Human), sidebar with paper list + node/edge counts, main pane with split SVG/PDF view.

To redeploy after edits:

```bash
python3 make_site.py
git add -A && git commit -m "..." && git push
# GitHub Pages auto-rebuilds in ~1 minute
```

---

## 4. The 6 fingerprint metrics

Computed by `compute_metrics.py`. All p<0.001 on n=80 (Mann-Whitney U two-tailed).

| Bucket | Metric | What it measures | AI mean | Human mean | Ratio | p-value |
|---|---|---|---:|---:|---:|---:|
| **Structure** | `sum_node_degree` | Σ in+out = 2·\|edges\| | 36.05 | 59.95 | 1.66× | 9e-11 |
| **Structure** | `graph_longest_path` | DAG max-depth (DFS+memo, cycle-guard) | 13.68 | 23.95 | 1.75× | 2e-12 |
| **Prior_Work** | `pw_node_count` | # Prior_Work nodes (incl sub-claims) | 2.30 | 4.38 | 1.90× | 2e-04 |
| **Prior_Work** | `pw_total_cites` ⭐ | Σ citations over PW nodes (strongest) | 2.15 | 7.42 | 3.45× | 4e-09 |
| **Limitation** | `lim_scope_avg_cites` ⭐ | per-paper PW-union critique surface | 1.73 | 4.65 | 2.70× | 3e-07 |
| **Method** | `method_node_count` | # Method nodes (incl components) | 3.42 | 7.33 | 2.14× | 2e-05 |

Strongest signals (in order): `pw_total_cites` (3.45×), `lim_scope_avg_cites` (2.70×), `method_node_count` (2.14×), `pw_node_count` (1.90×), `graph_longest_path` (1.75×), `sum_node_degree` (1.66×).

---

## 5. Classifier results

A simple linear model on the 6 metrics, 5-fold CV (64 train / 16 test per fold):

|              | Predicted AI | Predicted Human |
|--------------|-------------:|----------------:|
| **Actual AI**    | 37 (TN)      | 3 (FP)          |
| **Actual Human** | 6 (FN)       | 34 (TP)         |

- **Accuracy**: 71/80 = **88.7%**
- **False positives** (AI mistaken for human): 3 — small.
- **False negatives** (human mistaken for AI): 6 — most of the model's errors. Some human papers, especially short/template-like Posters, do look structurally AI-like.

This says the 6 metrics are a **structural signal** rather than a perfect classifier — useful as a fingerprint, not a verdict.

---

## 6. Known limitations of the approach

1. **Pipeline is non-deterministic.** Graph construction is LLM-driven (an agent following SKILL.md). Re-running the same paper twice can yield slightly different graphs — node count, edge attributions, sub-claim splits. We have not measured re-extraction stability.
2. **Taxonomy is hand-defined.** The 7 node types and 5 edge kinds are author-defined. They were tuned on FARS + ICLR ML papers and may not generalise to other CS sub-fields, let alone other disciplines.
3. **Skill is tuned on Intros only.** Body and Discussion sections are unanalyzed. A method-section graph might capture different signals (algorithm flow, equation dependencies); not built yet.

---

## 7. Open future work

1. **Regression to review scores.** Use the 6 graph-based metrics to regress / predict the average review score.
2. **Compare against existing AI detectors as a baseline.**
3. **Make graph construction more deterministic.**

---

## 8. Onboarding — how to continue

### Extract a new paper

1. Read `skill/SKILL.md` IN FULL (don't skim — the audit checklist matters).
2. Read `skill/EXAMPLE.json` to see the v2 schema.
3. Extract intro: `pdftotext -layout PAPER.pdf - | sed -n '/^1[. ]\+I[Nn][Tt]/,/^2[. ]/p'`
4. Build JSON following Stages 1–3.
5. Run `skill/validate_graph.py` and `skill/coverage_check.py` (≥85%) before declaring done.
6. Render: `python3 skill/render_graph.py FAxxxx.json`.

### Recompute metrics after JSON edits

```bash
cd /Users/zhaihaotian/PycharmProjects/argument_graphs_final
python3 skill/compute_metrics.py ai/ human/ -o metrics.csv
python3 skill/plot_metrics.py metrics.csv -o metrics_plots.png
python3 skill/classify_papers.py metrics.csv
```

### Inspect a single paper's graph

```bash
python3 -c "
import json
with open('ai/FA0001.json') as f: d = json.load(f)
for n in d['nodes']:
    print(n['id'], n['type'], n.get('display_label',''), 'cites=', n.get('citations',0))
"
```

### Redo many graphs in parallel

Don't do it in one agent. Spawn 3–6 parallel general-purpose subagents (Opus) with 5–7 papers each:
1. Each must read `SKILL.md` in full.
2. Each extracts, validates, renders, reports.
3. Then spawn 3–4 reviewer subagents (also reading SKILL.md) to check each other's output.
4. Final pass for any specific issues.

### Update the deployed site

```bash
cd /Users/zhaihaotian/PycharmProjects/argument_graphs_final
python3 make_site.py
git add -A
git commit -m "..."
git push   # GitHub Pages auto-rebuilds in ~1 minute
```

