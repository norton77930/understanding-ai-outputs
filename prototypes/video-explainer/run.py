"""PROTOTYPE (throwaway). One command: `uv run python run.py`
TTS (4 variants) -> measure durations -> Manim preview (-ql) + frames -> final 720p30 -> mux + srt -> compare.html.
Optional: `uv run python run.py A C` renders only the listed variants."""
import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path

os.environ.setdefault("PYTHONUTF8", "1")
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out"
MODELS = ROOT / "models"
SCRIPT = json.loads((ROOT / "script.json").read_text(encoding="utf-8"))
PAD = 0.35  # seconds of silence appended to each scene's narration
ZH_FONT = "Microsoft JhengHei"

VARIANTS = {
    "A": dict(engine="kokoro-onnx v1.0", voice="af_heart", lang="en", font="Segoe UI",
              license="Kokoro-82M weights Apache-2.0; kokoro-onnx MIT; offline"),
    "B": dict(engine="kokoro-onnx v1.1-zh", voice="zf_001", lang="zh", font=ZH_FONT,
              license="Kokoro-82M-v1.1-zh weights Apache-2.0; offline; Mandarin (mainland-trained)"),
    "C": dict(engine="edge-tts (Azure neural, online)", voice="zh-TW-HsiaoChenNeural", lang="zh", font=ZH_FONT,
              license="Unofficial use of Edge Read-Aloud endpoint; no SLA, ToS grey area; needs internet"),
    "D": dict(engine="Windows SAPI (System.Speech)", voice="Microsoft Hanhan Desktop", lang="zh", font=ZH_FONT,
              license="Ships with Windows; offline; legacy concatenative/HMM quality"),
}


def sh(cmd):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")


def ffdur(p):
    return float(sh(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]).stdout.strip())


# ---------- TTS ----------
_kok = {}


def kokoro_en(text, path):
    from kokoro_onnx import Kokoro
    import soundfile as sf
    if "en" not in _kok:
        _kok["en"] = Kokoro(str(MODELS / "kokoro-v1.0.onnx"), str(MODELS / "voices-v1.0.bin"))
    samples, sr = _kok["en"].create(text, voice="af_heart", speed=1.0, lang="en-us")
    sf.write(path, samples, sr)


def kokoro_zh(text, path):
    from kokoro_onnx import Kokoro
    from misaki import zh
    import soundfile as sf
    if "zh" not in _kok:
        _kok["zh"] = Kokoro(str(MODELS / "kokoro-v1.1-zh.onnx"), str(MODELS / "voices-v1.1-zh.bin"),
                            vocab_config=str(MODELS / "config-v1.1-zh.json"))
        _kok["g2p"] = zh.ZHG2P(version="1.1")
    ph, _ = _kok["g2p"](text)
    samples, sr = _kok["zh"].create(ph, voice="zf_001", speed=1.0, is_phonemes=True)
    sf.write(path, samples, sr)


def edge(text, path):
    import edge_tts
    asyncio.run(edge_tts.Communicate(text, "zh-TW-HsiaoChenNeural").save(str(path)))


def sapi(text, path):
    tf = Path(str(path) + ".txt")
    tf.write_text(text, encoding="utf-8")
    sh(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "sapi_tts.ps1"),
        "-TextFile", str(tf), "-OutWav", str(path), "-Voice", "Microsoft Hanhan Desktop"])
    tf.unlink()


TTS = {"A": (kokoro_en, "wav"), "B": (kokoro_zh, "wav"), "C": (edge, "mp3"), "D": (sapi, "wav")}


def do_tts(v, d):
    fn, ext = TTS[v]
    text_key = VARIANTS[v]["lang"]
    t0 = time.perf_counter()
    raws = []
    for i, s in enumerate(SCRIPT["scenes"]):
        p = d / f"raw_s{i + 1}.{ext}"
        fn(s[text_key], p)
        raws.append(p)
    tts_s = time.perf_counter() - t0
    # normalize to 48k mono wav + pad, then measure (audio-first: these durations drive the animation)
    durs, speech = [], []
    for i, p in enumerate(raws):
        speech.append(ffdur(p))
        n = d / f"s{i + 1}.wav"
        sh(["ffmpeg", "-y", "-v", "error", "-i", str(p), "-af", f"apad=pad_dur={PAD}", "-ar", "48000", "-ac", "1", str(n)])
        durs.append(ffdur(n))
    lst = d / "concat.txt"
    lst.write_text("".join(f"file 's{i + 1}.wav'\n" for i in range(len(raws))), encoding="utf-8")
    sh(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(d / "narration.wav")])
    return tts_s, durs, speech


# ---------- Manim ----------
def render(v, d, durs, quality):
    cfg = d / "scene_config.json"
    cfg.write_text(json.dumps({"script": str(ROOT / "script.json"), "lang": VARIANTS[v]["lang"],
                               "font": VARIANTS[v]["font"], "durations": durs}), encoding="utf-8")
    env = dict(os.environ, VE_CONFIG=str(cfg), PYTHONUTF8="1")
    media = d / f"media_{quality}"
    t0 = time.perf_counter()
    subprocess.run([sys.executable, "-m", "manim", "render", f"-q{quality}", "--disable_caching", "--progress_bar", "none",
                    "--media_dir", str(media), "-o", f"{v}_{quality}.mp4", str(ROOT / "scene.py"), "Explainer"],
                   check=True, env=env, cwd=str(d), capture_output=True)
    dt = time.perf_counter() - t0
    vid = next(media.rglob(f"{v}_{quality}.mp4"))
    return dt, vid


