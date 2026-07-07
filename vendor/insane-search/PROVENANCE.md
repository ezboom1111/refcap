# insane-search engine — vendored (engine-only)

- **Source**: https://github.com/fivetaku/insane-search (MIT, author: fivetaku)
- **Vendored commit**: `2714e72282b915c6983723652d0c365af08e9e1f` (see `.source-sha`)
- **Vendored on**: 2026-07-07
- **What's here**: `engine/` only — the Python fetch-escalation engine. Run: `python -m engine <URL> [--json] [--trace] [--device mobile] [--no-playwright]` from this directory.
- **What's excluded (deliberately)**: the Claude Code plugin wrapper (`.claude-plugin/`, `setup/`, `skills/insane-search/SKILL.md`, commands). Reason below.

## Why engine-only (audit 2026-07-07)

Full source audit (20 py files, ~4051 lines) before adopting. Findings:

**Engine = clean, high quality, adopted:**
- `safety.py`: textbook SSRF guard — blocks private/loopback/link-local/reserved/metadata (169.254.169.254) + DNS-rebinding defense (resolves host, checks every A/AAAA). Default-deny.
- `transport.py`: per-host curl_cffi session pool, per-hop SSRF-validated redirects, browser→curl cookie bridge. "No-Site-Name Rule" (hashed host keys, no per-site branching) = same philosophy as browser-agent-mcp-farm.
- `__main__.py`: built-in prompt-injection risk detection on fetched content.
- `learning.py`: per-host success-route cache in `~/.insane_search/learned.json` — **local JSON only, no network**, 500-entry cap, 30-day TTL, self-pruning.
- No exfiltration, no backdoor, no arbitrary code execution.

**Plugin wrapper = excluded** (solo-maintainer self-promo + config mutation + vendor lock):
- `setup/setup.sh` injects a `SessionStart` hook into `~/.claude/settings.json` (auto-update-notifier).
- `setup/gptaku-update-check.cjs` phones home each session via `git ls-remote` to the marketplace GitHub repo (24h cached; benign update check, no user data sent).
- `setup.sh` reads past Claude session transcripts locally for language detection (local-only, no send).
- Opt-in "star my repos" via user `gh` auth on explicit "star yes".
- It's a Claude Code plugin (won't run on Hermes/deepseek boxes). Taking engine-only keeps vendor-independence and avoids polluting global config. Matches the 2026-06-25 farm decision philosophy: absorb the useful DNA, not the wrapper.

## Measured A/B (first data point, 2026-07-07)

Naver desktop blog URL `blog.naver.com/<id>/<logNo>`:
- **Hand-wired stack (m.blog URL swap)**: 571 Korean chunks ✅
- **insane-search engine (curl tiers, --no-playwright)**: 15 attempts, all `xform=original`, verdict=challenge, `ok=False` ❌

Root cause: engine's mobile transform (`url_transforms.py`) only does `www.X→m.X` and `X→m.X` — it does NOT handle subdomain hosts (`blog.naver.com`→`m.blog.naver.com`), and has no `PostView` rewrite. So its blind spot = exactly leesearch's Korean-wall recipe. → **complementary, not competing.** Routing: leesearch handles known KR recipes (naver mobile/PostView) first; insane-search engine handles unknown/harder walls (impersonation grid + WAF profiles + learning). Optional future: add a `mobile_prefix_subdomain` transform to the vendored engine to close its blind spot.
