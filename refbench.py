#!/usr/bin/env python
# refbench - INTERNAL benchmark for the transcription stage of refcap.
# Compares faster-whisper models on the SAME audio: transcribe time, RTF, coverage, and
# "accuracy" PROXY = CER vs the strongest model (large-v3). HONEST: no human ground truth here,
# so "accuracy" means agreement-with-strongest-model, not true WER. High cross-model agreement
# on a span => likely correct (the corroboration principle); divergence => that's where errors live.
# Usage: python refbench.py <file1> [file2 ...]
import sys, os, time, json, re
from refrecord import load_model, coverage_gate

MODELS = ["small", "medium", "large-v3"]  # ghost613-turbo dropped (hallucinates). Add "large-v3-turbo" (generic) to benchmark before adopting.
REF = "large-v3"  # pseudo-reference for CER (strongest general model, NOT human truth)


def norm(s):
    return re.sub(r"[^가-힣a-z0-9]", "", s.lower())


def cer(ref, hyp):
    r, h = norm(ref), norm(hyp)
    if not r:
        return None
    # Levenshtein distance (char), space-O(min)
    if len(r) < len(h):
        r, h = h, r
    prev = list(range(len(h) + 1))
    for i, rc in enumerate(r, 1):
        cur = [i]
        for j, hc in enumerate(h, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (rc != hc)))
        prev = cur
    return round(prev[-1] / max(1, len(norm(ref))), 3)


def run_model(model, path, lang="ko"):
    t_load0 = time.time()
    m, used = load_model(model)
    t_load = time.time() - t_load0
    t0 = time.time()
    segs, info = m.transcribe(path, vad_filter=False, language=lang,
                              condition_on_previous_text=False, no_speech_threshold=0.6)
    segs = list(segs)
    dt = time.time() - t0
    dur = float(info.duration or 0.0)
    text = " ".join(s.text.strip() for s in segs)
    cov = coverage_gate(segs, info, rms=0.1)  # file mode: assume non-silent; coverage logic still valid
    return {"model": model.split("/")[-1], "used": used, "load_s": round(t_load, 1),
            "trans_s": round(dt, 1), "rtf": round(dt / dur, 2) if dur else None,
            "dur": round(dur, 1), "coverage": cov["coverage_ratio"], "logprob": cov["mean_logprob"],
            "status": cov["status"], "nseg": cov["n_segments"], "text": text}


def main():
    files = sys.argv[1:]
    all_rows = {}
    for path in files:
        name = os.path.basename(path)
        rows = []
        for model in MODELS:
            print(f"[refbench] {name} :: {model} ...", flush=True)
            rows.append(run_model(model, path))
        # CER vs reference
        ref_text = next((r["text"] for r in rows if r["used"] == REF or r["model"].startswith("large-v3")), None)
        for r in rows:
            r["cer_vs_ref"] = cer(ref_text, r["text"]) if ref_text is not None else None
        all_rows[name] = rows
        print(f"\n=== {name} (ref={REF}) ===")
        print(f"{'model':<28}{'dur':>6}{'trans_s':>9}{'RTF':>6}{'cover':>7}{'logp':>7}{'CER_ref':>9}  status")
        for r in rows:
            print(f"{r['model']:<28}{r['dur']:>6}{r['trans_s']:>9}{str(r['rtf']):>6}"
                  f"{str(r['coverage']):>7}{str(r['logprob']):>7}{str(r['cer_vs_ref']):>9}  {r['status']}")
        print()
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "refs", "_bench.json"), "w", encoding="utf-8") as f:
        json.dump(all_rows, f, ensure_ascii=False, indent=2)
    print("[refbench] saved refs/_bench.json")


if __name__ == "__main__":
    main()
