#!/usr/bin/env python3
"""
render_graph.py — deterministic SVG renderer for argument graphs (v2).

Input:  FAxxxx.json (new schema with 5 edge kinds + 7 main types + subtypes)
Output: FAxxxx.svg

Renderer responsibilities (LLM does NOT think about these):
- Place each node in a fixed y-zone by main type
  (Context -> Prior_Work -> Limitation -> Proof -> Method -> Result -> Contribution)
- Within a zone, split into sub-rows by topological depth using same-zone edges
  (so a parent sits above its children when both are in the same zone)
- Show only `display_label` + `id [type:subtype]` in the box; full `text` is in
  the SVG <title> tooltip
- Render `citations` as N small filled dots above the node
- Auto-detect fork nodes (out_degree >= 2) and join nodes (in_degree >= 2),
  draw dashed grouping rectangles around the fork-children / join-parents
  and label them ("FORK: ..." / "JOIN: ..."). Use optional `fork_label` /
  `join_label` fields on the node for custom text.
- Edge color/style by `kind`. Optional `connective` field is rendered as a small
  label on the edge.

Usage:
    python render_graph.py FA0013.json [FA0013.svg]
"""

import json
import sys
from collections import defaultdict, OrderedDict


# ============ LAYOUT CONSTANTS ============
VIEWBOX_W = 1480
MARGIN_X = 170          # left margin to leave room for zone labels
MARGIN_RIGHT = 40
NODE_GAP_X = 18
SUBROW_GAP_Y = 28       # vertical gap between sub-rows within a zone
ZONE_GAP_Y = 60         # vertical gap between zones
ZONE_PAD_TOP = 18       # padding inside zone (above first sub-row)
ZONE_PAD_BOTTOM = 18

BOX_HEIGHT = 56          # baseline; actual height grows with content
BOX_MIN_W = 110
BOX_MAX_W = 360
GROUP_PAD = 12          # padding inside dashed fork/join box

# Per-node text content rendering
LABEL_FONT_SIZE = 11
LABEL_LINE_H = 14
TEXT_FONT_SIZE = 9.5
TEXT_LINE_H = 12
HEADER_H = 18           # top "ID [type]" line
TEXT_MAX_LINES = 4      # cap text snippet to this many wrapped lines
TEXT_MAX_CHARS = 240    # truncate text snippet to this many chars before wrapping

ZONE_ORDER = [
    "Context",
    "Prior_Work",
    "Limitation",
    "Proof",
    "Method",
    "Result",
    "Contribution",
]

# Backward-compat: legacy types map into new zones
TYPE_ALIAS = {
    "Evidence-internal": "Proof",
    "Evidence-external": "Proof",
}

COLORS = {
    "Context":      ("#e0ebf5", "#6d8ba8"),
    "Prior_Work":   ("#e8e8e8", "#888"),
    "Limitation":   ("#f5dcd4", "#c4502e"),
    "Proof":        ("#fff2cc", "#b38a2c"),
    "Method":       ("#d5ece8", "#3a8a7e"),
    "Result":       ("#f0e6f5", "#7a3ec4"),
    "Contribution": ("#d8ead4", "#3e8a3e"),
}

# (color, dashed, stroke_width, marker_id)
EDGE_STYLE = {
    "elaboration": ("#666",    False, 1.2, "ar"),
    "contrast":    ("#c4502e", False, 1.6, "ar-crit"),
    "consequence": ("#3a6a8a", False, 1.5, "ar-cons"),
    "evidence":    ("#b38a2c", False, 1.5, "ar-ev"),
    "addresses":   ("#7a3ec4", True,  1.4, "ar-back"),
}


