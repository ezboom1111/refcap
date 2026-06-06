#!/usr/bin/env python
# refsep - Demucs vocal separation that writes WAV via the stdlib (torchaudio 2.x needs torchcodec to
# save, which is brittle on Windows; we bypass it). htdemucs is 44.1kHz stereo native, matching our
# ffmpeg-extracted clips, so no resample. Use this to strip BGM before ASR on music-dominant VO.
# Usage: python refsep.py <in.wav> <out_vocals.wav>  |  or import separate_vocals(in,out)->dict
import sys, os, wave
import numpy as np
import torch


def _read_wav(path):
    with wave.open(path, "rb") as w:
        sr, ch, n = w.getframerate(), w.getnchannels(), w.getnframes()
        a = np.frombuffer(w.readframes(n), dtype="<i2").astype("float32") / 32768.0
    a = a.reshape(-1, ch).T  # [channels, samples]
    return a, sr, ch


def _save_wav(path, a, sr):
    a = np.clip(a, -1.0, 1.0)
    if a.ndim == 1:
        a = a[None, :]
    pcm = (a.T * 32767.0).astype("<i2")  # interleave channels
    with wave.open(path, "wb") as w:
        w.setnchannels(a.shape[0]); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def separate_vocals(in_path, out_path, model_name="htdemucs"):
    from demucs.pretrained import get_model
    from demucs.apply import apply_model
    model = get_model(model_name)
    model.eval()
    a, sr, ch = _read_wav(in_path)
    wav = torch.from_numpy(a)
    if wav.shape[0] == 1:
        wav = wav.repeat(model.audio_channels, 1)  # mono -> model channels (htdemucs=2)
    ref = wav.mean(0)
    mean, std = ref.mean(), ref.std()
    wav_n = (wav - mean) / (std + 1e-8)
    with torch.no_grad():
        sources = apply_model(model, wav_n[None], device="cpu", progress=True,
                              split=True, overlap=0.25)[0]
    sources = sources * std + mean
    vocals = sources[model.sources.index("vocals")].cpu().numpy()  # [ch, samples]
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    _save_wav(out_path, vocals, sr)
    voc_rms = float((vocals ** 2).mean() ** 0.5)
    mix_rms = float((a ** 2).mean() ** 0.5)
    return {"out": out_path, "sr": sr, "model": model_name,
            "vocals_rms": round(voc_rms, 4), "mix_rms": round(mix_rms, 4),
            "vocal_energy_ratio": round(voc_rms / mix_rms, 3) if mix_rms else None}


if __name__ == "__main__":
    info = separate_vocals(sys.argv[1], sys.argv[2])
    import json
    print(json.dumps(info, ensure_ascii=False))
