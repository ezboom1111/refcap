#!/usr/bin/env python
# refauto - FULL automation: URL -> yt-dlp download -> refextract (smart frames + timed transcript).
# Then a frontier agent (Claude/Codex) reads refs/<id>/ and decomposes with FRAMEWORK.md.
# NOT part of browser-agent-mcp-farm (personal utility; yt-dlp download is ToS-gray, kept out of the farm).
# Usage: python refauto.py <url> [note] [model]
import sys, os, subprocess, glob

if len(sys.argv) < 2:
    print("usage: python refauto.py <url> [note] [model]"); sys.exit(1)
url = sys.argv[1]
note = sys.argv[2] if len(sys.argv) > 2 else url
model = sys.argv[3] if len(sys.argv) > 3 else "small"
here = os.path.dirname(os.path.abspath(__file__))
dl = os.path.join(here, "dl")
os.makedirs(dl, exist_ok=True)
out_tmpl = os.path.join(dl, "%(id)s.%(ext)s")

print("=== yt-dlp download ===", flush=True)
subprocess.run([sys.executable, "-m", "yt_dlp", "-f", "best[height<=720][ext=mp4]/best[height<=720]/best", "-o", out_tmpl, "--no-playlist", url], check=True)
files = sorted([f for f in glob.glob(os.path.join(dl, "*")) if not f.endswith(".part")], key=os.path.getmtime)
if not files:
    print("download produced no file"); sys.exit(1)
mp4 = files[-1]
print("downloaded:", mp4, flush=True)

print("=== refextract (frames + transcript) ===", flush=True)
subprocess.run([sys.executable, os.path.join(here, "refextract.py"), mp4, "--note", note, "--model", model], check=False)
