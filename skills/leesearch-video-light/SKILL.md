---
name: leesearch-video-light
description: >-
  LIGHT video / short-form trend research — the cheap, lawful path under the leesearch front-door. Use for
  YouTube videos WITH served captions where you need trend numbers (view-velocity), the spoken gist, or a
  list/guide's items — gathered with free tools (served captions, YouTube Data API, Gemini AI Studio, Google
  Trends), NO download and NO ASR, then the load-bearing numbers sealed through the browser-agent-mcp-farm
  cite-or-fail gate. This is the leesearch entry that delegates to the youtube-research playbook. If the video
  has NO captions, is foreign-language, or is off-YouTube (TikTok/IG), escalate to leesearch-video-heavy.
when_to_use: >-
  Caption-available YouTube trend reading / cheap video research where downloading and ASR are unnecessary.
  For no-caption / foreign / non-YouTube / deep digs, use leesearch-video-heavy instead.
last_verified: 2026-06-09
---

# leesearch-video-light (cheap, lawful, farm-verified)

> Canonical source (versioned in the refcap repo). Deployed copies live at
> `~/.claude/skills/leesearch-video-light/` and `~/.codex/skills/leesearch-video-light/`.

The **light path** of leesearch. **Follow the `youtube-research` skill** — it is the full playbook this entry
delegates to (DISCOVER → GET captions/API → UNDERSTAND → QUANTIFY view-velocity → VERIFY through the farm).
This file exists so the leesearch namespace has a clean light/heavy pair; the engine is `youtube-research`.

## The one rule
**Caption/transcript-first** (the spoken layer is ~100× cheaper than video pixels). No download, no ASR, no
cookies, no anti-bot bypass (ToS). Secrets (`YOUTUBE_API_KEY`) env-only.

## Escalate to leesearch-video-heavy when
- the video has **no served captions**, or
- it is a **foreign-language** VO, or
- it is **off-YouTube** (TikTok / Instagram / Reels / podcast / arbitrary page), or
- you need **local ASR / OCR / frame extraction** or a **resumable multi-source** investigation.

Full playbook + ToS + security rules: the **`youtube-research`** skill.
