#!/usr/bin/env python3
"""
coverage_check.py — sentence-coverage validator for argument graphs.

Reads (JSON + source PDF), extracts intro sentences from the PDF, and reports
which source sentences are NOT represented as nodes in the JSON.

Why it exists: extractor LLMs habitually compress dense methodology paragraphs
(esp. ones with formulas or parallel-clause structures like "In DRAG...
In IterDRAG...") into a single summary node, silently dropping 5-10 sentences.
This script catches that.

Usage:
    python3 coverage_check.py PAPER.pdf GRAPH.json [--threshold 0.85]

Exit code 0 if coverage >= threshold (default 0.85), 1 otherwise.
Prints: per-sentence coverage table, summary stats, and a list of likely-missing
substantive sentences.
"""

import json
import re
import subprocess
import sys
import argparse
import unicodedata
from difflib import SequenceMatcher


def normalize(s):
    """Lowercase, strip whitespace and punctuation, normalize unicode."""
    s = unicodedata.normalize("NFKC", s)
    s = s.lower()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[\(\)\[\]\{\}.,;:!?\"'`\-—–]", "", s)
    return s.strip()


def extract_intro(pdf_path):
    """Run pdftotext and slice out Section 1 / Introduction up to Section 2."""
    # Try -layout first (better for two-column), fall back to default
    for args in [["pdftotext", "-layout", pdf_path, "-"],
                  ["pdftotext", pdf_path, "-"]]:
        try:
            out = subprocess.check_output(args, stderr=subprocess.DEVNULL).decode("utf-8", "ignore")
        except Exception:
            continue
        intro = slice_intro(out)
        if intro and len(intro) > 200:
            return intro
    return ""


def slice_intro(text):
    """Find the Introduction section in raw pdftotext output."""
    # Common patterns for Section 1 header
    intro_pats = [
        r"\n\s*1\s+I\s*N\s*T\s*R\s*O\s*D\s*U\s*C\s*T\s*I\s*O\s*N\s*\n",  # spaced caps
        r"\n\s*1\s+Introduction\s*\n",
        r"\n\s*1\.\s+Introduction\s*\n",
        r"\n\s*INTRODUCTION\s*\n",
        r"\n\s*Introduction\s*\n",
    ]
    end_pats = [
        r"\n\s*2\s+R[Ee][Ll][Aa][Tt][Ee][Dd]",
        r"\n\s*2\.\s+R[Ee][Ll][Aa][Tt][Ee][Dd]",
        r"\n\s*2\s+B[Aa][Cc][Kk][Gg][Rr][Oo][Uu][Nn][Dd]",
        r"\n\s*2\s+P[Rr][Ee][Ll][Ii][Mm][Ii][Nn]",
        r"\n\s*2\s+M[Oo][Dd][Ee][Ll][Ii][Nn][Gg]",
        r"\n\s*2\s+M[Ee][Tt][Hh][Oo][Dd]",
        r"\n\s*2\s+P[Rr][Oo][Pp][Oo][Ss][Ee][Dd]",
        r"\n\s*2\s+T[Hh][Ee]",
        r"\n\s*2\s+[A-Z][A-Za-z]",   # generic "2 Capital..."
        r"\n\s*2\.\s+[A-Z]",
        r"\n\s*RELATED\s+WORK\s*\n",
    ]
    start = None
    for p in intro_pats:
        m = re.search(p, text)
        if m:
            start = m.end()
            break
    if start is None:
        return ""
    end = len(text)
    for p in end_pats:
        m = re.search(p, text[start:])
        if m:
            end = start + m.start()
            break
    return text[start:end]


def split_sentences(intro_text):
    """Split intro text into candidate sentences. Robust to OCR artifacts."""
    # Collapse intra-paragraph line breaks (but keep paragraph breaks as sentence-cut hints)
    text = re.sub(r"-\n", "", intro_text)        # join hyphenated line wraps
    text = re.sub(r"(?<![.\?!])\n(?!\n)", " ", text)  # un-wrap soft line breaks
    text = re.sub(r"\s+", " ", text)
    # Split on sentence-final punctuation followed by space + capital letter
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z(\"'])", text)
    sents = [p.strip() for p in parts if len(p.strip()) > 20]
    # Filter out obvious junk: figure refs, footers, page-num lines
    sents = [s for s in sents
             if not re.match(r"^(Figure|Table|Equation|Eq\.)\s*\d", s)
             and "arXiv:" not in s
             and not re.match(r"^Published as", s)]
    return sents


