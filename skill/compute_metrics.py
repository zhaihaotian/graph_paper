#!/usr/bin/env python3
"""
compute_metrics.py — compute 6 core fingerprint metrics from argument graphs.

Reads .json files in folder(s) of argument graphs (output of the extractor),
computes the 6 curated metrics, and writes a CSV.

The 6 metrics (all p<0.001 on n=80 corpus, AI vs Human):

    Structure
      sum_node_degree       — Σ (in_deg + out_deg) over all nodes = 2 × |edges|
      graph_longest_path    — DAG max-depth (DFS + memo with cycle guard)

    Prior_Work
      pw_node_count         — # of nodes with type=Prior_Work (incl. sub-claims)
      pw_total_cites        — Σ citations over Prior_Work nodes  (strongest signal)

    Limitation
      lim_scope_avg_cites   — paper-level "critique surface": ⋃ over all Limitation
                              nodes L of (PW ancestors at first qualifying BFS depth
                              ∪ their PW elaboration children); sum citations across
                              the union.  (strongest signal)

    Method
      method_node_count     — # of nodes with type=Method (incl. components)

Usage:
    python3 compute_metrics.py ai/ human/ -o metrics.csv
    python3 compute_metrics.py graphs/ -o metrics.csv
"""

import json
import sys
import os
import argparse
import csv
from collections import defaultdict


def main_type(t):
    if not t:
        return ""
    return t.split(":", 1)[0].strip()


