#!/usr/bin/env python
# refextract - turn a recorded reference video (mp4) into AGENT-READABLE evidence:
#   SMART-sampled frames (hook-dense + scene-changes + backbone + end) + TIMESTAMPED transcript.
# The analysis itself is done by a frontier agent (Claude/Codex) reading frames + transcript with
# FRAMEWORK.md. This script is the high-quality EXTRACT only.
# NOT part of browser-agent-mcp-farm (personal reference-analysis utility; keep raw video out of the farm).
# Usage: python refextract.py <video.mp4> [--note "source/context"] [--model small]
import sys, os, subprocess, json, glob, shutil, argparse


def find_ffmpeg():
    if shutil.which("ffmpeg"):
        return "ffmpeg"
    base = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages")
    hits = glob.glob(os.path.join(base, "Gyan.FFmpeg*", "**", "ffmpeg.exe"), recursive=True)
    return hits[0] if hits else None


def run(args):
    subprocess.run(args, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--note", default="")
    ap.add_argument("--model", default="small")
    args = ap.parse_args()

    video = os.path.abspath(args.video)
    if not os.path.exists(video):
        print(json.dumps({"error": "not found: " + video})); return
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        print(json.dumps({"error": "ffmpeg not found"})); return
    ffprobe = "ffprobe" if ffmpeg == "ffmpeg" else os.path.join(os.path.dirname(ffmpeg), "ffprobe.exe")

    name = os.path.splitext(os.path.basename(video))[0]
    here = os.path.dirname(os.path.abspath(__file__))
    outdir = os.path.join(here, "refs", name)
    frames = os.path.join(outdir, "frames")
    os.makedirs(frames, exist_ok=True)

    dur = 0.0
    try:
        r = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", video], capture_output=True, text=True)
        dur = float(r.stdout.strip())
    except Exception:
        dur = 0.0

    # SMART sampling (not uniform): hook is where the scroll-stop happens; scene changes carry the editing rhythm.
    run([ffmpeg, "-y", "-ss", "0", "-t", "3", "-i", video, "-vf", "fps=2", os.path.join(frames, "hook_%02d.jpg")])            # hook 0-3s @2fps
    run([ffmpeg, "-y", "-i", video, "-vf", "select='gt(scene,0.4)',showinfo", "-vsync", "vfr", os.path.join(frames, "scene_%03d.jpg")])  # cuts/transitions
    run([ffmpeg, "-y", "-i", video, "-vf", "fps=1/3", os.path.join(frames, "bb_%03d.jpg")])                                   # backbone 1/3s
    if dur > 1:
        run([ffmpeg, "-y", "-ss", str(max(0.0, dur - 0.5)), "-i", video, "-frames:v", "1", os.path.join(frames, "end.jpg")])  # CTA/end

    frame_files = sorted(os.path.basename(p) for p in glob.glob(os.path.join(frames, "*.jpg")))

    transcript_path = os.path.join(outdir, "transcript_timed.txt")
    seg_count = 0
    lang = "?"
    ocr_meta = {"lines": 0, "hint_chars": 0}
    try:
        import wave, contextlib
        import numpy as np
        import refrecord as R
        # upgraded transcription: extract audio, then process_wav (vad-off + 3-layer gate + degeneracy
        # guard + best-of-2 + Demucs tier-2). Replaces the legacy small+VAD path.
        wav = os.path.join(outdir, "audio.wav")
        run([ffmpeg, "-y", "-i", video, "-vn", "-ac", "2", "-ar", "44100", wav])
        with contextlib.closing(wave.open(wav, "rb")) as w:
            a = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype("float32") / 32768.0
        rms = float((a ** 2).mean() ** 0.5)
        # OCR on-screen text -> dynamic prompt hint. MEASURED: recovers ASR-dropped captions/dialogue
        # (cod_news 90.1->95.2%), neutral on clean VO. file-based only (needs frames). Best-effort.
        # Run OCR in a SUBPROCESS so easyocr's torch RAM is reclaimed before whisper loads (else OOM).
        hint = ""
        try:
            here_dir = os.path.dirname(os.path.abspath(__file__))
            # cwd=here_dir + RELATIVE ascii paths: Windows mangles Korean absolute paths passed as
            # subprocess args. Write JSON to a file (not stdout) to dodge stdout-pipe encoding too.
            rel_frames = os.path.relpath(frames, here_dir)
            ocr_json = os.path.join(outdir, "_ocr.json")
            rel_out = os.path.relpath(ocr_json, here_dir)
            subprocess.run([sys.executable, "refocr.py", "--frames", rel_frames, "--out", rel_out],
                           cwd=here_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
            with open(ocr_json, encoding="utf-8") as jf:
                oc = json.load(jf)
            hint = oc.get("hint", "")
            ocr_meta = {"lines": len(oc.get("lines", [])), "hint_chars": len(hint)}
            os.remove(ocr_json)
        except Exception:
            pass
        res = R.process_wav(wav, R.ESCALATION_MODEL, "ko", rms, outdir, ocr_hint=hint or None)
        lang = "ko"
        seg_count = res["coverage"]["n_segments"]
        for junk in ("audio.wav", "vocals.wav"):   # don't hoard raw audio
            try:
                os.remove(os.path.join(outdir, junk))
            except OSError:
                pass
    except Exception as e:
        with open(transcript_path, "w", encoding="utf-8") as f:
            f.write("# transcript FAILED: %s: %s\n" % (type(e).__name__, e))

    meta = {"video": video, "note": args.note, "durationSec": round(dur, 1), "frames": frame_files, "frameCount": len(frame_files), "transcriptSegments": seg_count, "language": lang, "ocr": ocr_meta, "outdir": outdir}
    with open(os.path.join(outdir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(json.dumps({"ok": True, "outdir": outdir, "frameCount": len(frame_files), "transcriptSegments": seg_count, "durationSec": round(dur, 1), "language": lang}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
