# AGENTS.md — refcap

Personal content-reference + multi-source research repo. A **neutral** evidence stack (imports the
`browser-agent-mcp-farm` 0). It powers the **`leesearch-video-heavy`** skill — the heavy / local-extraction
research path under the `leesearch` front-door.

## For any coding agent (Claude Code / Codex / …) working here
- **The loop is `RESEARCH_RUNBOOK.md`** (read it first): open → frontier → ingest → finding(anchored) →
  verify → plan(farm) → digest. The brain is YOU; `refledger.py` is the disk-bound spine that only
  persists nouns (artifact / finding / frontier-entry) and judges whether evidence is real.
- **Skills** are authored canonically here: `SKILL.md` (root = `leesearch-video-heavy`) and `skills/`
  (`leesearch`, `leesearch-video-light`). Deployed copies live in `~/.claude/skills/` (Claude Code) and
  `~/.codex/skills/` (Codex) — same `SKILL.md` format.
- **Always use ascii slugs** for `refledger.py` — never pass a Korean absolute path as an arg (Windows
  mangles it): `SLUG=$(python refledger.py open "<goal>")` then use `$SLUG`.
- **Tests**: `python -m unittest test_refledger test_scenarios` (42, stdlib only).
- **Constraints**: sequential extractor subprocesses (15 GB OOM defense); don't-hoard (keep hashes, delete
  raw media); secrets env-only; no TikTok/IG auto-acquisition / cookies / anti-bot bypass (ToS);
  cite-or-fail proves anchoring, NOT transcript correctness.
