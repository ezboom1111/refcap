#!/usr/bin/env python
# refrecord - AUTONOMOUS desktop-audio capture (WASAPI loopback) -> timed transcript, hardened by a
# 3-layer coverage gate + a measured tier-2 recovery for music-masked VO.  No click / cable / 3rd party.
#
# PIPELINE (all thresholds + model picks are BENCHMARKED, see refbench2.py / refs/_bench2.json):
#   1. record default-speaker loopback -> audio.wav
#   2. transcribe with PRIMARY (medium): clean VO -> CER 0.01 vs large-v3, and conservative on hard audio
#      so the gate fires honestly instead of passing garbage.
#   3. LAYER-3 coverage/confidence gate: turns an incomplete transcript into a LOUD status, not silence.
#   4. TIER-2 (only when the gate flags a gap on real audio): Demucs strips the BGM, then large-v3 reads
#      the isolated vocals.  MEASURED: large-v3 on a music clip went COVERAGE_GAP(cov 0.10, hallucinated
#      "자막은 설정에서...") -> OK(cov 0.60, coherent "야 빠졌다... 탈락했어... 노란차 출동"); cheap models
#      then corroborate the same recovered content. Demucs RTF ~0.4 on CPU, paid only on flagged clips.
#   5. boilerplate filter: drops known whisper non-speech hallucinations (유료 광고 / 자막 설정 / 구독·좋아요).
#
# MEASURED ACCURACY (clean-VO Korean review content; 3 clips; cross-vendor agreement vs Google ASR +
# human burned-in-subtitle adjudication, NOT a self-proxy): bra 96.8%, tshirt 96.4% (large-v3+prompt),
# drmartens whisper >=90% (its 87% cross-vendor number was depressed by GOOGLE's errors, which the human
# subtitle disproved). >=90% target MET on clean VO. NOT reachable on music-only / no-VO montages (there
# is no verbatim VO to transcribe) - the gate honestly reports NO_SPEECH there instead of fabricating.
# ACCURACY MODE: pass model="large-v3" -> primary runs large-v3 + DOMAIN_PROMPT (the verified ~96% config).
#
# MODEL VERDICTS (benchmarked, do not relitigate without re-measuring):
#   medium        = PRIMARY. accurate + conservative; best gate partner.
#   small         = fast fallback if primary won't load (clean VO CER 0.058).
#   large-v3      = ESCALATION / tier-2 reader. strongest on hard audio; cheap+fast on clean vocals (RTF 0.33).
#   large-v3-turbo= OPTIONAL fast-clean strong model (CER 0.019, RTF 0.55 = 2.2x faster than large-v3) BUT
#                   hallucinates more on hard audio -> only for clean input, never as the tier-2 reader.
#   distil-large-v3.5 = REJECTED for Korean (English-only distillation: outputs English garbage, CER ~1-2).
#   ghost613 turbo(KO)= REJECTED (repetition-loop hallucination "황 황 황…", CER 0.89-0.95, gate-blind).
# Usage: python refrecord.py <seconds> <out_id> [model] [lang=ko]   (model=large-v3 -> accuracy mode)
import sys, os, json, wave, re
import numpy as np
import soundcard as sc

SR = 48000  # native loopback rate; faster-whisper resamples internally
PRIMARY_MODEL = "medium"
FALLBACK_MODEL = "small"
ESCALATION_MODEL = "large-v3"
SEPARATION_MODEL = "htdemucs_ft"   # tier-2 separator. BENCHMARKED: fine-tuned htdemucs recovers a FULLER VO
                                   # than default htdemucs (11 vs 2 segments, logprob -0.50 vs -0.68, complete
                                   # narration vs a 2-phrase fragment) at ~5x the time (RTF 1.8 vs 0.34). tier-2
                                   # is a last-resort recovery path hit only on flagged clips, so completeness
                                   # beats speed here. Set to "htdemucs" if separation latency matters more.
# Domain priming for the strong-model passes. MEASURED (3 clean-VO clips, cross-vendor vs Google ASR +
# human burned-in-subtitle adjudication): a generic-register prompt raised large-v3 agreement on the
# marginal clip from 91.6% -> 96.4% (prevented a segment-drop, fixed "털"->"허리"), neutral elsewhere,
# with NO content-parroting (it names no products, only the register). large-v3+prompt is the verified
# >=90% (in fact ~96%) accuracy config for clean Korean review VO.
DOMAIN_PROMPT = "다음은 한국어 패션·제품 비교 리뷰 영상의 또박또박한 내레이션입니다."

