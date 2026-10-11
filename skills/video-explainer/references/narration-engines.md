# Narration engines

A **Narration engine** turns the narration into audio. One engine offers one or more voices. The selection rules are in `select_engine()` in `scripts/make_video.py`.

## Engines in v1

| Engine | Network | Default for | Default voice | Model download |
| --- | --- | --- | --- | --- |
| `kokoro` | No (offline) | English; offline fallback for zh-TW | `af_heart` (en), `zf_001` (zh) | `kokoro-en` about 354 MB, `kokoro-zh` about 379 MB |
| `edge-tts` | Yes | zh-TW | `zh-TW-HsiaoChenNeural` (Taiwan accent) | None |
| `elevenlabs` | Yes (paid) | Nothing: only when the storyboard names it | None: the user gives a voice ID | None |
| `silent` | No | Tests only | None | None |

Other Kokoro voices by language: `en-gb` `bf_emma`, `es` `ef_dora`, `fr` `ff_siwis`, `hi` `hf_alpha`, `it` `if_sara`, `ja` `jf_alpha`, `pt` `pf_dora`. Other languages are best effort through these voices.

## Selection

1. An engine or voice named in the storyboard wins. There is no automatic fallback for it.
2. zh-TW uses edge-tts. When edge-tts is unreachable, it falls back to Kokoro Chinese (`zf_001`) and adds a notice: the accent is mainland Mandarin, not Taiwan. `plan` assumes the network works unless you pass `--offline`. `preview` and `final` check the network for real.
3. Any other language uses Kokoro when it has a voice for that language.
4. Otherwise `plan` exits 1. Ask the user for an engine and voice.

Override examples:

- `"engine": "kokoro"`: Kokoro with the default voice for `lang`.
- `"engine": {"name": "kokoro", "voice": "bf_emma"}`: a specific voice.
- `"engine": {"name": "edge-tts", "voice": "zh-TW-YunJheNeural"}`: another edge-tts voice.
- `"engine": {"name": "elevenlabs", "voice": "<voice_id>"}`: ElevenLabs with a voice ID from the user's ElevenLabs voice library.

## ElevenLabs

- Named only. A set `ELEVENLABS_API_KEY` never changes the automatic selection.
- The model is `eleven_multilingual_v2`. The voice ID is required. Without it, `plan` exits 1.
- The key comes only from the `ELEVENLABS_API_KEY` environment variable. Never put it in the storyboard: `plan` exits 1 for an engine field that looks like a credential (`key`, `token`, `secret`, `auth`). The doctor reports only whether the variable is set.
- `plan` makes no network call. It reports `narration_cost`: the narration characters, the estimated credits (1 credit per character) and a price note. Without the key, `plan` adds a notice. `preview` and `final` then stop with exit 2.
- Narration audio is cached. `final` reuses the audio from `preview`, so you pay once. The cache does not depend on the key.
- Chinese length estimates use the default rate of 3.05 characters per second (not measured for ElevenLabs).

## Models

Kokoro model files live in the user cache folder (`VIDEO_EXPLAINER_CACHE`, else the OS user cache), never in the project. `plan` lists missing files in `downloads` with their size. Ask the user before you download. Then run `make_video.py fetch-models kokoro-en` or `kokoro-zh`. `preview` and `final` never download. They stop with exit 2 when a model is missing.

## Before you publish

Read this before you upload a video to YouTube, Shorts, Reels or any public channel. This is not legal advice. Check the current terms yourself.

- **edge-tts** uses Microsoft Edge's read-aloud service through an unofficial endpoint. It has no service terms for this use. Microsoft can change or block it at any time. This is a risk for a monetized channel. `plan` adds a notice for the `youtube` and `short` presets.
  - **Official route to the same voice:** Azure AI Speech offers `zh-TW-HsiaoChenNeural` under Microsoft's service terms, with a monthly free tier. v1 has no Azure engine. Generate the audio there yourself, or switch to Kokoro.
  - **Offline route:** set `"engine": "kokoro"`. The Chinese accent is then mainland Mandarin.
- **Kokoro** (Kokoro-82M weights, run through kokoro-onnx) is licensed Apache-2.0. Commercial use is allowed. Keep the licence notice if you redistribute the model files.
- **BreezyVoice** (MediaTek Research) is an optional advanced route to an offline Taiwan accent. v1 does not include it. You run it yourself and need a custom engine to use its audio.
  - It is slow on a CPU. In our test the real-time factor was about 33: 10 seconds of speech took about 5.5 minutes. A GPU makes it much faster.
  - It clones the voice of a speaker recording. Use a recording that you have the rights to, such as your own voice. The rights to the example voice in its repository are unclear. Do not publish with it.
  - Check the licence of its code and model before you publish.
- **ElevenLabs**: the free plan has no commercial licence and needs "elevenlabs.io" in the title of each published video. Paid plans include a commercial licence. `plan` adds a notice for the `youtube` and `short` presets.
