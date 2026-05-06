#!/usr/bin/env python3
"""
validate_graph.py — schema validator for extracted argument graphs.

New schema (v2):
- 5 canonical edge kinds: elaboration / contrast / consequence / evidence / addresses
- 7 canonical main types: Context / Prior_Work / Limitation / Method / Result / Proof / Contribution
  (subtypes via free-form ': subtype' suffix; only the part before ':' is validated)
- fork / join are NOT edge kinds — they are computed from out_degree / in_degree

Usage:
    python validate_graph.py FA0013.json
    python validate_graph.py graphs_v1/*.json   # batch
"""

import json
import sys
import glob
from collections import Counter, defaultdict

CANONICAL_KINDS = {
    'elaboration', 'contrast', 'consequence', 'evidence', 'addresses'
}

CANONICAL_TYPES = {
    'Context', 'Prior_Work', 'Limitation',
    'Method', 'Result', 'Proof', 'Contribution',
    # Backward-compat aliases (legacy graphs):
    'Evidence-internal', 'Evidence-external',
}

# Removed in v2 — flagged with helpful redirects
RETIRED_KINDS = {
    'fork':           'fork is now a node topology property (out_degree>=2). Use elaboration edges from parent to children.',
    'join':           'join is now a node topology property (in_degree>=2). Use elaboration/consequence edges from parents to child.',
    'critique':       'use contrast (with marker) or elaboration.',
    'motivates':      'use consequence (with marker like "To this end" / "为此").',
    'back_reference': 'use addresses (cross-segment + lexical overlap).',
}


def main_type(t):
    """Strip ': subtype' suffix; return main type."""
    if not t:
        return ''
    return t.split(':', 1)[0].strip()


def validate(path):
    with open(path) as f:
        d = json.load(f)
    errors = []
    warnings = []

    nodes = d.get('nodes', [])
    edges = d.get('edges', [])
    node_ids = {n['id'] for n in nodes}

    # Type validation (strip subtype before validating)
    for n in nodes:
        mt = main_type(n.get('type'))
        if mt not in CANONICAL_TYPES:
            errors.append(f"Node {n.get('id','?')}: bad type '{n.get('type')}' (main='{mt}')")
        if not n.get('text', '').strip():
            errors.append(f"Node {n.get('id','?')}: missing/empty text")
        # display_label recommended but not required
        if not n.get('display_label'):
            warnings.append(f"Node {n.get('id','?')}: missing display_label (renderer will truncate text)")

    # Edge validation
    out_deg = defaultdict(int)
    in_deg = defaultdict(int)
    for e in edges:
        k = e.get('kind', '')
        if k in RETIRED_KINDS:
            errors.append(
                f"Edge {e.get('from')}->{e.get('to')}: retired kind '{k}'. {RETIRED_KINDS[k]}"
            )
        elif k not in CANONICAL_KINDS:
            errors.append(f"Edge {e.get('from')}->{e.get('to')}: bad kind '{k}'")
        if e.get('from') not in node_ids:
            errors.append(f"Edge from unknown node: {e.get('from')}")
        if e.get('to') not in node_ids:
            errors.append(f"Edge to unknown node: {e.get('to')}")
        out_deg[e.get('from')] += 1
        in_deg[e.get('to')] += 1

    # Contribution outgoing edges:
    #   (1) `addresses` → Limitation (back-reference: this contribution resolves
    #       a named gap)
    #   (2) `elaboration` → another Contribution (main contribution unfolding
    #       into sub-claims — e.g., "Contribution 3: X" elaborating into
    #       "3a: mechanism", "3b: evidence", "3c: implication")
    # All other outgoing kinds from Contribution are forbidden.
    contrib_ids = {n['id'] for n in nodes if main_type(n.get('type')) == 'Contribution'}
    limitation_ids = {n['id'] for n in nodes if main_type(n.get('type')) == 'Limitation'}
    for e in edges:
        if e.get('from') in contrib_ids:
            kind = e.get('kind')
            to = e.get('to')
            if kind == 'addresses':
                if to not in limitation_ids:
                    errors.append(
                        f"Contribution `addresses` edge must target a Limitation: "
                        f"{e.get('from')}->{to}"
                    )
            elif kind == 'elaboration':
                if to not in contrib_ids:
                    errors.append(
                        f"Contribution `elaboration` edge must target another Contribution "
                        f"(sub-claim): {e.get('from')}->{to}"
                    )
            else:
                errors.append(
                    f"Contribution may only have outgoing `addresses` (→ Limitation) "
                    f"or `elaboration` (→ another Contribution) edges, "
                    f"not '{kind}': {e.get('from')}->{to}"
                )

    # Limitation source rule: every Limitation must have at least one incoming
    # edge from Prior_Work or another Limitation (excluding addresses back-refs
    # which come from Method/Contribution and represent resolution, not source).
    in_by_node = defaultdict(list)
    for e in edges:
        in_by_node[e.get('to')].append((e.get('from'), e.get('kind')))
    for nid in limitation_ids:
        sources = [(s, k) for s, k in in_by_node[nid] if k != 'addresses']
        src_main_types = {main_type(next((n.get('type') for n in nodes if n['id'] == s), '')) for s, _ in sources}
        if not (src_main_types & {'Prior_Work', 'Limitation'}):
            srcs_str = ', '.join(f"{s}({main_type(next((n.get('type') for n in nodes if n['id']==s), ''))})" for s,_ in sources) or 'NONE'
            warnings.append(
                f"Limitation {nid}: no Prior_Work/Limitation source (only from {{{srcs_str}}}). "
                f"Apply Pass 3 fix: re-type to Context, add PW->L edge, or split out a buried PW."
            )

    # Topology report (informational)
    fork_nodes = sorted(nid for nid, d in out_deg.items() if d >= 2)
    join_nodes = sorted(nid for nid, d in in_deg.items() if d >= 2)

    # Type histogram
    types = Counter(main_type(n.get('type', '?')) for n in nodes)
    kinds = Counter(e.get('kind', '?') for e in edges)

    # Subtype histogram (anything with ':')
    subtypes = Counter(
        n.get('type') for n in nodes if ':' in (n.get('type') or '')
    )

    return errors, warnings, types, kinds, fork_nodes, join_nodes, subtypes


def main():
    if len(sys.argv) < 2:
        print("Usage: python validate_graph.py FILE.json [FILE2.json ...]")
        sys.exit(1)

    paths = []
    for arg in sys.argv[1:]:
        paths.extend(glob.glob(arg) if '*' in arg else [arg])

    total_err = 0
    for path in paths:
        errors, warnings, types, kinds, fork_nodes, join_nodes, subtypes = validate(path)
        status = "OK " if not errors else "FAIL"
        print(f"{status}  {path}  nodes={sum(types.values())}  edges={sum(kinds.values())}")
        for e in errors:
            print(f"   ERROR: {e}")
        for w in warnings:
            print(f"   WARN:  {w}")
        if fork_nodes:
            print(f"   fork nodes (out_degree>=2): {', '.join(fork_nodes)}")
        if join_nodes:
            print(f"   join nodes (in_degree>=2):  {', '.join(join_nodes)}")
        if subtypes:
            sub_str = ', '.join(f"{k}({v})" for k, v in subtypes.most_common())
            print(f"   subtypes seen: {sub_str}")
        total_err += len(errors)

    if total_err:
        sys.exit(1)


if __name__ == '__main__':
    main()