# Known whisper hallucinations on non-speech / music (NEVER genuine VO in this domain). Matched on a
# normalized form so spacing/punctuation variants are caught. Kept tight to avoid removing real lines.
HALLUCINATION_BOILERPLATE = {
    "이영상은유료광고를포함하고있습니다", "자막은설정에서선택하실수있습니다",
    "시청해주셔서감사합니다", "구독과좋아요부탁드립니다", "구독좋아요알림설정",
    "이시각세계였습니다", "한글자막", "엠비씨뉴스", "다음영상에서만나요",
    "자막제공배달의민족", "자막제공", "한글자막by", "본방송은유료광고를포함하고있습니다",
    "지금까지뉴스스토리였습니다", "지금까지000였습니다", "끝까지시청해주셔서감사합니다",
}


def _norm(s):
    return re.sub(r"[^가-힣a-z0-9]", "", s.lower())


def _words(text):
    return [w for w in re.sub(r"[^\w가-힣]", " ", text).split() if w]


def degeneracy(segs):
    """LAYER-3.5: detect degenerate ASR output the coverage gate is BLIND to. Counting loops
    ('1 2 3 .. 13'), word repetition ('물을 물을 물을'), single-char loops ('황 황 황') all have LOW
    no_speech_prob -> high coverage -> status OK, yet the text is garbage. MEASURED: medium on a music
    clip returned cov 0.80 / OK with text '1.2.3...13 ... 물을 물을 물을' -> this forces tier-2 anyway."""
    words = [w for s in segs for w in _words(s.text)]
    n = len(words)
    if n < 6:
        return {"degenerate": False, "reason": None}
    uniq = len(set(words)) / n
    run = best = 1
    for i in range(1, n):
        run = run + 1 if words[i] == words[i - 1] else 1
        best = max(best, run)
    tiny = sum(1 for w in words if w.isdigit() or len(w) <= 1) / n
    if tiny > 0.5:
        return {"degenerate": True, "reason": f"counting/tiny-token loop ({tiny:.0%} bare digits/1-char)"}
    # only a DOMINANT loop is degeneracy; a local ASR hiccup (e.g. '하기도'x7 inside a 200-word travel
    # list) must NOT flag the whole good transcript. MEASURED: gyeongju_food false-positive. Require the
    # run to dominate (>=25% of words, min 8) -- global garbage is still caught by tiny/uniq below.
    if best >= max(8, int(0.25 * n)):
        return {"degenerate": True, "reason": f"dominant repeat loop x{best}/{n}"}
    if uniq < 0.35:
        return {"degenerate": True, "reason": f"low lexical diversity (uniq={uniq:.2f})"}
    return {"degenerate": False, "reason": None}


def deloop(text):
    """Repair a LOCAL ASR loop: cap any run of identical consecutive words at 2 (e.g. '하기도'x7 -> x2).
    Output polish only; does not touch the gate. Natural double-emphasis ('정말 정말') survives."""
    ws = text.split()
    if not ws:
        return text
    out, run = [ws[0]], 1
    for w in ws[1:]:
        run = run + 1 if w == out[-1] else 1
        if run <= 2:
            out.append(w)
    return " ".join(out)


def load_model(name):
    from faster_whisper import WhisperModel
    try:
        return WhisperModel(name, device="cpu", compute_type="int8"), name
    except Exception as e:
        print(f"[refrecord] model '{name}' failed to load ({e}); falling back to '{FALLBACK_MODEL}'", flush=True)
        return WhisperModel(FALLBACK_MODEL, device="cpu", compute_type="int8"), FALLBACK_MODEL


def transcribe_once(wav_path, model_name, lang, prompt=None):
    m, used = load_model(model_name)
    # VAD OFF + no condition-carry: VAD wrongly drops voice buried under BGM; condition_on_previous_text
    # makes a model early-stop. These recover continuous narration that small+VAD silently lost.
    # initial_prompt (when given) primes register/domain -> measured +accuracy + fewer segment-drops.
    segments, info = m.transcribe(wav_path, vad_filter=False, language=lang,
                                  condition_on_previous_text=False, no_speech_threshold=0.6,
                                  beam_size=5, initial_prompt=prompt)
    segs = list(segments)   # materialize before freeing the model
    del m                   # free ctranslate2 model now so best-of-2 never holds two models at once
    import gc
    gc.collect()            # (peak RAM otherwise = large-v3 + medium + post-OCR pages -> OOM on 15GB)
    return segs, info, used


def strip_boilerplate(segs):
    """Drop segments that are exactly a known whisper non-speech hallucination phrase."""
    kept, dropped = [], []
    for s in segs:
        if _norm(s.text) in HALLUCINATION_BOILERPLATE:
            dropped.append(s.text.strip())
        else:
            kept.append(s)
    return kept, dropped