def wrap_to_lines(s, max_chars):
    """Greedy word-wrap. Splits on space; preserves order; returns list[str]."""
    if not s:
        return []
    words = s.split()
    lines = []
    cur = ""
    for w in words:
        if not cur:
            cur = w
        elif len(cur) + 1 + len(w) <= max_chars:
            cur = cur + " " + w
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def node_content(n, box_w, is_chip=False):
    """Compute the rendered content of a node. Returns dict:
       {label_lines, text_lines, content_h}
    where content_h is just the body height (not including header).
    """
    if is_chip:
        label = n.get("display_label") or (n.get("text", "")[:30])
        return {"label_lines": [label], "text_lines": [], "content_h": SIDE_CHIP_H - 4}

    chars_per_line = max(14, int(box_w / 6.4))

    label = n.get("display_label") or ""
    label_lines = wrap_to_lines(label, chars_per_line)[:2]

    # Show text snippet UNDER the label, but only if the label didn't already
    # cover the whole text (avoid duplication).
    full_text = n.get("text", "") or ""
    text_lines = []
    label_lower = " ".join(label_lines).lower().strip()
    if full_text and label_lower not in full_text.lower() or len(full_text) > len(label) * 2:
        snippet = full_text[:TEXT_MAX_CHARS]
        if len(full_text) > TEXT_MAX_CHARS:
            snippet = snippet.rsplit(" ", 1)[0] + "…"
        # text uses smaller font so chars-per-line is a bit higher
        text_lines = wrap_to_lines(snippet, int(chars_per_line * 1.18))[:TEXT_MAX_LINES]
        if text_lines and len(full_text) > len(" ".join(text_lines)):
            # ensure ellipsis if truncated by line cap
            last = text_lines[-1]
            if not last.endswith("…"):
                text_lines[-1] = last.rstrip(".,;: ") + "…"

    label_h = len(label_lines) * LABEL_LINE_H
    text_h = len(text_lines) * TEXT_LINE_H + (4 if text_lines else 0)
    content_h = label_h + text_h
    return {"label_lines": label_lines, "text_lines": text_lines, "content_h": content_h}


