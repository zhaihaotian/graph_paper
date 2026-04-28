# Project Handoff — Argument-Graph Fingerprinting of AI vs Human Papers

**Date**: 2026-04-27
**Status**: Phase 1 complete (corpus + tool + metrics + report). Ready for analysis extension.

---

## 1. Project Goal

Detect AI-generated academic papers via the **structural fingerprint of their introduction**, not via text-level cues. Concretely:

1. Parse each paper's Introduction into a typed argument graph (claims = nodes, logical relations = edges).
2. Compute graph-theoretic metrics on each.
3. Compare AI-generated vs human-written papers.

The corpus is FARS (suspected-AI papers from arXiv 2024–2026 cs.* submissions) + ICLR 2025 oral papers (human).

---

## 2. Data Corpus

**Location**: `/Users/zhaihaotian/PycharmProjects/argument_graphs_final/`

```
argument_graphs_final/
├── ai/                          ← 20 AI-generated paper graphs
│   ├── FA0001.json + FA0001.svg
│   ├── FA0005.json + .svg
│   ├── FA0006.json + .svg
│   ├── FA0007.json + .svg
│   ├── FA0008.json + .svg
│   ├── FA0011.json + .svg
│   ├── FA0012.json + .svg
│   ├── FA0013.json + .svg
│   ├── FA0018.json + .svg
│   ├── FA0021.json + .svg
│   ├── FA0022.json + .svg
│   ├── FA0025.json + .svg
│   ├── FA0027.json + .svg
│   ├── FA0028.json + .svg
│   ├── FA0032.json + .svg
│   ├── FA0034.json + .svg
│   ├── FA0035.json + .svg
│   ├── FA0038.json + .svg
│   ├── FA0041.json + .svg
│   └── FA0047.json + .svg
├── human/                       ← 20 human-written paper graphs
│   ├── FA0001_anchor.json + .svg
│   ├── FA0006_anchor.json + .svg
│   ├── FA0008_anchor.json + .svg
│   ├── FA0011_anchor.json + .svg
│   ├── FA0012_anchor.json + .svg
│   ├── FA0013_anchor.json + .svg
│   ├── FA0018_anchor.json + .svg
│   ├── FA0021_anchor.json + .svg
│   ├── FA0022_anchor.json + .svg
│   ├── FA0032_anchor.json + .svg
│   ├── FA0034_anchor.json + .svg
│   ├── ICLR_AttentionHeads.json + .svg
│   ├── ICLR_BIRD.json + .svg
│   ├── ICLR_Backtracking.json + .svg
│   ├── ICLR_InferenceScaling.json + .svg
│   ├── ICLR_InfluenceFunctions.json + .svg
│   ├── ICLR_KAN.json + .svg
│   ├── ICLR_LinearRNN.json + .svg
│   ├── ICLR_NeuralODE.json + .svg
│   └── ICLR_WizardMath.json + .svg
├── metrics.csv                  ← per-paper full metric table (40 rows × ~37 columns)
├── REPORT.md                    ← finalized report (Chinese narrative + 10 metrics)
└── HANDOFF.md                   ← this file
```

### Source PDFs (for re-extraction / coverage check)

- **AI papers (FA series)**:
  - `selected_15` PDFs: `/Users/zhaihaotian/PycharmProjects/analemma_fars_papers/manual_review_workspace_2026-03-25/selected_15_pdfs/`
  - 5 additional FA PDFs (FA0005/35/38/41/47): `/Users/zhaihaotian/PycharmProjects/analemma_fars_papers/rag_novelty_workspace_2026-03-19/fars_30_sample/original_en/`

- **Anchor PDFs** (real papers cited as anchor by FA series):
  - `/Users/zhaihaotian/PycharmProjects/analemma_fars_papers/manual_review_workspace_2026-03-25/section_extractions/FA####_*/##_<title>_<arxiv-id>.pdf`
  - One subdirectory per FA paper; the anchor PDF has a numeric prefix (e.g., `01_in_training_defenses_against_emergent_misalignment_2508.06249.pdf`) while the AI paper itself uses the FA####_<uuid>.pdf naming.

