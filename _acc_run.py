# generalize the accuracy check to any clean-VO clip. Downloads audio + Google auto-caption,
# transcribes with medium / large-v3 / large-v3+styleprompt / large-v3+wordprompt, computes
# cross-vendor symmetric agreement (whisper vs Google) = true-accuracy estimate. Saves per-clip JSON.
# Usage: python _acc_run.py <youtube_id> <tag>
import json, re, os, sys, subprocess
import refrecord as R

vid, tag = sys.argv[1], sys.argv[2]
D = f"refs/_acc/{tag}"
os.makedirs(D, exist_ok=True)
url = f"https://www.youtube.com/watch?v={vid}"
PY = sys.executable

# domain priming prompts. STYLE = generic register (no content words -> cannot parrot content).
# WORD = generic fashion-review vocabulary (mild parrot risk, broader coverage).
STYLE = "다음은 한국어 패션 제품 비교 리뷰 영상의 또박또박한 여성 내레이션입니다."
WORD = "패션 비교 리뷰. 캡소매, 넥라인, 핏, 가성비, 내돈내산, 슬림핏, 오버핏, 스퀘어넥, 라운드넥, 기장감, 소매통."

if not os.path.exists(f"{D}/audio.wav"):
    subprocess.run([PY, "-m", "yt_dlp", "-f", "best[height<=720][ext=mp4]/best[height<=720]/best",
                    "-o", f"{D}/v.%(ext)s", "--no-playlist", url], check=True)
    subprocess.run([PY, "-m", "yt_dlp", "--skip-download", "--write-auto-subs", "--sub-langs", "ko",
                    "--convert-subs", "srt", "-o", f"{D}/auto", "--no-playlist", url], check=False)
    subprocess.run(["ffmpeg", "-y", "-i", f"{D}/v.mp4", "-vn", "-ac", "2", "-ar", "44100",
                    f"{D}/audio.wav", "-loglevel", "error"], check=True)

def srt_text(path):
    if not os.path.exists(path): return ""
    out = []
    for ln in open(path, encoding="utf-8"):
        ln = ln.strip()
        if ln and not ln.isdigit() and "-->" not in ln:
            if not out or out[-1] != ln: out.append(ln)
    return " ".join(out)

def tx(model, prompt=None):
    m, used = R.load_model(model)
    segs, info = m.transcribe(f"{D}/audio.wav", vad_filter=False, language="ko",
                              condition_on_previous_text=False, no_speech_threshold=0.6,
                              beam_size=5, initial_prompt=prompt)
    return " ".join(s.text.strip() for s in list(segs))

def norm(s): return re.sub(r"[^가-힣a-z0-9]", "", s.lower())
def cer(a, b):
    r, h = norm(a), norm(b)
    if not r: return None
    if len(r) < len(h): r, h = h, r
    prev = list(range(len(h)+1))
    for i, rc in enumerate(r, 1):
        cur = [i]
        for j, hc in enumerate(h, 1):
            cur.append(min(prev[j]+1, cur[j-1]+1, prev[j-1]+(rc != hc)))
        prev = cur
    return prev[-1]/max(1, len(norm(a)))
def sym(a, b): return (cer(a, b)+cer(b, a))/2

T = {"google": srt_text(f"{D}/auto.ko.srt"), "medium": tx("medium"),
     "large-v3": tx("large-v3"), "large-v3+style": tx("large-v3", STYLE),
     "large-v3+word": tx("large-v3", WORD)}
agree = {f"{k} vs google": (None if not T["google"] else round(100*(1-sym(T[k], T["google"])), 1))
         for k in ["medium", "large-v3", "large-v3+style", "large-v3+word"]}
res = {"tag": tag, "id": vid, "google_chars": len(norm(T["google"])),
       "agreement_vs_google_pct": agree, "transcripts": T}
json.dump(res, open(f"{D}/_acc.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"[{tag}] agreement vs google:", json.dumps(agree, ensure_ascii=False))