def coverage_gate(segs, info, rms):
    """LAYER-3: turn an incomplete/low-confidence transcript into an explicit status, not a silent pass."""
    voiced = [s for s in segs if s.no_speech_prob < 0.5]
    voiced_sec = sum(s.end - s.start for s in voiced)
    dur = float(info.duration or 0.0)
    ratio = round(voiced_sec / dur, 3) if dur else 0.0
    mlp = round(sum(s.avg_logprob for s in voiced) / len(voiced), 3) if voiced else None
    if voiced_sec < 0.8:
        status = "NO_SPEECH_OR_MASKED" if rms > 0.02 else "SILENT"   # instrumental, or VO fully masked -> escalate to tell apart
    elif ratio < 0.5 and rms > 0.02:
        status = "COVERAGE_GAP"        # audio not silent but speech sparse -> VO likely masked by BGM -> escalate
    elif mlp is not None and mlp < -1.0:
        status = "LOW_CONFIDENCE"      # transcript present but model unsure
    else:
        status = "OK"
    deg = degeneracy(segs)
    if deg["degenerate"] and status in {"OK", "LOW_CONFIDENCE"}:
        status = "DEGENERATE"          # high coverage but looping/garbage text -> gate would wrongly pass
    return {"status": status, "audio_sec": round(dur, 1), "voiced_sec": round(voiced_sec, 1),
            "coverage_ratio": ratio, "mean_logprob": mlp, "n_segments": len(segs),
            "degenerate_reason": deg["reason"]}


def demucs_available():
    try:
        import demucs  # noqa: F401
        import refsep   # noqa: F401  (our stdlib-saving separator)
        return True
    except Exception:
        return False


def tier2_recover(wav_path, outdir, lang, rms, prompt=None):
    """Demucs vocal-separation -> re-read with large-v3. MEASURED best for music-masked VO.
    Returns (segs, info, used, cov, method) or None if demucs is unavailable / errors."""
    if not demucs_available():
        return None
    try:
        import refsep
        voc = os.path.join(outdir, "vocals.wav")
        sep = refsep.separate_vocals(wav_path, voc, model_name=SEPARATION_MODEL)
        segs, info, used = transcribe_once(voc, ESCALATION_MODEL, lang, prompt=prompt or DOMAIN_PROMPT)
        segs, _ = strip_boilerplate(segs)
        cov = coverage_gate(segs, info, rms=sep.get("vocals_rms", rms))
        return segs, info, f"demucs+{used}", cov, {"sep": sep}
    except Exception as e:
        print(f"[refrecord] tier-2 demucs recovery failed: {e}", flush=True)
        return None


