---
name: leesearch-video-heavy
description: >
  Evidence-grounded short-form/content research. Given an investigation goal, organically gather
  multi-source data (YouTube video→ASR, images→vision, web pages, APIs), keep an append-only research
  ledger with provenance + a resumable frontier, anchor every load-bearing claim to registered bytes
  (cite-or-fail), and seal high-value findings as a tamper-evident Merkle bundle. Plugs in BELOW the
  host agent's brain/memory — it does NOT replace them; it adds the provenance layer they lack.
when_to_use: >
  Use when the user asks to research/investigate a topic and wants conclusions that are traceable,
  reproducible, and auditable (not just plausible). Especially short-form trend analysis ("what to post").
host_contract: >
  The HOST AGENT is the brain (decomposition, source choice, mid-stream adaptation, when-to-stop).
  This skill provides only the SPINE: a thin disk-bound shared working memory (refledger.py) + an
  entrance to a deterministic evidence gate (the farm). It imports the farm 0 (neutrality).
---

# refcap-research skill

**Read `RESEARCH_RUNBOOK.md` first** — it is the loop you (the agent) run. This SKILL.md is the one-paragraph
contract; the runbook is the procedure.

## What this skill is / isn't
- **IS**: a neutral, small, externally-auditable EVIDENCE KERNEL. `refledger.py` (stdlib only) keeps
  `research/<ascii-slug>/{ledger.jsonl, frontier.jsonl}` + emits a `farm_plan.json` of cite-or-fail
  calls you execute. The farm (separate MCP server) does the byte-grounding + Merkle seal.
- **ISN'T**: a brain, a memory system, a skill-learning loop, or an orchestration engine. Those are the
  host's (Claude Code / hermes). Do not reimplement them — you will lose to 18-months-ahead incumbents.

## Boundary with leesearch-video-light (분담 — overlap 금지)
This is the **HEAVY path** (`leesearch-video-heavy`; local whisper ASR, audio-separation, OCR, frame
sampling + a resumable ledger). The **LIGHT path** is **`leesearch-video-light`** (which wraps the
`youtube-research` playbook: caption-available YouTube, free APIs, **no download / no ASR**). Routing is
owned by the **`leesearch`** front-door:
- captions exist / YouTube / cheap trend numbers → **`leesearch-video-light`** (cheaper, clearly lawful).
- no captions / foreign VO / off-YouTube (TikTok·IG) / deep multi-source → **this skill** (`leesearch-video-heavy`).
Exactly **one** skill per source; both seal load-bearing claims through the **same** farm cite-or-fail gate.

## The one-line philosophy
Code persists **nouns** (artifact, finding, frontier-entry) and judges only whether evidence is real
(exists + unchanged + capture-quality-labeled). You perform **verbs** (choose, ask, stop, adapt).
Litmus: *"does this decision change per topic?"* → then it's yours, never the code's.

## Honest boundary (do not over-market)
cite-or-fail proves a quote exists in registered bytes — NOT that the bytes (e.g. an ASR transcript) are
correct. Fabrication-at-capture is the open roof; the only upstream defense is `coverage_gate`'s
pre-capture NO_SPEECH/DEGENERATE labeling, preserved as each artifact's `quality_label`. `verify` warns
on low-quality citations; surface that limit to the user, never hide it. Never claim "transcription verified".

## Entry
```bash
SLUG=$(python refledger.py open "<goal>")   # ascii slug; pass it (NOT a Korean abs path) to every command
# then follow RESEARCH_RUNBOOK.md: frontier → ingest → finding(anchored) → verify → plan(farm) → digest
```
Constraints: stdlib-only, sequential extractor subprocess calls (15GB OOM defense), don't-hoard (hashes
kept, raw media deleted), no TikTok/IG auto-acquisition / cookie / anti-bot bypass (ToS).