- **ICLR Oral PDFs**:
  - `/Users/zhaihaotian/PycharmProjects/analemma_fars_papers/rag_novelty_workspace_2026-03-19/iclr_oral_9_papers/original_en/`

### Selected 15 PDFs source list

```
FA0001 FA0006 FA0007 FA0008 FA0011 FA0012 FA0013 FA0018 FA0021 FA0022
FA0025 FA0027 FA0028 FA0032 FA0034
```

(All 15 in `selected_15_pdfs/`. The 5 round-2 additions FA0005/35/38/41/47 are from the larger `fars_30_sample/`.)

### Anchor markdown intros (DO NOT USE — broken OCR)

`/Users/zhaihaotian/PycharmProjects/analemma_fars_papers/manual_review_workspace_2026-03-25/ai_fingerprint_analysis/anchor_intros_fixed/FA####_ANCHOR_intro_FIXED.md`

These are pre-extracted but **OCR is broken** (column wrapping mangled, sentences truncated). All anchor paper graphs were re-extracted from the source PDFs, NOT from these markdowns. Avoid using these.

---

## 3. The Skill (Pipeline Tool)

**Location**: `/Users/zhaihaotian/.claude/skills/argument-graph-extractor/`

```
argument-graph-extractor/
├── SKILL.md                ← spec for the extraction pipeline (READ FIRST)
├── EXAMPLE.json + .svg     ← canonical reference (FA0013, current v2 schema)
├── render_graph.py         ← deterministic SVG renderer
├── validate_graph.py       ← schema validator (type/kind/Contribution rules)
├── coverage_check.py       ← sentence-coverage hard validator (PDF vs JSON)
└── compute_metrics.py      ← per-paper metric extraction → CSV
```

### Workflow per paper

```bash
# 1. Extract intro from PDF
pdftotext -layout PAPER.pdf - | sed -n '/^1[. ]\+I[Nn][Tt]/,/^2[. ]/p'

# 2. Build JSON manually or via subagent following SKILL.md (Stages 1-3)

# 3. Validate schema
python3 /Users/zhaihaotian/.claude/skills/argument-graph-extractor/validate_graph.py FAxxxx.json

# 4. Validate sentence coverage (≥85% required)
python3 /Users/zhaihaotian/.claude/skills/argument-graph-extractor/coverage_check.py PAPER.pdf FAxxxx.json

# 5. Render SVG
python3 /Users/zhaihaotian/.claude/skills/argument-graph-extractor/render_graph.py FAxxxx.json

# 6. (After many graphs) compute corpus metrics
python3 /Users/zhaihaotian/.claude/skills/argument-graph-extractor/compute_metrics.py ai/ human/ -o metrics.csv
```

---

## 4. Schema (v2)

### 4.1 Node types (7)

| Type | Definition |
|---|---|
| **Context** | Field/problem framing. Includes "However X has issue Y" at the field level. |
| **Prior_Work** | Neutral description of what a specific prior method did. Subject is a named system/cited paper. |
| **Limitation** | Evaluative critique of a SPECIFIC named Prior_Work falling short. (Critical: NOT a generic field-level "However" — those stay Context.) |
| **Method** | The paper's proposed method or component. |
| **Result** | This paper's experimental outcome / number / ablation. |
| **Proof** | Pointer to in-paper supporting material (Figure, Table, Appendix). |
| **Contribution** | High-level claimed contribution. For benchmark/dataset papers, "Findings" → Contribution; for method papers, "Findings" → Result. |

**Subtypes** allowed via `Main: subtype` syntax (e.g., `Method: component`, `Contribution: Finding 1`, `Proof: experimental`).

### 4.2 Edge types (5 — strict whitelist)

| Kind | Required marker / condition |
|---|---|
| **elaboration** | (default fallback when no marker matches) |
| **contrast** | Marker required: However / Yet / But / Nevertheless / By contrast / Unlike / Instead / 然而 / 但是 / 反之 |
| **consequence** | Marker required: Therefore / As a result / Hence / Consequently / Thus / To address this / To this end / 因此 / 所以 / 为此 / 为了 |
| **evidence** | Target type must be `Result` or `Proof` |
| **addresses** | Cross-segment + both endpoints share a distinctive technical term (e.g., "diversity collapse", "calibrated signal"). Common words don't count. Direction: Method/Contribution → Limitation. |

