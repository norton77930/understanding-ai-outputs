# PROTOTYPE — throwaway

**Question:** On this Windows machine, can an agent produce a ~20-second 3Blue1Brown-style explainer with ManimCE + narration, and which narration voice should be the default for English and for zh-TW?

**Short answer:** Yes. One command produced four narrated 720p30 explainers (binary search, 3 scenes) with audio-first sync, SRT subtitles and a comparison page, with no LaTeX or GPU. Voice defaults are provisional until someone listens (see "Voice notes").

## Run

```
# once: install (uv cache on D:, uses the existing Miniforge 3.12 so uv does not download a Python to C:)
env UV_CACHE_DIR=D:/uv-cache UV_PYTHON_DOWNLOADS=never uv sync --python C:/Users/NORTON.DENG/AppData/Local/miniforge3/python.exe
# once: download into models/ (from https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.1)
#   kokoro-v1.0.onnx, voices-v1.0.bin, kokoro-v1.1-zh.onnx, voices-v1.1-zh.bin
#   https://huggingface.co/hexgrad/Kokoro-82M-v1.1-zh/raw/main/config.json -> models/config-v1.1-zh.json

# the one command (all 4 variants; `run.py A C` for a subset)
env UV_CACHE_DIR=D:/uv-cache PYTHONUTF8=1 uv run python run.py
```

Outputs: `out/{A,B,C,D}.mp4`, `out/{A,B,C,D}.srt`, `out/compare.html`, `out/metrics.json`, preview frames in `out/frames/<variant>/`.

Pipeline (`run.py`): TTS per scene → append 0.35 s silence pad → measure each scene with ffprobe → write durations to `out/work/<v>/scene_config.json` → `scene.py` fits each scene's animations and waits to exactly that duration (weighted run_times, with a drift-correcting wait) → render at `-ql`, extract one frame per scene → render at `-qm` (720p30) → mux with ffmpeg (copy video, AAC audio) → SRT built from the scene text and durations.

## Results

| | A | B | C | D |
|---|---|---|---|---|
| Engine | kokoro-onnx 0.6.1, Kokoro v1.0 | kokoro-onnx 0.6.1, Kokoro v1.1-zh + misaki-fork[zh] G2P | edge-tts 7.2.8 (online) | Windows SAPI System.Speech |
| Voice | af_heart (en-US) | zf_001 (Mandarin) | zh-TW-HsiaoChenNeural | Microsoft Hanhan Desktop (zh-TW) |
| License | weights Apache-2.0, lib MIT, offline | weights Apache-2.0, offline | unofficial Edge Read-Aloud endpoint, ToS grey area, needs network | ships with Windows, offline |
| Narration (3 scenes incl. pads) | 18.9 s | 19.8 s | 26.4 s | 27.6 s |
| Speech rate | 168 wpm | 4.2 hanzi/s | 3.1 hanzi/s | 3.0 hanzi/s |
| TTS wall time (3 scenes, incl. model load) | 11.7 / 17.3 s | 14.7 / 25.0 s | 5.6 / 5.5 s | 14.9 / 20.8 s |
| Preview render `-ql` | 43 / 71 s | 45 / 89 s | 52 / 60 s | 43 / 88 s |
| Final render 720p30 `-qm` | 39 / 104 s | 93 / 57 s | 80 / 95 s | 54 / 55 s |
| Final mp4 | 19.0 s, 709 KB | 19.9 s, 720 KB | 26.6 s, 837 KB | 27.8 s, 884 KB |
| Whisper-small round-trip | verbatim | 3 homophone slips (有/由, 沒/每) | 3 slips (有/由, 牌/排, 沒/每) | 2 slips (有/由, 牌/排) |

Times are run 1 / run 2. The machine was under variable load (even `du` was slow during run 2), so render times vary by about 2x for the same 20 s clip; read them as a 40–100 s per render range. The whole pipeline (4 TTS + 8 renders + mux) took 9m23s wall in run 1. Final video is 0.1–0.18 s longer than its audio because of per-animation frame rounding (silent tail; harmless).

## Layout check (preview + vision loop)

