# TikTok / Instagram capture system (real-browser, bot-immune)

yt-dlp / scrapers get IP-blocked. The user's REAL logged-in browser does NOT. So the capture surface
is the real browser, driven via **claude-in-chrome** (MCP tools). This is the system; no custom
extension needed for the high-signal data.

## Why this works (and bots don't)
- yt-dlp/Playwright = bot signature -> "Your IP address is blocked" (measured).
- Real Chrome (human session) = loads TikTok/IG fine. claude-in-chrome drives THAT browser.

## The flow (repeatable)
1. **NAVIGATE** (`navigate`) to a target: an account `/@handle`, a hashtag `/tag/일본여행`, or a single `/@h/video/ID`.
   (TikTok individual-video + account pages load without login; the For-You feed may wall - prefer account/hashtag/video URLs.)
2. **HARVEST metadata** (`read_page` filter=all) - the highest-signal, programmatic layer:
   - per video: caption, #hashtags, music name + `/music/ID`, likes / comments / **saves** / shares, post date, duration, `/@h/video/ID`.
   - the sidebar / account page yields a WHOLE feed's metadata in one read = the account's content formula.
3. **CAPTURE frames** (`computer` screenshot) for videos worth visual decode - hook (first frame), a mid frame, the end. Click the player to play; screenshot at intervals. (Audio = muted; for MUSIC videos the track name is in the DOM = enough. For VO videos, see Audio gap.)
4. **ANALYZE** with `FRAMEWORK.md` (frontier agent reads frames + metadata). For an account, extract the COMMON formula across its harvested titles + engagement (higher signal than one video).

## Audio gap (closed - VO path)
- Music-based videos: track name is in the DOM (`/music/...`) -> known, no transcription needed.
- Voiceover videos: muted screenshots don't give speech. Use the **refcap tab recorder** Chrome extension
  (`tabcap-extension/`, built): click the icon -> it records that tab's audio+video to a local `.webm` ->
  run `refextract.py <webm>` (whisper) for the timed VO transcript -> analyze with FRAMEWORK. One click =
  one clip; you drive playback (account-safe). See `tabcap-extension/README.md`.
- Fallback (no extension): Windows Game Bar (`Win+G`) records the tab -> same `refextract` path.

## Discovery (honest)
- TikTok/IG have NO public discovery API. Get target URLs via: TikTok web search (`/search`), a hashtag page, a known account, or a web search. Then the flow above runs.

## What it delivers vs the farm
This is a personal capture+analysis utility OUTSIDE the farm. It downloads/records nothing into the
farm; the farm stays the clean cite-or-fail verifier for the few hard numbers only.
