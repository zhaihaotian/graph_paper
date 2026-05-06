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

A sentence usually = 1 claim. Split into 2 only if a semicolon or "but"/"yet" joins two independent clauses with different argumentative roles (e.g., one Prior_Work + one Limitation in the same sentence — see OS-BLIND N17 split).

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
| `Proof` | Pointer to in-paper supporting material that exists outside the prose: a Figure, Table, or Appendix reference. Use sparingly — only when the paper explicitly directs the reader to a non-prose artifact for support. | "as shown in Fig. 1", "see Appendix H", "Table 2 reports..." |
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
- Title: "Defenses against Emergent Misalignment". Para 1: "However, fine-tuning causes broad misalignment" → Context (the paper IS about EM, this sentence introduces EM)
- Title: "Safe Computer-Use Agents". Para 1: "However, agents can be misled to harmful actions" → Context (the paper IS about CUA harm, this sentence introduces CUA harm)
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

Add an `addresses` edge ONLY if both nodes share a distinctive technical term (not common words). Examples:
- N5b "依赖基于模板" + N6d "一对一人工设计(非模板)" → both reference "template" → addresses edge ✓
- N5a "忽视无意攻击场景" + N6a "每个任务以无害指令开始" → both reference "harmless/unintentional" → addresses edge ✓

**Optional `connective` field**: record the literal marker word ("However", "因此", "as shown in") so the renderer can label the edge.

**Pass 3 — Limitation source check (REQUIRED):** After Pass 1 + Pass 2, every `Limitation` node MUST have at least one incoming edge from `Prior_Work` or another `Limitation` (excluding `addresses` back-references which come from Method/Contribution). Rationale: a Limitation is by definition a critique of prior work, so its argumentative source must trace back to a Prior_Work node — either directly, or via a Limitation-cluster sub-claim chain whose head receives from Prior_Work.

