# refcap tab recorder (Chrome extension, Tier-2)

Records the **active tab's audio + video** to a local `.webm` — the path for **voiceover (VO)** short-form
(TikTok / IG / kids-cafe reviews / honest clothing reviews) where muted screenshots are audio-blind.
No upload, no network, no farm involvement. Personal utility, lives outside the farm.

## Install (one time)
1. Chrome → `chrome://extensions`
2. Toggle **Developer mode** (top-right) ON.
3. **Load unpacked** → select this folder (`C:\Users\이지범\refcap\tabcap-extension`).
4. Pin the **refcap tab recorder** icon (puzzle-piece menu → pin).

## Record one video
1. Open the TikTok/IG/YouTube video in a tab. Have it ready to play.
2. Click the **refcap** icon → badge shows **REC** (red). Press play on the video.
   (The tab stays audible — audio is piped back to you.)
3. When the clip ends, click the icon again → a `refcap-rec-<timestamp>.webm` lands in **Downloads**.

> Records whatever the tab outputs (audio + visible video). Capture exactly the clip you want; trim by
> start/stop timing. One click = one file.

## Analyze (existing pipeline, no new code)
```
python refextract.py "C:\Users\이지범\Downloads\refcap-rec-<ts>.webm" "<note: niche, stats, why selected>"
python colorprofile.py refs\<id>\frames
```
→ `frames/` (smart frames) + `transcript_timed.txt` (whisper VO) + `color.json`.
Then the agent decodes it with `FRAMEWORK.md`.

## Scope / honesty
- **You** drive: you pick and play the clip; the extension only records the tab you point it at. No
  auto-scroll, no bulk feed harvesting (account-safe).
- `tabCapture` requires a user click on the icon each session (Chrome gesture rule) — by design.
- Delete the raw `.webm` after analysis; don't hoard source video.