**Retired edge kinds** (validator will reject): fork, join, critique, motivates, back_reference. Use the 5 above only.

### 4.3 Topology (computed, not authored)

- `fork` node: out_degree ≥ 2
- `join` node: in_degree ≥ 2

The renderer auto-detects and draws dashed grouping rectangles. JOIN boxes are suppressed when any two parents have an ancestor-descendant relationship (avoids "grandparent + descendant" repetition noise).

### 4.4 Special rules

- **Contribution outgoing edges**: ONLY two kinds allowed
  - `addresses` → Limitation (back-reference)
  - `elaboration` → another Contribution (parent → sub-claim hierarchy; e.g., "Contribution 3" → "3a/3b/3c")
  - All other outgoing kinds from Contribution are forbidden by validator.

- **Side-enum chip rendering**: A fork-parent's same-zone children that are ALL leaves (out_degree=0) AND have short display_labels (≤30 chars) AND parent zone is not Contribution → rendered as small chips on the right side of parent (not as full nodes below). Used for Context-level "harms include A, B, C" enumerations.

- **Sub-claim expansion**: When a single sentence enumerates parallel items, you MAY split into a parent node + lettered children (e.g., N4, N4a, N4b) connected by elaboration edges.

---

## 5. Critical Audit Rules (lessons learned the hard way)

These came from many rounds of reviewer-caught errors. Subagents will compress / mis-classify without them.

### 5.1 Context vs Limitation in para-1

**Most common bug**: Para-1 sentences with "However" labeled as Limitation when they should be Context.

Rule: A Limitation requires a TARGET — a specific Prior_Work being critiqued. If the "However" appears before any Prior_Work has been introduced, and it's framing a field-level problem (e.g., "However, current LLMs hallucinate"), it's Context.

**Theme alignment heuristic**: If the paper's title/abstract is about phenomenon X (e.g., a safety paper about safety risks), and a "However" sentence introduces X → it's the topic-of-study being framed → Context.

### 5.2 Sentence coverage (the BIRD failure)

**Bug**: Subagents compress dense methodology paragraphs (multiple "we propose / we use / we sample" verb-clauses) into one summary node, dropping 5-10 sentences.

The BIRD paper had Para 3 entirely skipped (10 methodology sentences with abduction/deduction, sampling+optimization, ∑ formula). Same compression bug found in:
- ICLR_KAN (worked example with formula)
- ICLR_InferenceScaling (DRAG/IterDRAG parallel paragraphs)
- ICLR_InfluenceFunctions (GGN design choice)

**Fix**: Run `coverage_check.py PAPER.pdf graph.json` — it diffs source sentences vs node texts. Threshold 85%. Fail = MUST add missing nodes.

### 5.3 Edge kind marker discipline

- `contrast` requires real marker word in B's first ~10 chars. No marker → `elaboration` (don't invent "(implicit)" connectives).
- `consequence` same rule.
- `evidence` target must be Result or Proof, not Prior_Work or Limitation. Wrong type → re-type or change to elaboration.
- `addresses` requires distinctive shared term (NOT generic words like "training", "model").

### 5.4 OCR-broken anchor markdowns

The `anchor_intros_fixed/*.md` files have column-wrap OCR damage. ALL anchor papers were re-extracted from source PDFs in the most recent round. If revisiting, use PDFs not markdowns.

---

## 6. Final Metric Set (10 metrics, in REPORT.md)

Computed by `compute_metrics.py`, exported to `metrics.csv` (full ~37 columns) and summarized in `REPORT.md` (10 chosen metrics).

