"""PROTOTYPE (throwaway). BreezyVoice CPU runner, called by ../run.py in its own Py3.10 venv.

Usage: python tts.py JOBS_JSON
JOBS_JSON = {"jobs": [{"text": ..., "out": ...wav}, ...]}. Loads the model once, synthesizes every job,
prints one JSON line `RESULT {...}` with load time and per-job wall time / audio length.

Text normalization: ttsfrd is Linux-only and WeTextProcessing needs pynini (no Windows wheel), so a stub
`tn` package is injected below. It only turns Arabic integers into Chinese numerals (37 -> 三十七);
our script text is otherwise clean. Vendored code is not patched.
"""
import json
import os
import re
import sys
import time
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROTO = HERE.parent
VENDOR = PROTO / "vendor" / "BreezyVoice"
MODEL = PROTO / "models" / "breezyvoice"
SPEAKER_WAV = VENDOR / "data" / "example.wav"
# transcription of data/example.wav as given in the BreezyVoice README
SPEAKER_TEXT = "在密碼學中，加密是將明文資訊改變為難以讀取的密文內容，使之不可讀的方法。只有擁有解密方法的對象,經由解密過程才能將密文還原為正常可讀的內容。"

DIG = "零一二三四五六七八九"


def num2zh(n: int) -> str:
    if n < 10:
        return DIG[n]
    if n < 100:
        t, o = divmod(n, 10)
        return ("" if t == 1 else DIG[t]) + "十" + (DIG[o] if o else "")
    return "".join(DIG[int(c)] for c in str(n))  # digit-by-digit fallback, not needed for this script


class _StubNormalizer:
    def __init__(self, *a, **k):
        pass

    def normalize(self, text):
        return re.sub(r"\s*(\d+)\s*", lambda m: num2zh(int(m.group(1))), text)


for name in ("tn", "tn.chinese", "tn.english", "tn.chinese.normalizer", "tn.english.normalizer"):
    sys.modules[name] = types.ModuleType(name)
sys.modules["tn.chinese.normalizer"].Normalizer = _StubNormalizer
sys.modules["tn.english.normalizer"].Normalizer = _StubNormalizer

sys.path[:0] = [str(VENDOR), str(VENDOR / "third_party" / "Matcha-TTS")]


def main():
    jobs = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))["jobs"]
    t0 = time.perf_counter()
    import torch
    import torchaudio
    import single_inference as si  # vendored; sets torch threads to 1
    torch.set_num_threads(int(os.environ.get("BREEZY_THREADS", os.cpu_count() or 4)))
    from g2pw import G2PWConverter
    from cosyvoice.utils.file_utils import load_wav
    cv = si.CustomCosyVoice(str(MODEL))
    conv = G2PWConverter()
    prompt16k = load_wav(str(SPEAKER_WAV), 16000)
    ptext = si.get_bopomofo_rare(cv.frontend.text_normalize_new(SPEAKER_TEXT, split=False), conv)
    load_s = time.perf_counter() - t0
    print(f"[breezy] loaded in {load_s:.1f}s, threads={torch.get_num_threads()}", flush=True)
    res = []
    for j in jobs:
        t1 = time.perf_counter()
        text = si.get_bopomofo_rare(cv.frontend.text_normalize_new(j["text"], split=False), conv)
        print(f"[breezy] synth: {text}", flush=True)
        out = cv.inference_zero_shot_no_normalize(text, ptext, prompt16k)
        torchaudio.save(j["out"], out["tts_speech"], 22050)
        dt = time.perf_counter() - t1
        audio = out["tts_speech"].shape[1] / 22050
        res.append(dict(text=text, wall_s=round(dt, 2), audio_s=round(audio, 3), rtf=round(dt / audio, 2)))
        print(f"[breezy] {dt:.1f}s wall for {audio:.2f}s audio (RTF {dt / audio:.2f})", flush=True)
    print("RESULT " + json.dumps(dict(load_s=round(load_s, 2), jobs=res), ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