I opened the `-ql` frames with an image-reading tool and judged them myself.

- **Before** (run 1, preserved in `out/frames_before/`): nothing was off-frame or clipped. The 16-box row spans about 45–810 px of the 854 px frame, and the zh labels rendered correctly in Microsoft JhengHei with no missing glyphs. Problems found: (1) scene 2 showed the previous caption ghosting behind the new one ("53 > 37: drop the right part" under "42 > 37: drop it"), because captions cross-faded at the same position; the extraction time (90% of the scene) also landed inside that cross-fade. (2) English used Manim's default serif font, whose old-style numerals made the box numbers sit at uneven heights.
- **Fix (once):** caption swaps became `Succession(FadeOut(old), FadeIn(new))`, English uses Segoe UI, and frames are sampled 0.2 s before the scene end (inside the final hold).
- **After** (run 2, `out/frames/`): no ghosting, numerals are even, and all 12 frames are clean. Remaining cosmetic issue, left as is: a large empty band between the title and the box row.
- Verdict: the loop works. One look at 12 low-res frames caught a real transition defect and a typography issue, and one re-render fixed both.

## Install footprint and pain (all on D:)

- `uv sync`: 13m45s, network-bound. Every package installed from binary wheels, including pycairo 1.29.2, manimpango 0.7.0, skia-pathops and av. jieba was built from an sdist (pure Python, fine). No compiler, no LaTeX, no system PATH change.
- `.venv` 516 MB; uv cache `D:/uv-cache` 0 → 596 MB. uv hardlinks on the same drive, so the real combined usage is about 600 MB, not 1.1 GB.
- Kokoro models 701 MB (2 × 311 MB onnx + 27 MB + 52 MB voices), downloaded in 8m23s. Optional Whisper-small for the round-trip check: 464 MB in `models/whisper`.
- `out/` is about 32 MB including intermediate renders.
- C: impact: jieba writes a small dictionary cache to `%TEMP%`; the first `uv run` import took about 2 minutes (bytecode compile and AV scanning). Nothing else went to C:.
- Pain points: none blocking. `PYTHONUTF8=1` set as a precaution. SAPI text goes through a UTF-8 temp file into PowerShell to avoid console code-page issues. pydub and jieba emit SyntaxWarnings on 3.12 (cosmetic). misaki prints "en_callable is None, so English may be removed", so keep Latin text out of zh narration. Digits are fine: 37 becomes 三十七. One run stopped silently during C's final render. The error was hidden by an output filter, and the immediate re-run of C and D succeeded, so the cause is unknown; possibly a transient Windows file lock.

## Voice notes (objective only, nobody has listened yet)

- **English → Kokoro af_heart (A)**: offline, Apache-2.0, 168 wpm (natural explainer pace), and Whisper transcribed it verbatim. Provisional default.
- **zh-TW**:
  - **C edge-tts HsiaoChen** is the only neural voice here that is actually a Taiwan (zh-TW) locale voice, and it was the fastest TTS. Downsides: needs the network, unofficial endpoint, no SLA.
  - **B Kokoro zf_001** is offline and Apache-2.0, but the v1.1-zh model and misaki/pypinyin are mainland-Mandarin. Words with Taiwan-specific readings (e.g. 星期 qí/qī, 垃圾 lèsè/lājī, 和 hàn/hé, 企業 qì/qǐ) will get mainland pronunciation. This script avoided them, so the risk did not show here. It also speaks fastest (4.2 hanzi/s vs about 3.0), which may sound rushed.
  - **D SAPI Hanhan** is offline and free, but it is a legacy pre-neural voice. Expect robotic prosody.
  - Provisional zh-TW default: **C**, with **B** as the offline fallback. Confirm by listening in `out/compare.html`.
- The zh narration runs 26–28 s at natural rates (C, D), so for a ~20 s target the zh script needs to be about 25% shorter, or the rate raised (edge-tts `rate="+15%"`).
- Whisper's slips (由→有, 每→沒, 排→牌) are tone-only homophone confusions. They appear across engines, so they are weak evidence about any single TTS.
