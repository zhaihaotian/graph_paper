#!/bin/bash
# Run a single blind review via `claude -p` with NO tools, intro inlined.
# Usage: run_blind_review.sh PXXX
set -e
CODE="$1"
BASE="/Users/zhaihaotian/PycharmProjects/argument_graphs_final"
INTRO_FILE="$BASE/blind_reviews_input/${CODE}.txt"
OUT_FILE="$BASE/blind_reviews_output/${CODE}.json"

[ -f "$INTRO_FILE" ] || { echo "MISSING $INTRO_FILE" >&2; exit 1; }
INTRO=$(cat "$INTRO_FILE")

PROMPT="You are a peer reviewer. Read the paper introduction below and produce a JSON review.

Two judgments:
(a) Peer-review-style assessment: strengths, weaknesses, overall_score (1-10), recommendation
(b) AI-vs-Human prediction: predicted_label, confidence (0-1), reasoning

Score rubric: 1-3 serious flaws | 4-5 weak | 6-7 solid | 8-9 strong | 10 top-tier.
AI cues: short, formulaic, single-anchor, 3-bullet contributions.
Human cues: long, nuanced, multi-thread, varied prose.

Output ONLY valid JSON in this schema, no markdown, no extra text:
{\"peer_review\":{\"strengths\":[\"...\"],\"weaknesses\":[\"...\"],\"overall_score\":<int 1-10>,\"recommendation\":\"accept|weak_accept|borderline|weak_reject|reject\"},\"ai_detection\":{\"predicted_label\":\"AI|Human\",\"confidence\":<float 0-1>,\"reasoning\":\"1-3 sentences\"}}

PAPER INTRODUCTION:
\"\"\"
$INTRO
\"\"\""

env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT claude -p "$PROMPT" \
    --allowedTools "" \
    --model claude-sonnet-4-6 \
    --output-format text \
    2>/dev/null > "$OUT_FILE.raw"

# Extract first JSON object from output (in case of stray text)
python3 -c "
import json, re, sys
raw = open('$OUT_FILE.raw').read().strip()
# Find first { ... matching } at depth 0
depth = 0; start = -1; end = -1
for i, ch in enumerate(raw):
    if ch == '{':
        if depth == 0: start = i
        depth += 1
    elif ch == '}':
        depth -= 1
        if depth == 0: end = i; break
if start >= 0 and end > start:
    js = raw[start:end+1]
    obj = json.loads(js)
    json.dump(obj, open('$OUT_FILE','w'), indent=2)
    print('OK ${CODE}')
else:
    print('FAIL ${CODE}: no JSON in output', file=sys.stderr)
    sys.exit(1)
"
rm -f "$OUT_FILE.raw"