def escape_xml(s):
    if s is None:
        return ""
    return (str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def main_type(t):
    if not t:
        return "Context"
    base = t.split(":", 1)[0].strip()
    return TYPE_ALIAS.get(base, base)


def subtype(t):
    if not t or ":" not in t:
        return ""
    return t.split(":", 1)[1].strip()


# ============ TOPOLOGY ANALYSIS ============

def build_topology(nodes, edges):
    out_neighbors = defaultdict(list)   # parent -> [children] in JSON order
    in_neighbors = defaultdict(list)    # child -> [parents]
    for e in edges:
        out_neighbors[e["from"]].append(e["to"])
        in_neighbors[e["to"]].append(e["from"])
    out_deg = {nid: len(out_neighbors[nid]) for nid in {n["id"] for n in nodes}}
    in_deg = {nid: len(in_neighbors[nid]) for nid in {n["id"] for n in nodes}}
    return out_neighbors, in_neighbors, out_deg, in_deg


def subrow_assignment(zone_nodes, zone_ids, in_neighbors):
    """Topological depth within a zone using only same-zone in-edges."""
    same_zone_parents = {n["id"]: [p for p in in_neighbors[n["id"]] if p in zone_ids]
                          for n in zone_nodes}
    depth = {}
    # Roots = no same-zone parents
    for n in zone_nodes:
        if not same_zone_parents[n["id"]]:
            depth[n["id"]] = 0
    # Iterate
    for _ in range(len(zone_nodes) + 1):
        changed = False
        for n in zone_nodes:
            if n["id"] in depth:
                continue
            ps = same_zone_parents[n["id"]]
            if all(p in depth for p in ps):
                depth[n["id"]] = max(depth[p] for p in ps) + 1
                changed = True
        if not changed:
            break
    # Any leftover (cycles): depth 0
    for n in zone_nodes:
        depth.setdefault(n["id"], 0)
    return depth


# ============ LAYOUT ============

SIDE_CHIP_W = 140
SIDE_CHIP_H = 38
SIDE_CHIP_GAP = 8
SIDE_GAP_FROM_PARENT = 24


def detect_side_enum(nodes, out_neighbors):
    """A fork-parent qualifies for side-enum layout iff:
       - it has >= 2 same-zone children
       - ALL same-zone children are leaves (out_degree == 0)
       - parent zone is NOT Contribution (sub-contributions are substantial,
         render as full nodes below, not chips)
       - all children's display_label is short (<= 30 chars; "X, Y, Z" enums)
    Returns: dict parent_id -> [child_node_dicts in JSON order]
    """
    nodes_by_id = {n["id"]: n for n in nodes}
    side_groups = {}
    for nid, n in nodes_by_id.items():
        children = out_neighbors.get(nid, [])
        if len(children) < 2:
            continue
        parent_zone = main_type(n.get("type"))
        if parent_zone == "Contribution":
            continue
        same_zone_children = [c for c in children
                              if c in nodes_by_id
                              and main_type(nodes_by_id[c].get("type")) == parent_zone]
        if len(same_zone_children) < 2:
            continue
        # All same-zone children must be leaves
        if not all(len(out_neighbors.get(c, [])) == 0 for c in same_zone_children):
            continue
        # All children's display_label must be short
        if not all(len((nodes_by_id[c].get("display_label") or "")) <= 30
                    for c in same_zone_children):
            continue
        side_groups[nid] = [nodes_by_id[c] for c in same_zone_children]
    return side_groups


def compute_layout(nodes, edges):
    """Assign (x, y, w, h) to each node.

    Returns:
        pos: id -> (x, y, w, h)
        viewbox_h: total svg height
        zone_extents: zone -> (y_top, y_bottom)
        zone_subrows: zone -> {subrow_idx: [nodes_in_order]}
        side_groups: parent_id -> [child_nodes] (placed off main spine)
    """
    out_neighbors, in_neighbors, out_deg, in_deg = build_topology(nodes, edges)
    side_groups = detect_side_enum(nodes, out_neighbors)
    side_child_ids = {c["id"] for kids in side_groups.values() for c in kids}

    # Group MAIN-SPINE nodes by zone, skipping side-enum children
    zone_nodes = OrderedDict((z, []) for z in ZONE_ORDER)
    for n in nodes:
        if n["id"] in side_child_ids:
            continue
        z = main_type(n.get("type"))
        if z not in zone_nodes:
            zone_nodes[z] = []
        zone_nodes[z].append(n)

    pos = {}
    zone_extents = {}
    zone_subrows = {}
    current_y = 50

    for z in ZONE_ORDER:
        row = zone_nodes.get(z, [])
        if not row:
            continue
        zone_top = current_y
        zone_ids = {n["id"] for n in row}
        depth = subrow_assignment(row, zone_ids, in_neighbors)
        max_depth = max(depth.values()) if depth else 0

        # Build sub-rows preserving JSON order
        subrows = OrderedDict((d, []) for d in range(max_depth + 1))
        for n in row:
            subrows[depth[n["id"]]].append(n)
        zone_subrows[z] = subrows

        zone_inner_y = zone_top + ZONE_PAD_TOP

        for d, srow in subrows.items():
            n_in_row = len(srow)
            avail = VIEWBOX_W - MARGIN_X - MARGIN_RIGHT

            # If exactly one node in subrow AND it has side-enum children,
            # reserve room on the right for the chip strip.
            side_w_needed = 0
            if n_in_row == 1 and srow[0]["id"] in side_groups:
                kids = side_groups[srow[0]["id"]]
                side_w_needed = (SIDE_GAP_FROM_PARENT
                                 + len(kids) * SIDE_CHIP_W
                                 + (len(kids) - 1) * SIDE_CHIP_GAP)

            if n_in_row == 1:
                if side_w_needed:
                    box_w = min(BOX_MAX_W, avail - side_w_needed)
                else:
                    box_w = min(BOX_MAX_W + 60, avail * 0.55)
            else:
                ideal = (avail - NODE_GAP_X * (n_in_row - 1)) / n_in_row
                box_w = max(BOX_MIN_W, min(BOX_MAX_W, ideal))

            total_w = n_in_row * box_w + (n_in_row - 1) * NODE_GAP_X + side_w_needed
            x_start = MARGIN_X + (avail - total_w) / 2

            # Compute per-row uniform height = max content height across nodes in this subrow
            row_content_h = max(
                node_content(n, box_w)["content_h"] for n in srow
            )
            box_h = max(BOX_HEIGHT, HEADER_H + row_content_h + 12)

            x = x_start
            for n in srow:
                pos[n["id"]] = (x, zone_inner_y, box_w, box_h)
                x += box_w + NODE_GAP_X

            # Place side-enum chips next to qualifying parent in this subrow
            if side_w_needed and n_in_row == 1:
                parent = srow[0]
                px, py, pw, ph = pos[parent["id"]]
                chip_x = px + pw + SIDE_GAP_FROM_PARENT
                chip_y = py + (ph - SIDE_CHIP_H) / 2
                for kid in side_groups[parent["id"]]:
                    pos[kid["id"]] = (chip_x, chip_y, SIDE_CHIP_W, SIDE_CHIP_H)
                    chip_x += SIDE_CHIP_W + SIDE_CHIP_GAP

            zone_inner_y += box_h + SUBROW_GAP_Y

        zone_inner_y -= SUBROW_GAP_Y  # remove trailing gap
        zone_inner_y += ZONE_PAD_BOTTOM
        zone_extents[z] = (zone_top, zone_inner_y)
        current_y = zone_inner_y + ZONE_GAP_Y

    return pos, current_y + 30, zone_extents, zone_subrows, side_groups


# ============ FORK / JOIN GROUP DETECTION ============

def reachable(out_neighbors, src, max_depth=12):
    """Set of node IDs reachable from src via any path."""
    seen = set()
    frontier = [src]
    depth = 0
    while frontier and depth < max_depth:
        nxt = []
        for n in frontier:
            for c in out_neighbors.get(n, []):
                if c not in seen:
                    seen.add(c)
                    nxt.append(c)
        frontier = nxt
        depth += 1
    return seen


def has_ancestor_pair(member_ids, out_neighbors):
    """True if any two members have an ancestor-descendant relationship."""
    for a in member_ids:
        reach_a = reachable(out_neighbors, a)
        for b in member_ids:
            if a != b and b in reach_a:
                return True
    return False


def detect_groups(nodes, edges, pos, out_neighbors, in_neighbors):
    """Find dashed grouping rectangles to draw.

    Returns list of dicts:
      {kind: 'fork'|'join', anchor_id, members:[ids], label, zone}

    Smart filters:
    - For JOIN: skip if any 2 parents have ancestor-descendant relationship
      (it's not a true convergence, just grandparent + descendant repeating).
    - FORK label resolution: per-zone via parent.fork_labels[zone] if present,
      else parent.fork_label, else f"FORK from {nid}".
    """
    nodes_by_id = {n["id"]: n for n in nodes}
    groups = []

    for nid, n in nodes_by_id.items():
        # FORK
        children = out_neighbors.get(nid, [])
        if len(children) >= 2:
            by_zone = defaultdict(list)
            for c in children:
                if c in nodes_by_id:
                    by_zone[main_type(nodes_by_id[c].get("type"))].append(c)
            fork_labels = n.get("fork_labels") or {}
            for z, members in by_zone.items():
                if len(members) >= 2:
                    label = (fork_labels.get(z)
                             or n.get("fork_label")
                             or f"FORK from {nid}")
                    groups.append({
                        "kind": "fork",
                        "anchor_id": nid,
                        "members": members,
                        "label": label,
                        "zone": z,
                    })

        # JOIN
        parents = in_neighbors.get(nid, [])
        if len(parents) >= 2:
            by_zone = defaultdict(list)
            for p in parents:
                if p in nodes_by_id:
                    by_zone[main_type(nodes_by_id[p].get("type"))].append(p)
            join_labels = n.get("join_labels") or {}
            for z, members in by_zone.items():
                if len(members) >= 2 and not has_ancestor_pair(members, out_neighbors):
                    label = (join_labels.get(z)
                             or n.get("join_label")
                             or f"JOIN -> {nid}")
                    groups.append({
                        "kind": "join",
                        "anchor_id": nid,
                        "members": members,
                        "label": label,
                        "zone": z,
                    })

    return groups


def group_bbox(member_ids, pos, pad=GROUP_PAD):
    xs1, ys1, xs2, ys2 = [], [], [], []
    for mid in member_ids:
        if mid not in pos:
            continue
        x, y, w, h = pos[mid]
        xs1.append(x); ys1.append(y); xs2.append(x + w); ys2.append(y + h)
    if not xs1:
        return None
    return (min(xs1) - pad, min(ys1) - pad - 8,
            max(xs2) - min(xs1) + 2 * pad,
            max(ys2) - min(ys1) + 2 * pad + 8)


# ============ EDGE GEOMETRY ============

def edge_endpoints(src_pos, dst_pos):
    sx, sy, sw, sh = src_pos
    dx, dy, dw, dh = dst_pos
    # Same row (horizontal connection)
    if abs(sy - dy) < 18:
        if sx < dx:
            return (sx + sw, sy + sh / 2), (dx, dy + dh / 2)
        else:
            return (sx, sy + sh / 2), (dx + dw, dy + dh / 2)
    # Different rows: bottom-center -> top-center, with horizontal offset
    return (sx + sw / 2, sy + sh), (dx + dw / 2, dy)


# ============ RENDER ============

def render(data):
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])

    out_neighbors, in_neighbors, out_deg, in_deg = build_topology(nodes, edges)
    pos, viewbox_h, zone_extents, zone_subrows, side_groups = compute_layout(nodes, edges)
    groups = detect_groups(nodes, edges, pos, out_neighbors, in_neighbors)
    # Side-enum groups have already been visualized as chips; skip the dashed
    # FORK box for those parents to avoid double decoration.
    side_parent_ids = set(side_groups.keys())
    groups = [g for g in groups
              if not (g["kind"] == "fork" and g["anchor_id"] in side_parent_ids)]

    parts = []
    parts.append(
        f'<svg viewBox="0 0 {VIEWBOX_W} {int(viewbox_h)}" xmlns="http://www.w3.org/2000/svg" '
        f'style="width:100%; background:#fdfcf6; border:1px solid #e2e0d7; border-radius:8px;" '
        f'font-family="-apple-system, BlinkMacSystemFont, Helvetica, Arial, sans-serif">'
    )

    parts.append("""<defs>
  <marker id="ar"      viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M 0 0 L 10 5 L 0 10 z" fill="#666"/></marker>
  <marker id="ar-crit" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M 0 0 L 10 5 L 0 10 z" fill="#c4502e"/></marker>
  <marker id="ar-cons" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M 0 0 L 10 5 L 0 10 z" fill="#3a6a8a"/></marker>
  <marker id="ar-ev"   viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M 0 0 L 10 5 L 0 10 z" fill="#b38a2c"/></marker>
  <marker id="ar-back" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M 0 0 L 10 5 L 0 10 z" fill="#7a3ec4"/></marker>
</defs>""")

    # Zone labels (left margin)
    for z, (y_top, y_bot) in zone_extents.items():
        label_y = (y_top + y_bot) / 2
        parts.append(
            f'<text x="14" y="{int(label_y)}" font-size="11" fill="#666" '
            f'font-weight="700" dominant-baseline="middle">{escape_xml(z.upper())}</text>'
        )
        # subtle horizontal divider above each zone (except first)
        if z != next(iter(zone_extents)):
            parts.append(
                f'<line x1="60" y1="{int(y_top - ZONE_GAP_Y/2)}" '
                f'x2="{VIEWBOX_W - 30}" y2="{int(y_top - ZONE_GAP_Y/2)}" '
                f'stroke="#eee" stroke-width="1"/>'
            )

    # FORK/JOIN dashed group boxes (drawn before edges/nodes so they sit underneath).
    # Fork labels go ABOVE the box; join labels go BELOW; this prevents overlap when
    # the same member set is both forked-from and joined-to.
    for g in groups:
        bbox = group_bbox(g["members"], pos)
        if not bbox:
            continue
        gx, gy, gw, gh = bbox
        color = "#9b8a3a" if g["kind"] == "fork" else "#3a6a8a"
        parts.append(
            f'<rect x="{int(gx)}" y="{int(gy)}" width="{int(gw)}" height="{int(gh)}" '
            f'rx="10" fill="none" stroke="{color}" stroke-width="1.2" stroke-dasharray="5 4" opacity="0.85"/>'
        )
        if g["kind"] == "fork":
            label_y = gy - 4
        else:
            label_y = gy + gh + 12
        parts.append(
            f'<text x="{int(gx + 8)}" y="{int(label_y)}" font-size="10" fill="{color}" '
            f'font-style="italic" font-weight="600">{escape_xml(g["label"])}</text>'
        )

    # Side-enum: dashed enumeration container around the chips, plus optional fork_label.
    # Drawn before edges so it sits underneath.
    nodes_by_id = {n["id"]: n for n in nodes}
    for parent_id, kids in side_groups.items():
        member_ids = [k["id"] for k in kids]
        bbox = group_bbox(member_ids, pos, pad=6)
        if not bbox:
            continue
        gx, gy, gw, gh = bbox
        parts.append(
            f'<rect x="{int(gx)}" y="{int(gy)}" width="{int(gw)}" height="{int(gh)}" '
            f'rx="8" fill="none" stroke="#9b8a3a" stroke-width="1.0" stroke-dasharray="4 3" opacity="0.7"/>'
        )
        flabel = nodes_by_id[parent_id].get("fork_label") or "examples"
        parts.append(
            f'<text x="{int(gx + 8)}" y="{int(gy - 4)}" font-size="9.5" fill="#9b8a3a" '
            f'font-style="italic">{escape_xml(flabel)}</text>'
        )

    # Edges (skip parent -> side-enum-child edges; the chip container conveys the relation)
    side_child_ids = {k["id"] for kids in side_groups.values() for k in kids}
    suppressed_edge_keys = set()
    for parent_id, kids in side_groups.items():
        for k in kids:
            suppressed_edge_keys.add((parent_id, k["id"]))

    for e in edges:
        if (e.get("from"), e.get("to")) in suppressed_edge_keys:
            continue
        src = pos.get(e.get("from"))
        dst = pos.get(e.get("to"))
        if not src or not dst:
            continue
        (x1, y1), (x2, y2) = edge_endpoints(src, dst)
        kind = e.get("kind", "elaboration")
        color, dashed, width, marker = EDGE_STYLE.get(kind, EDGE_STYLE["elaboration"])
        dash = ' stroke-dasharray="5 3"' if dashed else ""
        parts.append(
            f'<line x1="{int(x1)}" y1="{int(y1)}" x2="{int(x2)}" y2="{int(y2)}" '
            f'stroke="{color}" stroke-width="{width}"{dash} marker-end="url(#{marker})" opacity="0.9"/>'
        )
        connective = e.get("connective")
        if connective:
            lx, ly = (x1 + x2) / 2, (y1 + y2) / 2 - 3
            parts.append(
                f'<text x="{int(lx)}" y="{int(ly)}" font-size="9.5" fill="{color}" '
                f'font-weight="600" text-anchor="middle">{escape_xml(connective)}</text>'
            )

    # Nodes
    for n in nodes:
        nid = n["id"]
        if nid not in pos:
            continue
        x, y, w, h = pos[nid]
        full_type = n.get("type", "Context")
        mt = main_type(full_type)
        st = subtype(full_type)
        fill, stroke = COLORS.get(mt, ("#eee", "#888"))
        cx = x + w / 2
        is_chip = nid in side_child_ids

        # Citation dots: stacked vertically on the RIGHT side of the node, just
        # outside the box. Avoids the top-of-box area where incoming arrows land.
        # Chips get smaller dots stacked tighter.
        cites = int(n.get("citations", 0) or 0)
        if cites > 0:
            if is_chip:
                dot_r = 2.0
                dot_gap = 6
                cxd = x + w + 5
                dy0 = y + 6
            else:
                dot_r = 2.8
                dot_gap = 8
                cxd = x + w + 7
                dy0 = y + 8
            for i in range(cites):
                cyd = dy0 + i * dot_gap
                parts.append(
                    f'<circle cx="{cxd:.1f}" cy="{cyd:.1f}" r="{dot_r}" fill="#9b7a2e"/>'
                )

        parts.append(f'<g>')
        full_text = n.get("text", "")

        if is_chip:
            # Compact chip: smaller box, single-line label, no [type] header
            parts.append(
                f'<rect x="{int(x)}" y="{int(y)}" width="{int(w)}" height="{int(h)}" '
                f'rx="5" fill="{fill}" stroke="{stroke}" stroke-width="1.0" opacity="0.95"/>'
            )
            label = n.get("display_label") or (n.get("text", "")[:30])
            parts.append(
                f'<text x="{int(cx)}" y="{int(y + h/2 + 4)}" text-anchor="middle" '
                f'font-size="11" fill="#333" font-weight="500">{escape_xml(label)}</text>'
            )
            # Tiny ID at top-left
            parts.append(
                f'<text x="{int(x + 5)}" y="{int(y + 11)}" font-size="8" fill="#888">{escape_xml(nid)}</text>'
            )
        else:
            anchor_extra = " : ANCHOR" if n.get("anchor") else ""
            type_label = mt + (f": {st}" if st else "") + anchor_extra
            parts.append(
                f'<rect x="{int(x)}" y="{int(y)}" width="{int(w)}" height="{int(h)}" '
                f'rx="6" fill="{fill}" stroke="{stroke}" stroke-width="1.2"/>'
            )
            parts.append(
                f'<text x="{int(cx)}" y="{int(y + 14)}" text-anchor="middle" font-size="10.5" '
                f'font-weight="700" fill="#333">{escape_xml(nid)} [{escape_xml(type_label)}]</text>'
            )

            content = node_content(n, w)
            ty = y + HEADER_H + LABEL_LINE_H - 3
            for ln in content["label_lines"]:
                parts.append(
                    f'<text x="{int(cx)}" y="{int(ty)}" text-anchor="middle" '
                    f'font-size="{LABEL_FONT_SIZE}" font-weight="600" fill="#1a1a1a">{escape_xml(ln)}</text>'
                )
                ty += LABEL_LINE_H

            if content["text_lines"]:
                ty += 2  # small gap between label and text
                for ln in content["text_lines"]:
                    parts.append(
                        f'<text x="{int(cx)}" y="{int(ty)}" text-anchor="middle" '
                        f'font-size="{TEXT_FONT_SIZE}" fill="#555">{escape_xml(ln)}</text>'
                    )
                    ty += TEXT_LINE_H

        tooltip = f"{nid} [{full_type}] (cites={cites})\n{full_text}"
        parts.append(f'<title>{escape_xml(tooltip)}</title>')
        parts.append(f'</g>')

    # Edge legend (top-right)
    legend_x = VIEWBOX_W - 235
    legend_y = 12
    parts.append(
        f'<g><rect x="{legend_x}" y="{legend_y}" width="225" height="92" rx="6" '
        f'fill="#ffffff" stroke="#ccc" stroke-width="0.8" opacity="0.95"/>'
    )
    parts.append(
        f'<text x="{legend_x + 8}" y="{legend_y + 14}" font-size="9.5" font-weight="700" fill="#333">EDGE TYPES</text>'
    )
    edge_legend = [
        ("elaboration", "elaboration (default flow)"),
        ("contrast", "contrast (However / But)"),
        ("consequence", "consequence (Therefore)"),
        ("evidence", "evidence (→ Result/Proof)"),
        ("addresses", "addresses (Method↔Limit)"),
    ]
    for i, (kind, label) in enumerate(edge_legend):
        color, dashed, _, marker = EDGE_STYLE[kind]
        ly = legend_y + 28 + i * 13
        dash_attr = ' stroke-dasharray="4 2"' if dashed else ""
        parts.append(
            f'<line x1="{legend_x + 8}" y1="{ly}" x2="{legend_x + 30}" y2="{ly}" '
            f'stroke="{color}" stroke-width="1.6"{dash_attr} marker-end="url(#{marker})"/>'
        )
        parts.append(
            f'<text x="{legend_x + 38}" y="{ly + 3}" font-size="9" fill="#444">{escape_xml(label)}</text>'
        )
    parts.append('</g>')

    parts.append("</svg>")
    return "\n".join(parts)


def wrap_label(s, max_chars=28):
    if len(s) <= max_chars:
        return [s]
    # break on space closest to mid
    mid = len(s) // 2
    space_idxs = [i for i, ch in enumerate(s) if ch == " "]
    if not space_idxs:
        return [s[:max_chars], s[max_chars:]]
    best = min(space_idxs, key=lambda i: abs(i - mid))
    return [s[:best].strip(), s[best:].strip()]


def main():
    if len(sys.argv) < 2:
        print("Usage: python render_graph.py input.json [output.svg]")
        sys.exit(1)
    in_path = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) > 2 else in_path.replace(".json", ".svg")

    with open(in_path) as f:
        data = json.load(f)

    svg = render(data)
    with open(out_path, "w") as f:
        f.write(svg)
    print(f"Rendered: {out_path}  ({len(data.get('nodes', []))} nodes, {len(data.get('edges', []))} edges)")


if __name__ == "__main__":
    main()