def compute_one(d, label=""):
    nodes = d.get("nodes", [])
    edges = d.get("edges", [])
    n_id = {n["id"]: n for n in nodes}

    # Topology
    out_n = defaultdict(list)
    in_n = defaultdict(list)
    for e in edges:
        out_n[e["from"]].append(e["to"])
        in_n[e["to"]].append(e["from"])

    # Type filters
    pw_nodes = [n for n in nodes if main_type(n.get("type")) == "Prior_Work"]
    lim_nodes = [n for n in nodes if main_type(n.get("type")) == "Limitation"]
    method_nodes = [n for n in nodes if main_type(n.get("type")) == "Method"]
    pw_ids_all = {n["id"] for n in pw_nodes}

    # ------------------------------------------------------------------
    # 1. sum_node_degree = Σ (in_deg + out_deg) = 2 × |edges|
    # ------------------------------------------------------------------
    sum_node_degree = sum(len(out_n[nid]) + len(in_n[nid]) for nid in n_id)

    # ------------------------------------------------------------------
    # 2. graph_longest_path — DFS with memoization + cycle guard
    #    (addresses edges may create back-edges; treat them as terminating)
    # ------------------------------------------------------------------
    memo, on_stack = {}, set()
    def longest_from(nd):
        if nd in memo: return memo[nd]
        if nd in on_stack: return 1
        on_stack.add(nd)
        best = 1
        for c in out_n[nd]:
            best = max(best, 1 + longest_from(c))
        on_stack.discard(nd)
        memo[nd] = best
        return best
    graph_longest_path = max((longest_from(nid) for nid in n_id), default=0)

    # ------------------------------------------------------------------
    # 3. pw_node_count
    # ------------------------------------------------------------------
    pw_node_count = len(pw_nodes)

    # ------------------------------------------------------------------
    # 4. pw_total_cites = Σ citations over Prior_Work nodes
    # ------------------------------------------------------------------
    pw_total_cites = sum(int(n.get("citations", 0) or 0) for n in pw_nodes)

    # ------------------------------------------------------------------
    # 5. lim_scope_avg_cites (v3 — per-paper PW union "critique surface")
    #
    # For each Limitation L, reverse-BFS upward (excluding `addresses`
    # back-references). At the first BFS depth where any PW ancestors exist,
    # build coverage_L = (PW ancestors) ∪ (their PW elaboration children).
    # If any node in coverage_L has citations>0, this L contributes coverage_L
    # to the paper's PW union; otherwise continue BFS upward.
    #
    # paper_pw_union = ⋃ coverage_L over qualifying L
    # lim_scope_avg_cites = Σ p.cites for p in paper_pw_union
    # ------------------------------------------------------------------
    in_n_no_addr = defaultdict(list)
    out_n_no_addr = defaultdict(list)
    for e in edges:
        if e.get("kind") != "addresses":
            in_n_no_addr[e["to"]].append(e["from"])
            out_n_no_addr[e["from"]].append(e["to"])

    paper_pw_union = set()
    for L in lim_nodes:
        seen, frontier = {L["id"]}, [L["id"]]
        coverage_L = None
        for _ in range(15):
            nxt = []
            for nd in frontier:
                for p in in_n_no_addr[nd]:
                    if p not in seen:
                        seen.add(p)
                        nxt.append(p)
            if not nxt: break
            pw_anc = [p for p in nxt if p in pw_ids_all]
            if pw_anc:
                coverage = set()
                for pw in pw_anc:
                    coverage.add(pw)
                    for child in out_n_no_addr[pw]:
                        if child in pw_ids_all:
                            coverage.add(child)
                if any(int(n_id[p].get("citations", 0) or 0) > 0 for p in coverage):
                    coverage_L = coverage
                    break
            frontier = nxt
        if coverage_L is not None:
            paper_pw_union |= coverage_L
    lim_scope_avg_cites = sum(int(n_id[p].get("citations", 0) or 0)
                               for p in paper_pw_union)

    # ------------------------------------------------------------------
    # 6. method_node_count
    # ------------------------------------------------------------------
    method_node_count = len(method_nodes)

    return {
        "label": label,
        "paper_id": d.get("paper_id", ""),
        "sum_node_degree": sum_node_degree,
        "graph_longest_path": graph_longest_path,
        "pw_node_count": pw_node_count,
        "pw_total_cites": pw_total_cites,
        "lim_scope_avg_cites": lim_scope_avg_cites,
        "method_node_count": method_node_count,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folders", nargs="+",
                    help="One or more folders of .json graphs. "
                         "Folder basename becomes the `label` column.")
    ap.add_argument("-o", "--out", default="-",
                    help="Output CSV path (default: stdout)")
    args = ap.parse_args()

    rows = []
    for folder in args.folders:
        label = os.path.basename(os.path.normpath(folder))
        for fn in sorted(os.listdir(folder)):
            if not fn.endswith(".json"): continue
            path = os.path.join(folder, fn)
            try:
                d = json.load(open(path))
            except Exception as ex:
                print(f"WARN: skipping {path}: {ex}", file=sys.stderr)
                continue
            row = compute_one(d, label=label)
            row["file"] = fn
            rows.append(row)

    if not rows:
        print("No JSON found.", file=sys.stderr)
        sys.exit(1)

    cols = ["label", "file", "paper_id",
            "sum_node_degree", "graph_longest_path",
            "pw_node_count", "pw_total_cites",
            "lim_scope_avg_cites", "method_node_count"]

    out = sys.stdout if args.out == "-" else open(args.out, "w")
    w = csv.DictWriter(out, fieldnames=cols)
    w.writeheader()
    for r in rows:
        w.writerow({c: r.get(c, "") for c in cols})
    if args.out != "-":
        out.close()
        print(f"Wrote {len(rows)} rows × 6 metrics to {args.out}", file=sys.stderr)

    # Per-label means to stderr
    by_label = defaultdict(list)
    for r in rows:
        by_label[r["label"]].append(r)
    metric_cols = cols[3:]  # skip label/file/paper_id
    print("\n=== Per-label means ===", file=sys.stderr)
    print(f"{'metric':<24}" + "".join(f"{lbl:>14}" for lbl in by_label),
          file=sys.stderr)
    for c in metric_cols:
        line = f"{c:<24}"
        for lbl, rs in by_label.items():
            vals = [r[c] for r in rs if isinstance(r.get(c), (int, float))]
            mean = sum(vals)/len(vals) if vals else 0.0
            line += f"{mean:>14.3f}"
        print(line, file=sys.stderr)


if __name__ == "__main__":
    main()