def main():
    seconds = float(sys.argv[1])
    out_id = sys.argv[2]
    model = sys.argv[3] if len(sys.argv) > 3 else PRIMARY_MODEL
    lang = sys.argv[4] if len(sys.argv) > 4 else "ko"
    outdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "refs", out_id)
    os.makedirs(outdir, exist_ok=True)
    wav_path = os.path.join(outdir, "audio.wav")

    spk = sc.default_speaker()
    loop = sc.get_microphone(spk.name, include_loopback=True)
    nframes = int(SR * seconds)
    print(f"[refrecord] recording {seconds}s WASAPI loopback from '{spk.name}' ...", flush=True)
    with loop.recorder(samplerate=SR, channels=1) as rec:
        data = rec.record(numframes=nframes)

    pcm = np.clip(data[:, 0], -1.0, 1.0)
    rms = float(np.sqrt(np.mean(pcm ** 2)))
    pcm16 = (pcm * 32767).astype('<i2')
    with wave.open(wav_path, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(pcm16.tobytes())
    print(f"[refrecord] wrote {wav_path}  rms={rms:.4f}", flush=True)
    if rms < 1e-4:
        print(json.dumps({"ok": False, "reason": "silence captured - is audio playing through the DEFAULT speaker?", "rms": rms}))
        return

    result = process_wav(wav_path, model, lang, rms, outdir)
    print(json.dumps({"ok": True, "rms": round(rms, 4), **result}, ensure_ascii=False))


def _accuracy_best_of_two(wav_path, lang, rms, prompt=None):
    """Run large-v3+prompt AND medium; return the non-degenerate, higher-coverage transcript (guards
    against large-v3 early-truncation on hard audio). Tie on coverage -> large-v3 (higher ceiling).
    `prompt` (DOMAIN_PROMPT + optional OCR on-screen-text hint) primes only the large-v3 pass."""
    cands = []
    for mdl, pr in [(ESCALATION_MODEL, prompt or DOMAIN_PROMPT), (PRIMARY_MODEL, None)]:
        s, i, u = transcribe_once(wav_path, mdl, lang, prompt=pr)
        s, _ = strip_boilerplate(s)
        c = coverage_gate(s, i, rms)
        cands.append((s, i, u, c))
    # rank: non-degenerate first, then coverage bucketed to 0.1, then large-v3 wins ties.
    cands.sort(key=lambda x: (x[3]["status"] != "DEGENERATE", round(x[3]["coverage_ratio"], 1),
                              x[2] == ESCALATION_MODEL), reverse=True)
    s, i, u, c = cands[0]
    other = cands[1]
    method = f"accuracy-best-of-2({u} over {other[2]}: cov {c['coverage_ratio']} vs {other[3]['coverage_ratio']})"
    return s, i, u, c, [], method


def process_wav(wav_path, model, lang, rms, outdir, ocr_hint=None):
    """Steps 2-5 of the pipeline (transcribe -> gate -> tier-2 -> decide -> write transcript).
    Pure of recording so it is unit-testable on any wav. Returns a JSON-safe result dict.
    ocr_hint: OCR'd on-screen text (file-based path) appended to the strong-model prompt. MEASURED:
    recovers ASR-dropped on-screen dialogue/captions (cod_news 90.1->95.2%), neutral on clean VO."""
    os.makedirs(outdir, exist_ok=True)   # self-contained: tier-2 vocals + transcript get written here
    strong_prompt = DOMAIN_PROMPT + (" " + ocr_hint if ocr_hint else "")
    if model == ESCALATION_MODEL:
        # ACCURACY MODE = ensemble-of-2. large-v3 has the highest ceiling (clean VO ~96%) BUT can
        # TRUNCATE on fast-VO-over-BGM (MEASURED: daiso haul - large-v3 stopped at ~half + hallucinated
        # an ending, while medium captured the full 30 segments). Run both and keep the non-degenerate,
        # higher-coverage one (truncation shows up as low coverage); tie -> large-v3 (higher ceiling).
        segs, info, used, cov, dropped, method = _accuracy_best_of_two(wav_path, lang, rms, strong_prompt)
    else:
        segs, info, used = transcribe_once(wav_path, model, lang)
        segs, dropped = strip_boilerplate(segs)
        cov = coverage_gate(segs, info, rms)
        method = "primary"

    # TIER-2 / ESCALATION when the gate flags a gap/garbage on real audio and we are not already strong.
    recovery = None
    if cov["status"] in {"COVERAGE_GAP", "NO_SPEECH_OR_MASKED", "LOW_CONFIDENCE", "DEGENERATE"} and used != ESCALATION_MODEL:
        alt = tier2_recover(wav_path, outdir, lang, rms, strong_prompt)   # measured-best: Demucs vocals + large-v3
        if alt is None:
            print(f"[refrecord] gate={cov['status']} -> escalating to {ESCALATION_MODEL} (raw; demucs unavailable)", flush=True)
            s2, i2, u2 = transcribe_once(wav_path, ESCALATION_MODEL, lang, prompt=strong_prompt)
            s2, _ = strip_boilerplate(s2)
            c2, m2 = coverage_gate(s2, i2, rms), f"{u2}-raw"
        else:
            print(f"[refrecord] gate={cov['status']} -> tier-2 demucs vocal-separation + {ESCALATION_MODEL}", flush=True)
            s2, i2, m2, c2, _meta = alt
        # A DEGENERATE primary has meaningless (often HIGH) coverage, so never decide on coverage alone:
        # a clean tier-2 result always beats degenerate garbage; never adopt a degenerate alt.
        alt_clean = c2["status"] != "DEGENERATE"
        if cov["status"] == "DEGENERATE":
            better = alt_clean
        else:
            better = alt_clean and (c2["coverage_ratio"] > cov["coverage_ratio"] + 0.1 or
                                    (cov["status"] == "NO_SPEECH_OR_MASKED" and c2["voiced_sec"] > 0.8))
        recovery = {"method": m2, "helped": bool(better), "before": cov, "after": c2}
        if better:
            segs, info, used, cov, method = s2, i2, m2, c2, m2

    header = (f"# transcript (lang={info.language}, model={used}, via={method}) - WASAPI loopback | "
              f"gate={cov['status']} coverage={cov['coverage_ratio']} "
              f"voiced={cov['voiced_sec']}/{cov['audio_sec']}s logprob={cov['mean_logprob']}")
    lines = [header] + [f"[{s.start:7.1f}-{s.end:7.1f}] {deloop(s.text.strip())}" for s in segs]
    with open(os.path.join(outdir, "transcript_timed.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return {"outdir": outdir, "model": used, "via": method, "coverage": cov,
            "recovery": recovery, "boilerplate_dropped": dropped,
            "text": " ".join(deloop(s.text.strip()) for s in segs)}


if __name__ == "__main__":
    main()