| Group | Metric | AI mean | Human mean | Ratio |
|---|---|---|---|---|
| A. Structure | sum_node_degree (Σ in+out = 2|E|) | 34.2 | 60.8 | 1.78× |
| A. Structure | graph_longest_path | 12.55 | 23.95 | 1.91× |
| A. Structure | max_width (top-level zone width) | 3.15 | 3.80 | 1.21× |
| B. Prior_Work | pw_node_count | 2.15 | 4.35 | 2.02× |
| B. Prior_Work | pw_top_level_count | 1.20 | 1.65 | 1.38× |
| B. Prior_Work | pw_avg_cites | 0.89 | 1.73 | 1.94× |
| B. Prior_Work | **pw_total_cites** | **2.05** | **7.25** | **3.54×** |
| C. Limitation | lim_scope_avg_cites (reverse-BFS to nearest cited PW) | 1.12 | 2.30 | 2.04× |
| D. Method | method_node_count | 3.15 | 8.35 | 2.65× |
| D. Method | method_pw_reach_avg (reverse-BFS, distinct PW reached) | 1.95 | 3.17 | 1.62× |

Each metric's full definition + algorithm + interpretation is in `REPORT.md` §4.

**Strongest signals**: pw_total_cites (3.54×), method_node_count (2.65×), lim_scope_avg_cites (2.04×), pw_node_count (2.02×), graph_longest_path (1.91×).

---

## 7. Design Decisions Made

These are choices that affect interpretation and are worth knowing:

1. **`anchor_cite_share` was REMOVED** from the report — `anchor` was a manual LLM flag with inconsistent assignment across papers (some had `anchor_paper` metadata but no node flagged, vice versa). The user judged it too unreliable.

2. **`max_width` was redefined twice**:
   - Originally: max nodes per type-zone (raw)
   - Now: max **top-level** nodes per type-zone (excluding sub-claims that have a same-zone parent), so e.g., a Contribution row with "4 main + 10 sub-claims" reports width=4 not 14.

3. **Contribution hierarchy was added**: We allowed Contribution → Contribution `elaboration` edges (for parent → sub-claim hierarchy). Initially Contribution outgoing was banned entirely; relaxed in two stages.

4. **Limitation scope (C1) used relaxed BFS**: User's strict definition ("Limitation with in_degree=1 AND parent is Prior_Work") yielded only 0.15 samples per paper. Relaxed to "any Limitation, reverse BFS, find nearest cited PW ancestor" — 2-4 samples per paper, signal preserved.

5. **`avg_node_degree` → `sum_node_degree`**: User wanted total, not average. Equivalent to 2 × |edges|.

6. **Side-enum chips rule**: Only fires for Context-zone leaf children with short labels. Originally fired for any zone, made Contribution sub-claims look tiny — fixed.

7. **Edge legend was added** to SVG renderer (top-right corner) so colors are decodable without external reference.

---

## 8. Common Pitfalls for Future Work

If you're going to extend the corpus or refine metrics:

- **Subagent compression bias**: When extracting new graphs, ALWAYS run `coverage_check.py` before declaring done. Subagents naturally collapse 8-10-sentence methodology paragraphs into 1 node.

- **Para-1 "However" is NOT Limitation**: Even if it sounds critical. If no Prior_Work has been introduced yet, it's Context (problem framing).

- **`addresses` edges are easy to fake**: Require distinctive shared term. "training" / "model" / "method" don't count. If you have to squint, drop the edge.

- **Anchor flag is unreliable**: Don't compute metrics that depend on it. Use citation-distribution proxies instead.

- **Sub-claims should be hierarchical, not flat**: NeuralODE was extracted as 14 flat Contribution siblings; corrected to 4 main + 10 sub-claims with elaboration edges.

- **OCR for two-column papers**: Use `pdftotext -layout` first, then fall back to no-layout. Some papers (DeepSeekMath) are single-column and parse cleanly without `-layout`.

---

## 9. Possible Next Steps (open questions)

1. **Statistical significance**: Run t-tests / Mann-Whitney U on the 10 metrics across AI vs Human (n=20 each). Currently only means + ratios reported; no p-values.

2. **Per-paper outlier analysis**: Some AI papers may look human-like, vice versa. Look at `metrics.csv` per-row to find borderline cases.

3. **Composite classifier**: Train a logistic regression / random forest on the 10 metrics → predict AI vs Human. Report AUC.

4. **Expand corpus**: 20+20=40 is small. Could go to 50+50 with more FA papers and more ICLR/NeurIPS papers.

