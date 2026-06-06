---
name: leesearch
description: >-
  Lee's unified research front-door (이지범's personal research router). Invoke this FIRST whenever the user
  asks to research / investigate / 조사 / 트렌드 분석 anything and wants traceable, farm-verifiable conclusions.
  It does NOT gather by itself — it CLASSIFIES the task and dispatches to the right executor skill
  (leesearch-video-light, leesearch-video-heavy, or the farm lenses market-scan / product-planning /
  deep-browser-research), then makes the load-bearing claims tamper-evident through the browser-agent-mcp-farm
  cite-or-fail gate. Use this as the single deterministic entry point so research is never left to ad-hoc
  skill-picking. Say "leesearch <goal>" to force it.
when_to_use: >-
  Any research / investigation / trend-reading request where you want one reliable front-door that routes to
  the correct gathering skill and guarantees farm-verified, cited conclusions — especially when unsure which
  research skill fits.
---

# leesearch — research front-door (router)

> Canonical source (versioned in the refcap repo). Deployed copies live at `~/.claude/skills/leesearch/`
> and `~/.codex/skills/leesearch/` for Claude Code and Codex respectively.

You (the host agent) are the dispatcher. This skill is the **decision tree**; the leaves do the gathering.
Pick exactly ONE executor per source, run it, then seal the load-bearing claims through the farm gate.

## Routing decision tree
1. **Target is a video / short-form clip?**
   - **YouTube + served captions, and you just need cheap trend numbers / the spoken gist / a list-guide's
     items** → **`leesearch-video-light`** (caption-first, free APIs, no download, no ASR).
   - **No captions / foreign-language VO / TikTok·Instagram·Reels / non-YouTube / a deep resumable
     multi-source dig** → **`leesearch-video-heavy`** (refcap local whisper ASR, audio-separation, OCR,
     frame sampling + a resumable ledger).
2. **Competitor / pricing / market-size?** → **`market-scan`** (farm lens; corroborated across independent domains).
3. **User-pain / feature-gap / requirement / voice-of-customer?** → **`product-planning`** (farm lens).
4. **Generic web page / PDF / dashboard / long article (not video, not market/product)?** → **`deep-browser-research`**.
5. **Just need a tamper-evident bundle of pages you already know?** → drive **`browser-agent-mcp-farm`** directly.

## Invariants (every route)
- **One skill per source.** Never run light + heavy on the same clip.
- **Seal the load-bearing few, not everything.** Register exact bytes → `farm_add_claim` (anchor = verbatim
  quote) → `farm_run_claim_gate` → `farm_export_bundle`. The farm is the VERIFIER, never the understanding
  engine. (An MCP server cannot call skills — YOU dispatch and YOU drive the farm tools.)
- **gate=OK ≠ true.** cite-or-fail proves a quote exists in registered bytes, not that the bytes are correct.
  Surface low-quality / unverifiable citations; corroborate the highest-stakes number across INDEPENDENT domains.
- **An honest gap beats a guess.** If no route reaches the answer, say so.

## Map (who owns what)
| route | skill | owner |
|---|---|---|
| light video | `leesearch-video-light` → wraps `youtube-research` | personal / farm impl |
| heavy video | `leesearch-video-heavy` (refcap stack) | personal |
| market | `market-scan` | farm (shared) |
| product | `product-planning` | farm (shared) |
| generic web | `deep-browser-research` | personal |
| evidence gate | `browser-agent-mcp-farm` | farm (shared) |

Farm skills keep their neutral names (shared, Apache-2.0); `leesearch-*` is the personal front-door layer on top.