def frames(v, vid, durs):
    fd = OUT / "frames" / v
    fd.mkdir(parents=True, exist_ok=True)
    start = 0.0
    for i, du in enumerate(durs):
        t = start + du - 0.2  # inside the scene's final hold: all elements settled (0.9*du hit a cross-fade)
        sh(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.3f}", "-i", str(vid), "-frames:v", "1", str(fd / f"scene{i + 1}.png")])
        start += du


def srt(v, durs):
    def ts(x):
        ms = int(round(x * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    out, t = [], 0.0
    for i, (s, du) in enumerate(zip(SCRIPT["scenes"], durs)):
        out.append(f"{i + 1}\n{ts(t)} --> {ts(t + du - PAD)}\n{s[VARIANTS[v]['lang']]}\n")
        t += du
    (OUT / f"{v}.srt").write_text("\n".join(out), encoding="utf-8")


def mux(v, vid, d):
    o = OUT / f"{v}.mp4"
    sh(["ffmpeg", "-y", "-v", "error", "-i", str(vid), "-i", str(d / "narration.wav"), "-map", "0:v", "-map", "1:a",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", str(o)])
    return o


def html(m):
    cards = []
    for v, r in m.items():
        meta = VARIANTS[v]
        cards.append(f"""<div class=c><h2>{v}: {meta['voice']}</h2><video controls preload=metadata src="{v}.mp4"></video>
<table><tr><th>Engine</th><td>{meta['engine']}</td></tr><tr><th>License</th><td>{meta['license']}</td></tr>
<tr><th>TTS time</th><td>{r['tts_s']:.1f} s</td></tr><tr><th>Narration</th><td>{r['total_s']:.1f} s ({r['rate']})</td></tr>
<tr><th>Render</th><td>preview {r['render_ql_s']:.1f} s, final {r['render_qm_s']:.1f} s</td></tr>
<tr><th>File size</th><td>{r['mp4_kb']} KB</td></tr></table></div>""")
    (OUT / "compare.html").write_text(f"""<!doctype html><meta charset=utf-8><title>Narration voice comparison (prototype)</title>
<style>body{{font-family:sans-serif;background:#111;color:#eee}}.g{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}
video{{width:100%}}table{{font-size:13px}}th{{text-align:left;padding-right:8px;color:#aaa}}h2{{font-size:16px}}</style>
<h1>Binary search explainer: 4 narration voices (PROTOTYPE)</h1><div class=g>{''.join(cards)}</div>""", encoding="utf-8")


def main():
    picks = sys.argv[1:] or list(VARIANTS)
    OUT.mkdir(exist_ok=True)
    mpath = OUT / "metrics.json"
    metrics = json.loads(mpath.read_text(encoding="utf-8")) if mpath.exists() else {}
    for v in picks:
        d = OUT / "work" / v
        d.mkdir(parents=True, exist_ok=True)
        print(f"[{v}] TTS {VARIANTS[v]['voice']} ...", flush=True)
        tts_s, durs, speech = do_tts(v, d)
        print(f"[{v}] tts {tts_s:.1f}s durations {[round(x, 2) for x in durs]}", flush=True)
        ql_s, ql_vid = render(v, d, durs, "l")
        frames(v, ql_vid, durs)
        print(f"[{v}] preview {ql_s:.1f}s, frames in out/frames/{v}", flush=True)
        qm_s, qm_vid = render(v, d, durs, "m")
        print(f"[{v}] final 720p30 {qm_s:.1f}s", flush=True)
        o = mux(v, qm_vid, d)
        srt(v, durs)
        texts = [s[VARIANTS[v]["lang"]] for s in SCRIPT["scenes"]]
        if VARIANTS[v]["lang"] == "en":
            rate = f"{sum(len(t.split()) for t in texts) / sum(speech) * 60:.0f} wpm"
        else:
            rate = f"{sum(sum(1 for ch in t if '一' <= ch <= '鿿') for t in texts) / sum(speech):.1f} hanzi/s"
        metrics[v] = dict(voice=VARIANTS[v]["voice"], tts_s=round(tts_s, 2), scene_s=[round(x, 3) for x in durs],
                          speech_s=[round(x, 3) for x in speech], total_s=round(sum(durs), 3), rate=rate,
                          render_ql_s=round(ql_s, 1), render_qm_s=round(qm_s, 1),
                          video_s=round(ffdur(qm_vid), 3), mp4_s=round(ffdur(o), 3), mp4_kb=o.stat().st_size // 1024)
        mpath.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[{v}] -> {o}", flush=True)
    html({k: metrics[k] for k in sorted(metrics)})
    print(json.dumps(metrics, indent=2, ensure_ascii=False))
    print(f"compare: {OUT / 'compare.html'}")


if __name__ == "__main__":
    main()