5. **Method-section graph (separate skill)**: Current skill only extracts Introduction. A `method-graph-extractor` for Section 3 might capture different signals (algorithm flow, equation dependencies).

6. **Cross-validate the skill**: Have the skill regenerate one paper's graph multiple times and check consistency (currently no reproducibility study).

7. **MARKERS.json data file**: The user originally declined this, but if subagent-marker-judgment proves error-prone, externalize the marker lookup tables into a separate JSON file.

8. **Per-cluster analysis**: Among the human papers, "anchor papers" (real papers cited by FA series) and "ICLR Oral" might have different structural signatures. Worth splitting human into two sub-classes.

---

## 10. How to Continue (template for next agent)

If asked to do more analysis:

```bash
# Inspect any single paper
python3 -c "
import json
with open('/Users/zhaihaotian/PycharmProjects/argument_graphs_final/ai/FA0001.json') as f: d = json.load(f)
for n in d['nodes']: print(n['id'], n['type'], n.get('display_label',''), 'cites=', n.get('citations',0))
"

# Check coverage on a paper
python3 /Users/zhaihaotian/.claude/skills/argument-graph-extractor/coverage_check.py \
  /path/to/source.pdf \
  /Users/zhaihaotian/PycharmProjects/argument_graphs_final/ai/FA0001.json -v

# Recompute metrics after JSON edits
cd /Users/zhaihaotian/PycharmProjects/argument_graphs_final
python3 /Users/zhaihaotian/.claude/skills/argument-graph-extractor/compute_metrics.py ai/ human/ -o metrics.csv
```

If the user asks to extract a new paper:
1. Read `/Users/zhaihaotian/.claude/skills/argument-graph-extractor/SKILL.md` IN FULL. Don't skim — the audit checklist is critical.
2. Read `EXAMPLE.json` to see the v2 schema.
3. Extract intro via `pdftotext -layout`.
4. Build JSON. Run validator + coverage_check before declaring done.
5. Render SVG.

If the user asks to redo all/many graphs:
- Don't do it in one agent. Spawn 3-6 parallel subagents (general-purpose, model: opus) with 3-5 papers each. Each must read the skill, extract, validate, render, report.
- Pattern from previous rounds: 3-4 extraction subagents → 3-4 reviewer subagents → final pass for any specific issues.

---

## 11. Conversation History Highlights

- **v1 → v2 schema migration**: Started with 10-edge schema (fork/join/critique/motivates/back_reference/addresses + the current 5). Collapsed to 5-edge after user pushed for "fork/join are topology, not edges". Old EXAMPLE.json was preserved briefly as legacy reference, then replaced with v2 FA0013 example.

- **The user pushed back on AI-paper subagent compression at least 3 times**. Final solution: hard `coverage_check.py` validator + Stage 5 audit checklist baked into SKILL.md.

- **The Context vs Limitation distinction took 2-3 iterations**. Final rule includes the "paper-theme alignment" heuristic (if "However" introduces the paper's topic-of-study, it's Context).

- **Anchor extraction**: Initially used `anchor_intros_fixed/*.md` files. After multiple coverage failures, re-extracted ALL anchors from source PDFs. Most anchors gained 50-200% more nodes after the redo.

- **Render iterations**: SVG layout went through ~5 revisions: original → side-enum chips → display_label + text snippet → citation dots on right side → edge legend → Contribution hierarchy support.

- **The user values 「客观可计算」over 「主观判断」**: Whenever a metric depends on LLM judgment (anchor flag, "is this a strong contrast"), they pushed for objective alternatives.

---

## 12. Final State Confirmation (as of handoff)

- 40 graphs in `argument_graphs_final/ai/` and `human/` — all PASS `validate_graph.py`
- All 9 ICLR papers + a sample of others passed `coverage_check.py` ≥85% (BIRD/KAN/InferenceScaling/InfluenceFunctions originally failed and were re-extracted)
- `metrics.csv` has 40 rows × 37 columns, all numeric fields populated
- `REPORT.md` written in Chinese with English-translated table at user's request
- Skill in `/Users/zhaihaotian/.claude/skills/argument-graph-extractor/` is the canonical version; the `EXAMPLE.json` matches current v2 schema

**End of handoff.**