def is_transition(sent):
    """Pure-transition / boilerplate sentences that may legitimately be skipped."""
    s = sent.lower().strip()
    patterns = [
        r"^(we|the paper|this paper) (organize|is organized|is structured)",
        r"^(the |our )?main contributions? (of this work|of this paper)? are",
        r"^(our|the) contributions? are summarized as follows",
        r"^the rest of (the |this )paper",
        r"^the remainder of (this|the) paper",
        r"^code (is |and|will|are)? (available|released)",
        r"^(the )?code (and )?(model|data|weights)? ?(are|is) (available|released|public)",
        r"^see (figure|fig|table|appendix)",
    ]
    for p in patterns:
        if re.search(p, s):
            return True
    return False


def best_match(sent, node_texts_norm):
    """Find max similarity between a source sentence and any node text."""
    s_norm = normalize(sent)
    if not s_norm:
        return 0.0, -1
    best_ratio, best_idx = 0.0, -1
    for i, n_norm in enumerate(node_texts_norm):
        # Substring match (cheap, high-confidence): if 60% of normalized
        # sentence appears as substring of node text → counts as match
        if len(s_norm) >= 30 and s_norm[:int(len(s_norm) * 0.6)] in n_norm:
            return 1.0, i
        if len(n_norm) >= 30 and n_norm[:int(len(n_norm) * 0.6)] in s_norm:
            return 1.0, i
        # SequenceMatcher fallback
        r = SequenceMatcher(None, s_norm, n_norm).ratio()
        if r > best_ratio:
            best_ratio, best_idx = r, i
    return best_ratio, best_idx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", help="Source PDF path")
    ap.add_argument("json", help="Argument graph JSON path")
    ap.add_argument("--threshold", type=float, default=0.85,
                    help="Required coverage ratio (default 0.85)")
    ap.add_argument("--match-cutoff", type=float, default=0.55,
                    help="Min similarity to count a sentence as covered (default 0.55)")
    ap.add_argument("--verbose", "-v", action="store_true",
                    help="Print full per-sentence table")
    args = ap.parse_args()

    intro = extract_intro(args.pdf)
    if not intro:
        print(f"FAIL: could not extract intro from {args.pdf}")
        sys.exit(1)
    sents = split_sentences(intro)

    with open(args.json) as f:
        d = json.load(f)
    node_texts = [n.get("text", "") for n in d["nodes"]]
    node_ids = [n["id"] for n in d["nodes"]]
    node_texts_norm = [normalize(t) for t in node_texts]

    covered = []
    missing = []
    transitions_skipped = []

    for i, s in enumerate(sents):
        if is_transition(s):
            transitions_skipped.append((i + 1, s))
            continue
        ratio, idx = best_match(s, node_texts_norm)
        if ratio >= args.match_cutoff:
            covered.append((i + 1, ratio, node_ids[idx], s))
        else:
            missing.append((i + 1, ratio, idx, s))

    n_substantive = len(covered) + len(missing)
    coverage_ratio = len(covered) / n_substantive if n_substantive else 1.0

    print(f"=== Coverage report: {args.json} vs {args.pdf} ===")
    print(f"  source sentences (substantive): {n_substantive}")
    print(f"  source sentences (transitions): {len(transitions_skipped)}")
    print(f"  nodes in JSON: {len(node_texts)}")
    print(f"  covered: {len(covered)}  missing: {len(missing)}")
    print(f"  coverage ratio: {coverage_ratio:.1%}  (threshold {args.threshold:.0%})")

    if args.verbose:
        print()
        print("--- COVERED ---")
        for sid, r, nid, s in covered:
            print(f"  S{sid:>2} [{r:.2f}] -> {nid}: {s[:100]}")
        if transitions_skipped:
            print()
            print("--- TRANSITIONS (skipped) ---")
            for sid, s in transitions_skipped:
                print(f"  S{sid:>2}: {s[:100]}")

    if missing:
        print()
        print(f"--- MISSING ({len(missing)} sentence(s) NOT represented as a node) ---")
        for sid, r, idx, s in missing:
            best_node = node_ids[idx] if idx >= 0 else "?"
            print(f"  S{sid:>2} [best ratio {r:.2f} vs {best_node}]")
            print(f"     {s[:200]}")
            print()

    if coverage_ratio < args.threshold:
        print(f"FAIL: coverage {coverage_ratio:.1%} < threshold {args.threshold:.0%}")
        sys.exit(1)
    else:
        print(f"OK: coverage {coverage_ratio:.1%} >= threshold {args.threshold:.0%}")
        sys.exit(0)


if __name__ == "__main__":
    main()
