#!/usr/bin/env python
# refbench2 - FULL internal benchmark for refcap's transcription stage.
# Matrix: {small, medium, large-v3, large-v3-turbo, distil-large-v3.5} x {raw, demucs-vocals} x clips.
# Measures: load_s, trans_s, RTF (trans/dur), coverage, mean_logprob, gate status, n_segments, text.
# "Accuracy" PROXY (no human truth): CER vs large-v3-on-RAW (strongest general model on the original mix).
# For the music clip the decisive question is whether Demucs vocal-separation (a) raises large-v3's
# confidence/coverage and (b) makes the CHEAP models CONVERGE to large-v3 (corroboration), or (c) reveals
# the clip is genuinely instrumental (vocals near-silent => honest NO_SPEECH, not a masked VO).
# Writes refs/_bench2.json + refs/_bench2.md (read those via the Read tool; console mangles Korean).
import sys, os, time, json, re, wave, contextlib
from refrecord import load_model, coverage_gate

MODELS = ["small", "medium", "large-v3", "large-v3-turbo", "distil-large-v3.5"]
REF = "large-v3"  # pseudo-reference on RAW audio
HERE = os.path.dirname(os.path.abspath(__file__))
AUD = os.path.join(HERE, "refs", "_bench_audio")
CLIPS = [
    {"id": "wAoMZRil0IY", "kind": "clean-VO"},
    {"id": "SIRnz00fHKE", "kind": "music-dominant"},
]


def norm(s):
    return re.sub(r"[^가-힣a-z0-9]", "", s.lower())


def cer(ref, hyp):
    r, h = norm(ref), norm(hyp)
    if not r:
        return None
    if len(r) < len(h):
        r, h = h, r
    prev = list(range(len(h) + 1))
    for i, rc in enumerate(r, 1):
        cur = [i]
        for j, hc in enumerate(h, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (rc != hc)))
        prev = cur
    return round(prev[-1] / max(1, len(norm(ref))), 3)


def wav_rms(path):
    with contextlib.closing(wave.open(path, "rb")) as w:
        import numpy as np
        n = w.getnframes()
        raw = w.readframes(n)
        a = np.frombuffer(raw, dtype="<i2").astype("float32") / 32768.0
        return float((a ** 2).mean() ** 0.5) if a.size else 0.0


def run_model(model, path, rms, lang="ko"):
    t0 = time.time()
    m, used = load_model(model)
    load_s = time.time() - t0
    t1 = time.time()
    segs, info = m.transcribe(path, vad_filter=False, language=lang,
                              condition_on_previous_text=False, no_speech_threshold=0.6)
    segs = list(segs)
    trans_s = time.time() - t1
    dur = float(info.duration or 0.0)
    text = " ".join(s.text.strip() for s in segs)
    cov = coverage_gate(segs, info, rms=rms)
    return {"model": model.split("/")[-1], "used": used, "load_s": round(load_s, 1),
            "trans_s": round(trans_s, 1), "rtf": round(trans_s / dur, 2) if dur else None,
            "dur": round(dur, 1), "coverage": cov["coverage_ratio"], "logprob": cov["mean_logprob"],
            "status": cov["status"], "nseg": cov["n_segments"], "text": text}


def main():
    out = {}
    for clip in CLIPS:
        cid = clip["id"]
        raw = os.path.join(AUD, f"{cid}.wav")
        voc = os.path.join(AUD, "sep", f"{cid}.vocals.wav")
        sources = [("raw", raw)]
        if os.path.exists(voc):
            sources.append(("demucs-vocals", voc))
        out[cid] = {"kind": clip["kind"], "sources": {}}
        for sname, spath in sources:
            if not os.path.exists(spath):
                continue
            rms = wav_rms(spath)
            rows = []
            for model in MODELS:
                print(f"[refbench2] {cid}/{sname} :: {model} (rms={rms:.3f}) ...", flush=True)
                try:
                    rows.append(run_model(model, spath, rms))
                except Exception as e:
                    rows.append({"model": model, "error": str(e)[:200]})
            out[cid]["sources"][sname] = {"rms": round(rms, 4), "rows": rows}
    # CER: ref = large-v3 on RAW for each clip; also cross-source convergence (vs large-v3 on SAME source)
    for cid, c in out.items():
        raw_rows = c["sources"].get("raw", {}).get("rows", [])
        ref_raw = next((r["text"] for r in raw_rows if r.get("used") == REF), None)
        for sname, s in c["sources"].items():
            ref_same = next((r["text"] for r in s["rows"] if r.get("used") == REF), None)
            for r in s["rows"]:
                if "text" not in r:
                    continue
                r["cer_vs_largev3_raw"] = cer(ref_raw, r["text"]) if ref_raw else None
                r["cer_vs_largev3_samesrc"] = cer(ref_same, r["text"]) if ref_same else None
    with open(os.path.join(HERE, "refs", "_bench2.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    # Markdown report (read via Read tool; avoids console mojibake)
    L = ["# refbench2 - transcription matrix (models x {raw, demucs-vocals})", ""]
    L.append("CER_raw = vs large-v3 on RAW | CER_same = vs large-v3 on SAME source (convergence). "
             "Lower CER_same on demucs-vocals across cheap models => Demucs made them corroborate.\n")
    for cid, c in out.items():
        L.append(f"## {cid}  ({c['kind']})\n")
        for sname, s in c["sources"].items():
            L.append(f"### source = {sname}  (rms={s['rms']})\n")
            L.append("| model | load_s | trans_s | RTF | cover | logprob | CER_raw | CER_same | status |")
            L.append("|---|---|---|---|---|---|---|---|---|")
            for r in s["rows"]:
                if "error" in r:
                    L.append(f"| {r['model']} | ERROR: {r['error']} |||||||| ")
                    continue
                L.append(f"| {r['model']} | {r['load_s']} | {r['trans_s']} | {r['rtf']} | "
                         f"{r['coverage']} | {r['logprob']} | {r.get('cer_vs_largev3_raw')} | "
                         f"{r.get('cer_vs_largev3_samesrc')} | {r['status']} |")
            L.append("")
            for r in s["rows"]:
                if "text" in r:
                    L.append(f"- **{r['model']}**: {r['text'][:300]}")
            L.append("")
    with open(os.path.join(HERE, "refs", "_bench2.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print("[refbench2] saved refs/_bench2.json + refs/_bench2.md")


if __name__ == "__main__":
    main()
