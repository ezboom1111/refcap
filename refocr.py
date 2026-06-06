#!/usr/bin/env python
# refocr - OCR on-screen (burned-in) text from video frames, to use as a DYNAMIC whisper initial_prompt.
# Why: foreign/loanword proper nouns get mis-decoded by ASR ("콜 오브 듀티" -> "뉴티"). Creators almost
# always show those names as on-screen captions/titles. OCR'ing them and priming whisper with that text
# pulls the decoder to the correct rendering -- general (no hardcoded glossary), per-clip, corroborated
# by the visual channel. File-based path only (needs frames; the live WASAPI recorder has no video).
# Usage: python refocr.py <video.mp4>   ->  prints {lines, hint, tokens}
import sys, os, glob, json, subprocess, re

_READER = None
def _reader():
    global _READER
    if _READER is None:
        import easyocr
        _READER = easyocr.Reader(["ko", "en"], gpu=False, verbose=False)
    return _READER


def release():
    """Free the easyocr (torch) reader so its RAM is reclaimed before whisper models load. On a 15GB
    box, easyocr + large-v3 + medium held at once can OOM-kill the process; call this after OCR."""
    global _READER
    _READER = None
    import gc
    gc.collect()


def extract_frames(video, outdir, every_sec=4, scale=720):
    os.makedirs(outdir, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-i", video, "-vf", f"fps=1/{every_sec},scale={scale}:-1",
                    f"{outdir}/f_%03d.jpg", "-loglevel", "error"], check=True)
    return sorted(glob.glob(f"{outdir}/f_*.jpg"))


def ocr_frames(frames, min_conf=0.45, min_len=2, crop=(0.28, 1.0)):
    """OCR the burned-in text. `crop`=(top,bottom) vertical fraction keeps the caption band (center+
    lower) and drops the top logo/watermark zone (which easyocr garbles to noise like 'XtC'). Set
    crop=None to OCR the whole frame."""
    import numpy as np
    from PIL import Image
    r = _reader()
    seen, lines = set(), []
    for f in frames:
        if crop:
            im = Image.open(f).convert("RGB")
            w, h = im.size
            img = np.array(im.crop((0, int(h * crop[0]), w, int(h * crop[1]))))
        else:
            img = f
        for _bbox, text, conf in r.readtext(img, detail=1):
            t = text.strip()
            if conf >= min_conf and len(t) >= min_len:
                k = re.sub(r"\s+", "", t.lower())
                if k and k not in seen:
                    seen.add(k); lines.append(t)
    return lines


def proper_noun_tokens(lines):
    """surface likely proper-noun hints: tokens with Latin letters (loanwords/brands) + multi-char Hangul
    words that look like names (kept short-list, the full lines are also fed as the prompt)."""
    toks = []
    for ln in lines:
        for w in re.split(r"[\s,./!?~·\-]+", ln):
            if re.search(r"[A-Za-z]", w) and len(w) >= 2:
                toks.append(w)
    # dedupe preserve order
    out, s = [], set()
    for t in toks:
        if t.lower() not in s:
            s.add(t.lower()); out.append(t)
    return out


def ocr_video(video, frames_dir=None, every_sec=4):
    frames_dir = frames_dir or f"{os.path.splitext(video)[0]}_ocrframes"
    frames = extract_frames(video, frames_dir, every_sec=every_sec)
    lines = ocr_frames(frames)
    hint = " ".join(lines)
    if len(hint) > 400:
        hint = hint[:400]
    return {"lines": lines, "hint": hint, "tokens": proper_noun_tokens(lines), "n_frames": len(frames)}


if __name__ == "__main__":
    # --frames <dir>: OCR already-extracted jpgs (used by refextract via subprocess, so easyocr's torch
    # RAM is fully reclaimed on exit before the whisper models load -> avoids OOM on a 15GB box).
    if len(sys.argv) >= 3 and sys.argv[1] == "--frames":
        fr = sorted(glob.glob(os.path.join(sys.argv[2], "*.jpg")))
        fr = fr[:: max(1, len(fr) // 24)][:24]   # denser sample -> more caption coverage
        lines = ocr_frames(fr)
        result = {"lines": lines, "hint": " ".join(lines)[:400],
                  "tokens": proper_noun_tokens(lines), "n_frames": len(fr)}
        # --out <file>: write JSON to a UTF-8 file (avoids Windows stdout-pipe encoding failures on
        # Korean text when called as a subprocess). Falls back to stdout.
        out_path = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else None
        if out_path:
            json.dump(result, open(out_path, "w", encoding="utf-8"), ensure_ascii=False)
        else:
            print(json.dumps(result, ensure_ascii=False))
    else:
        print(json.dumps(ocr_video(sys.argv[1]), ensure_ascii=False, indent=2))
