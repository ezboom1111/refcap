#!/usr/bin/env python
# colorprofile - quantitative color/look profile of a reference from its frames (Pillow only).
# Dominant palette + average saturation/brightness + contrast -> color.json (the "color grade" data layer).
# Usage: python colorprofile.py <frames_dir> [out.json]
import sys, os, glob, json
from collections import Counter
from PIL import Image, ImageStat


def hexc(c):
    return "#%02x%02x%02x" % (c[0], c[1], c[2])


def main():
    frames_dir = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.normpath(frames_dir)), "color.json")
    files = sorted(glob.glob(os.path.join(frames_dir, "*.jpg")))
    if not files:
        print(json.dumps({"error": "no frames in " + frames_dir})); return
    if len(files) > 12:
        step = len(files) / 12.0
        files = [files[min(len(files) - 1, int(i * step))] for i in range(12)]
    pal = Counter()
    S, V, Vstd = [], [], []
    for f in files:
        im = Image.open(f).convert("RGB").resize((160, 284))
        q = im.quantize(colors=6).convert("RGB")
        for cnt, col in q.getcolors(160 * 284):
            pal[col] += cnt
        hsv = im.convert("HSV")
        st = ImageStat.Stat(hsv)
        S.append(st.mean[1]); V.append(st.mean[2]); Vstd.append(st.stddev[2])
    total = sum(pal.values()) or 1
    palette = [{"hex": hexc(c), "weight": round(n / total, 3)} for c, n in pal.most_common(6)]
    res = {
        "frameSamples": len(files),
        "palette": palette,
        "brightness_0_255": round(sum(V) / len(V), 1),
        "saturation_0_255": round(sum(S) / len(S), 1),
        "contrast_Vstddev": round(sum(Vstd) / len(Vstd), 1),
    }
    with open(out_path, "w", encoding="utf-8") as fp:
        json.dump(res, fp, ensure_ascii=False, indent=2)
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