For each Limitation `L`:
1. Compute `sources = {(s, k) : edge s→L exists, kind k ≠ addresses}`
2. Compute `source_types = {type(s) for (s, _) in sources}`
3. **If `source_types ∩ {Prior_Work, Limitation} == ∅`**, ACTION REQUIRED. Pick one:
   - **(a) Re-type L → Context.** If L's source sentence frames a field-level problem the paper itself studies (paper-theme alignment from Stage 2), and no specific named Prior_Work is being critiqued, then L is actually Context. Edges into and out of L stay valid (Context can take any incoming/outgoing kind).
   - **(b) Add a PW → L edge.** If a relevant Prior_Work node already exists upstream and L critiques it (lexical match between L's text and the PW's subject), add an edge `PW → L` with kind `contrast` (if L has a "However"-class marker referring to the PW's subject) or `elaboration`. The Pass 1 adjacency edge can stay alongside (e.g., a `Result → L elaboration` plus a `PW → L contrast` is fine — L just becomes a join node).
   - **(c) Split out a buried PW.** If L's verbatim text contains a description of a method (with citation) that's being critiqued (e.g., `"However, current methods like GRPO (Shao et al., 2024) treat X as Y, missing Z"`), split the sentence: extract the method-description clause as a new `Prior_Work` node `Lpw` (carry the citation count to it), shrink L's text to just the critique clause (cite count → 0), and re-wire `Lpw → L (elaboration)` plus the original incoming → Lpw.

**Reasoning hint for (b) — "However its …" patterns**: when a Limitation begins with "However, its / their / this method's …", the pronoun usually refers back to the most recent Prior_Work in the discourse, NOT to the immediately preceding sentence (which may be a Result of that PW). Pass 1 will incorrectly attribute the contrast marker to the adjacent Result; Pass 3 should re-route the contrast to the actual antecedent PW. Keep the adjacent edge as `elaboration` (no marker) and add the `PW → L (contrast, "However")` edge.

**Topology — DO NOT author these as edges, they are computed:**
- A node with `out_degree ≥ 2` is a `fork` node (renderer draws a dashed group box around its children, grouped by destination zone).
- A node with `in_degree ≥ 2` is a `join` node (renderer draws a dashed group box around its parents) — UNLESS any two parents have an ancestor-descendant relationship, in which case the renderer suppresses the box (it's not a true convergence, just a grandparent + descendant repeating).

**Side-enum rule — automatic, no JSON field needed:**
- A fork-parent whose same-zone children ALL have `out_degree == 0` (pure leaves with no downstream) gets its children rendered as small chips on the right side of the parent, in a mini dashed enumeration container — NOT in the main vertical spine.
- If even ONE same-zone child has any outgoing edge, ALL children stay in the main spine sub-row.
- This keeps quick "for example: A, B, C" enumerations off the main spine, while keeping structurally-load-bearing forks (like "two categories of prior work" → each connects to the limitation) on the spine.

**Per-zone fork labels (optional):** A parent with multiple destination zones can use `fork_labels: {Method: "...", Contribution: "..."}` to label each fork-group separately. Falls back to `fork_label` (single string) or `f"FORK from {id}"`.

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
  "observations": "3-5 short paragraphs — narrative arc, fork/join structure (auto-detected), anchor paper, notable features. NO SCORING."
}
```

Then render:

```bash
python3 render_graph.py FAxxxx.json
```

Renderer responsibilities (you don't think about these):
- Place each node in a fixed y-row by main type (Context → Prior_Work → Limitation → Proof → Method → Result → Contribution)
- Show only `display_label` + `id [type:subtype]` in the box; full `text` is in the SVG `<title>` tooltip
- Render `citations` as small dots (●) above the node
- Detect fork nodes (out_degree ≥ 2) and join nodes (in_degree ≥ 2), draw dashed group boxes around their children/parents with auto labels
- Edge color/style by `kind`

### Stage 5 — Self-validate

**REQUIRED: run BOTH validators before declaring done.**

```bash
python3 validate_graph.py FAxxxx.json
python3 coverage_check.py PAPER.pdf FAxxxx.json   # if source PDF available
```

`validate_graph.py` checks structural rules:
- All `type` values (main part before `:`) are canonical
- All `kind` values are canonical (5 only)
- Every node has non-empty `text`
- Every edge references existing node IDs
- Contribution outgoing edges: TWO kinds allowed:
  - `addresses` → Limitation (back-reference: this contribution resolves a named gap)
  - `elaboration` → another Contribution (main contribution unfolding into sub-claims; e.g., "Contribution 3: novel framework" → "3a: theorem statement" → "3b: numerical evidence" → "3c: implication"). When a paper has 4 main numbered contributions each with 2-3 sub-bullets, do NOT flatten into 14 siblings — wire sub-bullets as elaborations of their parent.
  All other outgoing kinds (contrast / consequence / evidence) from Contribution are forbidden.
- Reports `fork` and `join` node counts (informational, not errors)

`coverage_check.py` catches the **#1 source of extraction errors** — silently dropping source sentences. It re-extracts the intro from the PDF, splits into sentences, and checks each substantive sentence is represented by a node. Default threshold: 85% coverage required. **If it fails, you MUST add the missing sentences as nodes — this is non-negotiable.**

Compression-bug signatures the coverage check catches:
- Dense methodology paragraphs with multiple "we propose / we use / we sample / we optimize" verb-clauses → should be 4-6 nodes, often gets compressed into 1
- Worked examples with formulas → typically 2-4 sentences, often skipped entirely
- Parallel-structure paragraphs ("In X..., In Y...") → each clause should be its own node
- Long contribution-list paragraphs with embedded sub-claims

**Then run the manual self-audit below.** Most other errors come from these specific patterns — go down the list before declaring done.

#### Self-audit checklist (each = pass/fail)

**Type accuracy:**
- [ ] **Para-1 "However" check.** For each node currently typed `Limitation`: was its source sentence in paragraph 1, before any Prior_Work was introduced? If yes → it's almost certainly **Context** (field-level problem framing). Re-type. (See "Context vs Limitation" rules in Stage 2.)
- [ ] **Theme alignment check.** If the paper's title/abstract is about phenomenon X (e.g., a safety paper about safety risks), and a "However" sentence introduces phenomenon X → **Context** (it's the topic-of-study being framed).
- [ ] **Limitation has a target.** Each `Limitation` node should critique a specific named Prior_Work method or category. If you can't point to which Prior_Work it critiques, it might actually be Context.
- [ ] **Result vs Contribution.** Mid-intro experimental numbers/findings → `Result`. End-of-intro "Our contributions are:" bullet list → `Contribution`. For benchmark/dataset papers, "Findings" → `Contribution`; for method papers, "Findings" → `Result`.

**Edge accuracy (the marker test):**
- [ ] **`contrast` requires marker.** Is the marker actually in the source text near the start of B's sentence? Markers: However, Yet, But, Nevertheless, By contrast, Unlike, Instead, 然而, 但是, 反之, 而. If no marker → fall back to `elaboration`.
- [ ] **`consequence` requires marker.** Markers: Therefore, As a result, Hence, Consequently, This raises, To address this, To this end, Thus, motivates, 因此, 所以, 导致, 为此, 为了. If no marker → `elaboration`.
- [ ] **`evidence` direction and target.** Edge goes FROM the claim TO the supporting evidence node. Target must be `Result` or `Proof` (not Prior_Work, not Limitation). If target is wrong type → change to `elaboration` OR re-type the target node.
- [ ] **`addresses` lexical test.** Both source and target must share a **distinctive** technical term (e.g., "diversity collapse", "calibrated signal", "fixed bounds"). Common words ("training", "model", "method") don't count. If overlap is weak/generic → drop the edge.
- [ ] **`addresses` direction.** Method / Method-component / Contribution → Limitation. Never the other direction.

**Structural integrity:**
- [ ] **Contribution outgoing.** Every outgoing edge from a Contribution is either `addresses` → Limitation, or `elaboration` → another Contribution (sub-claim of the same numbered contribution). Any other outgoing kind is forbidden.
- [ ] **Sub-claim contributions.** If a paper lists numbered contributions where each has 2-3 bullet sub-claims, do NOT flatten them into one big row of siblings. Make the main contribution a parent, the sub-bullets children with `elaboration` edges from parent. (4 main × 3 sub ≠ 14 flat siblings.)
- [ ] **Contribution incoming.** Every Contribution node has at least one incoming edge (otherwise it's a floating root). Usually from the Method or Result that justifies it.
- [ ] **Limitation source.** Every Limitation has at least one incoming edge from `Prior_Work` or another `Limitation` (excluding `addresses` back-references). If incoming is only from Context/Result/Proof, apply the Pass 3 fix: re-type to Context, add a PW→L edge, or split out a buried PW (see Stage 3 Pass 3).
- [ ] **Verbatim text.** No `[bracketed paraphrase]` reconstructions in the `text` field. If the source was OCR-broken, use `…` ellipsis instead of inventing words.
- [ ] **Sentence coverage.** Roughly 1 node per source sentence (±2 for semicolon splits and sub-claim expansion). No invented sentences. No silently-dropped sentences (other than pure transition lines like "We organize the paper as follows.").
- [ ] **Citation counts.** Each node's `citations` integer matches the count of `(Author, Year)` or `[N]` references in that sentence's verbatim slice.

If any check fails, fix and re-render. Do NOT deliver until all pass.

## Common mistakes to avoid

These are the high-frequency error patterns observed across past reviews. Catching them upfront saves a review pass.

**Type mistakes:**
- **Para-1 "However" labeled as Limitation.** Reviewer caught ~25 instances. The first paragraph is field framing, NOT method critique. Re-read the "Context vs Limitation" subsection in Stage 2.
- **Conflating Prior_Work with Limitation.** Neutral description of a method = Prior_Work. Evaluative critique = Limitation. Don't merge them.
- **Result mid-intro labeled as Contribution.** A specific empirical finding inside the intro narrative is `Result`. The end-of-intro bulleted contribution list is `Contribution`.

**Edge mistakes:**
- **`contrast` / `consequence` without a marker.** If the source sentence has no marker word from the lookup tables, default to `elaboration`. Do NOT invent a "(implicit)" connective.
- **`evidence` pointing at Prior_Work or Limitation.** evidence target must be `Result` or `Proof`. Wrong target → change kind to `elaboration`, or re-type the target.
- **`evidence` direction reversed.** Claim → supporting evidence node, not the other way.
- **`addresses` with weak lexical overlap.** Both endpoints need a distinctive shared term, not a common word. If you have to squint to find the overlap, drop the edge.
- **Authoring retired kinds** (`fork`, `join`, `critique`, `motivates`, `back_reference`). All removed. Only the 5 canonical kinds are valid; fork/join are computed by topology.
- **Skipping an edge between adjacent claims.** Use `elaboration` as fallback rather than leaving them disconnected.

**Structural mistakes:**
- **Contribution with non-`addresses` outgoing edge.** Forbidden — validator will reject.
- **Floating Contribution.** Each Contribution needs at least one incoming edge from the Method/Result that produced it.
- **Merging sentences to reduce node count.** One sentence ≈ one node. Enumerations EXPAND to parent + lettered children.
- **Inventing or omitting sentences.** Coverage should match the source. No silent drops (except pure transitions like "We organize the paper as follows").

**Output mistakes:**
- **`[paraphrase reconstructions]` in verbatim text.** If OCR broke the source, use `…` ellipsis. Don't fill in guessed words.
- **Full sentence in `display_label`.** Keep it 4-10 words; the renderer shows the full text under the label.
- **Hand-writing SVG.** Never. Use `render_graph.py`.
- **Scoring in `observations`.** No "quality:" / "novelty:" / numeric ratings. Structure description only.

## Reference example

`EXAMPLE.json` and `EXAMPLE.svg` are a current v2 reference (FA0013 — RD-VLA Jacobian regularization). Study before producing your own. The example uses the 5-edge / 7-type schema and demonstrates fork topology, addresses edges, and side-enum chips.

## Full pipeline

```bash
# Per-paper extraction:

# 1. Extract intro
pdftotext PAPER.pdf - | sed -n '/^1\. Introduction/,/^2\./p' > intro.md

# 2. Produce FAxxxx.json (stages 1-3)

# 3. Render SVG
python3 render_graph.py FAxxxx.json

# 4. Validate (schema + Pass 3 Limitation source)
python3 validate_graph.py FAxxxx.json

# 5. Coverage check vs source PDF (≥85%)
python3 coverage_check.py PAPER.pdf FAxxxx.json
```

```bash
# Corpus-level analysis (after extracting many papers):

# Compute fingerprint metrics over ai/ + human/ folders
python3 compute_metrics.py ai/ human/ -o metrics.csv

# Plot 6-metric boxplot with p-values
python3 plot_metrics.py metrics.csv -o metrics_plots.png

# Train AI-vs-Human classifier (LR + RF, 5-fold CV)
python3 classify_papers.py metrics.csv
```

## 6 Core fingerprint metrics

After dropping low-signal/derivative metrics, 6 are kept (all p<0.001 on n=80):

| Bucket | Metric | What it measures |
|---|---|---|
| Structure | `sum_node_degree` | Σ in+out = 2×|edges| |
| Structure | `graph_longest_path` | DAG max-depth (DFS+memo, cycle-guard) |
| Prior_Work | `pw_node_count` | # of Prior_Work nodes (incl sub-claims) |
| Prior_Work (strongest) | `pw_total_cites` | Σ citations over PW nodes |
| Limitation (strongest) | `lim_scope_avg_cites` | per-paper PW-union critique surface (v3) |
| Method | `method_node_count` | # of Method nodes (incl components) |

`compute_metrics.py` outputs all of these (plus auxiliary stats) to a CSV.
`classify_papers.py` defaults to these 6 features.

## Files bundled with this skill

- `SKILL.md` — this file
- `render_graph.py` — deterministic SVG renderer (auto-computes fork/join, draws group boxes, citation dots)
- `validate_graph.py` — schema validator (5 edge kinds, 7 main types, Pass 3 Limitation source check, topology report)
- `coverage_check.py` — sentence-coverage validator vs source PDF (catches compression bugs)
- `compute_metrics.py` — corpus metrics computation (writes metrics.csv)
- `plot_metrics.py` — 6-metric boxplot with Mann-Whitney U p-values
- `classify_papers.py` — AI-vs-Human classifier (Logistic Regression + Random Forest, 5-fold CV)
- `EXAMPLE.json` / `EXAMPLE.svg` — legacy reference (old schema, kept for layout reference)
