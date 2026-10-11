"""Tests for the ElevenLabs narration engine in make_video.py (issue #45).

The engine handles a user credential, so most tests check where the key goes:
only into the xi-api-key request header, never into output, files, errors,
the cache key or subprocesses. No test talks to the real ElevenLabs API: a
local http.server stands in for it through ELEVENLABS_API_BASE. The key is a
sentinel value, never a real key.

Engine tests import make_video in this process. CLI tests run it as a
subprocess with fake uv/ffmpeg/ffprobe, and `preview`/`final` replace the
ManimCE render with a stub, so no ManimCE, ffmpeg or network is needed.
"""

import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "skills" / "video-explainer" / "scripts"
SCRIPT = SCRIPTS / "make_video.py"
DOCTOR = SCRIPTS / "doctor.py"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import make_video  # noqa: E402

SENTINEL = "sk_TESTSENTINEL_0123456789abcdef"
OTHER_KEY = "sk_OTHERSENTINEL_fedcba9876543210"
VOICE = "21m00Tcm4TlvDq8ikWAM"
FAKE_MP3 = b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\xff\xfb\x90\x00" * 64
NO_PROXY = "127.0.0.1,localhost"
KEY_VARS = ("ELEVENLABS_API_KEY", "ELEVENLABS_API_BASE")


class FakeElevenLabs:
    """Local stand-in for the ElevenLabs API. `mode` sets the reply."""

    def __init__(self, mode="ok", delay=0.0):
        self.mode, self.delay, self.requests = mode, delay, []
        fake = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                self.handle_request("GET")

            def do_POST(self):
                self.handle_request("POST")

            def handle_request(self, method):
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length) if length else b""
                fake.requests.append({"method": method, "path": self.path,
                                      "headers": dict(self.headers.items()), "body": body})
                if fake.delay:
                    time.sleep(fake.delay)
                fake.reply(self)

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.handle_error = lambda *args: None  # a client that gave up
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()

    def reply(self, handler):
        mode = self.mode
        if mode == "drop":  # close the connection without a reply
            handler.close_connection = True
            return
        headers_text = json.dumps(self.requests[-1]["headers"])
        sent_key = {k.lower(): v for k, v in self.requests[-1]["headers"].items()}.get(
            "xi-api-key", "")
        replies = {
            "ok": (200, "audio/mpeg", FAKE_MP3),
            "401": (401, "application/json", json.dumps(
                {"detail": {"status": "invalid_api_key", "message": "Invalid API key"}})),
            "422": (422, "application/json", json.dumps(
                {"detail": {"status": "voice_not_found", "message": "bad voice"}})),
            "429": (429, "application/json", json.dumps(
                {"detail": {"code": "too_many_concurrent_requests"}})),
            "500": (500, "text/plain", "Internal Server Error " + headers_text),
            # Echoes every request header (the key included) in the error body
            # and in the detail fields that the engine reports.
            "echo": (400, "application/json", json.dumps(
                {"detail": {"status": sent_key,
                            "code": headers_text, "message": headers_text}})),
            "redirect": (302, "text/plain", ""),
        }
        status, ctype, body = replies[mode]
        if isinstance(body, str):
            body = body.encode("utf-8")
        handler.send_response(status)
        handler.send_header("Content-Type", ctype)
        handler.send_header("Content-Length", str(len(body)))
        if mode == "redirect":
            handler.send_header("Location", "/leak")
        handler.end_headers()
        handler.wfile.write(body)


def start_fake(test, mode="ok", delay=0.0):
    fake = FakeElevenLabs(mode, delay)
    test.addCleanup(fake.close)
    return fake


def clean_env(**extra):
    """os.environ without ElevenLabs settings, plus extra."""
    env = {k: v for k, v in os.environ.items() if k.upper() not in KEY_VARS}
    env.update(NO_PROXY=NO_PROXY, no_proxy=NO_PROXY, PYTHONUTF8="1")
    env.update(extra)
    return env


def files_containing(root, needle):
    data = needle.encode("utf-8")
    return [str(p) for p in Path(root).rglob("*")
            if needle in str(p) or (p.is_file() and data in p.read_bytes())]


# ---------------------------------------------------------------- engine (in process)

class EngineTests(unittest.TestCase):
    """ElevenLabsEngine.synthesize() and the cache, against the fake server."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.engine = make_video.ENGINES["elevenlabs"]

    def env(self, fake, key=SENTINEL):
        values = clean_env(ELEVENLABS_API_BASE=fake.base)
        if key is not None:
            values["ELEVENLABS_API_KEY"] = key
        return mock.patch.dict(os.environ, values, clear=True)

    def synthesize_error(self, mode, **kwargs):
        fake = start_fake(self, mode, **kwargs)
        with self.env(fake):
            with self.assertRaises(RuntimeError) as caught:
                self.engine.synthesize("Hello there.", "en", VOICE, self.tmp / "a.mp3")
        return fake, caught.exception

    def test_success_writes_the_mp3_and_sends_the_key_only_in_the_header(self):
        fake = start_fake(self)
        path = self.tmp / "a.mp3"
        with self.env(fake):
            self.engine.synthesize("Hello there.", "en", VOICE, path)
        self.assertEqual(path.read_bytes(), FAKE_MP3)
        self.assertEqual(len(fake.requests), 1)
        request = fake.requests[0]
        self.assertEqual(request["method"], "POST")
        self.assertEqual(request["path"],
                         f"/v1/text-to-speech/{VOICE}?output_format=mp3_44100_128")
        headers = {k.lower(): v for k, v in request["headers"].items()}
        self.assertEqual(headers["xi-api-key"], SENTINEL)
        self.assertEqual(json.loads(request["body"]),
                         {"text": "Hello there.", "model_id": "eleven_multilingual_v2"})
        # Only the xi-api-key header carries the key: not the URL, the body or
        # any other header.
        self.assertNotIn(SENTINEL, request["path"])
        self.assertNotIn(SENTINEL.encode(), request["body"])
        self.assertEqual([k for k, v in headers.items() if SENTINEL in v], ["xi-api-key"])

    def test_the_key_is_not_kept_on_the_engine(self):
        fake = start_fake(self)
        with self.env(fake):
            self.engine.synthesize("Hello there.", "en", VOICE, self.tmp / "a.mp3")
            board = {"lang": "en", "preset": "explainer",
                     "engine": {"name": "elevenlabs", "voice": VOICE}}
            selection = make_video.select_engine(board)
        self.assertNotIn(SENTINEL, repr(vars(self.engine)))
        self.assertNotIn(SENTINEL, repr(vars(type(self.engine))))
        self.assertNotIn(SENTINEL, json.dumps(selection))

    def test_http_errors_are_sanitized(self):
        for mode, status in (("401", "401"), ("422", "422"), ("429", "429"), ("500", "500"),
                             ("echo", "400")):
            with self.subTest(mode=mode):
                _, exc = self.synthesize_error(mode)
                message = str(exc)
                self.assertIn(status, message)
                self.assertIn("ElevenLabs", message)
                self.assertNotIn(SENTINEL, message)
                self.assertNotIn("Authorization", message)
                self.assertIsNone(exc.__cause__)
                self.assertIsNone(exc.__context__)
                self.assertNotIn(SENTINEL, "".join(traceback.format_exception(exc)))

    def test_error_detail_status_or_code_is_reported(self):
        _, exc = self.synthesize_error("422")
        self.assertIn("voice_not_found", str(exc))
        _, exc = self.synthesize_error("429")
        self.assertIn("too_many_concurrent_requests", str(exc))

    def test_echoed_key_in_the_error_detail_is_masked(self):
        _, exc = self.synthesize_error("echo")
        self.assertIn("[redacted]", str(exc))
        self.assertNotIn("xi-api-key", str(exc).lower())

    def test_dropped_connection_is_sanitized(self):
        _, exc = self.synthesize_error("drop")
        self.assertIn("ElevenLabs", str(exc))
        self.assertNotIn(SENTINEL, str(exc))
        self.assertIsNone(exc.__context__)

    def test_timeout_is_sanitized(self):
        with mock.patch.object(make_video, "ELEVENLABS_TIMEOUT", 0.2):
            _, exc = self.synthesize_error("ok", delay=1.0)
        self.assertIn("ElevenLabs", str(exc))
        self.assertNotIn(SENTINEL, str(exc))
        self.assertIsNone(exc.__context__)

    def test_unusable_key_value_is_sanitized(self):
        # http.client rejects a header value with a line break and names the
        # value in its error; the engine must not pass that message on.
        bad = "sk_TEST\nSENTINEL_line_break"
        fake = start_fake(self)
        with self.env(fake, key=bad):
            with self.assertRaises(RuntimeError) as caught:
                self.engine.synthesize("Hello.", "en", VOICE, self.tmp / "a.mp3")
        text = "".join(traceback.format_exception(caught.exception))
        self.assertNotIn("SENTINEL_line_break", text)
        self.assertEqual(fake.requests, [])

    def test_redirect_is_not_followed(self):
        fake, exc = self.synthesize_error("redirect")
        self.assertIn("302", str(exc))
        self.assertEqual([r["path"] for r in fake.requests if r["path"] == "/leak"], [])

    def test_missing_key_is_a_runtime_failure_naming_the_variable(self):
        fake = start_fake(self)
        for key in (None, "", "  "):
            with self.subTest(key=key), self.env(fake, key=key):
                with self.assertRaises(make_video.RuntimeFailure) as caught:
                    self.engine.synthesize("Hello.", "en", VOICE, self.tmp / "a.mp3")
                self.assertIn("ELEVENLABS_API_KEY", str(caught.exception))
        self.assertEqual(fake.requests, [])

    def test_cache_key_does_not_change_with_the_api_key(self):
        fake = start_fake(self)
        names = []
        for n, key in enumerate((SENTINEL, OTHER_KEY)):
            cache = self.tmp / f"cache{n}"
            cache.mkdir()
            with self.env(fake, key=key):
                path, reused = make_video.synthesize_cached(self.engine, VOICE, "Hello.", "en",
                                                            cache)
            self.assertFalse(reused)
            names.append(path.name)
            self.assertEqual(files_containing(cache, key), [])
        self.assertEqual(names[0], names[1])

    def test_cached_audio_needs_no_key_and_no_request(self):
        fake = start_fake(self)
        with self.env(fake):
            make_video.synthesize_cached(self.engine, VOICE, "Hello.", "en", self.tmp)
        with self.env(fake, key=None):
            _, reused = make_video.synthesize_cached(self.engine, VOICE, "Hello.", "en", self.tmp)
        self.assertTrue(reused)
        self.assertEqual(len(fake.requests), 1)

    def test_redact_replaces_the_current_key(self):
        with mock.patch.dict(os.environ, {"ELEVENLABS_API_KEY": SENTINEL}):
            self.assertEqual(make_video.redact(f"a {SENTINEL} b"), "a [redacted] b")
        with mock.patch.dict(os.environ, clean_env(), clear=True):
            self.assertEqual(make_video.redact("a b"), "a b")
        with mock.patch.dict(os.environ, {"ELEVENLABS_API_KEY": ""}):
            self.assertEqual(make_video.redact("a b"), "a b")
        with mock.patch.dict(os.environ, {"ELEVENLABS_API_KEY": " "}):
            self.assertEqual(make_video.redact("a b"), "a b")

    def test_drop_key_ignores_a_whitespace_only_key(self):
        with mock.patch.object(make_video, "_dropped_keys", []), \
                mock.patch.dict(os.environ, {"ELEVENLABS_API_KEY": " \t"}):
            make_video.drop_key()
            self.assertEqual(make_video._dropped_keys, [])
            self.assertEqual(make_video.redact("a b"), "a b")

    def test_prepare_drops_the_key_even_when_narration_fails(self):
        failing = mock.Mock(side_effect=make_video.RuntimeFailure("narration failed"))
        steps = dict(load_storyboard=mock.Mock(return_value={}), require_tools=mock.Mock(),
                     network_offline=mock.Mock(return_value=False),
                     select_engine=mock.Mock(return_value={"fallback": False}),
                     load_scenes_module=mock.Mock(), out_dir_for=mock.Mock(return_value=self.tmp),
                     narrate=failing, _dropped_keys=[])
        with mock.patch.multiple(make_video, **steps), \
                mock.patch.dict(os.environ, {"ELEVENLABS_API_KEY": SENTINEL}):
            with self.assertRaises(make_video.RuntimeFailure):
                make_video.prepare(mock.Mock())
            self.assertNotIn("ELEVENLABS_API_KEY", {k.upper() for k in os.environ})
            self.assertEqual(make_video.redact(f"a {SENTINEL} b"), "a [redacted] b")
        failing.assert_called_once()

    def test_child_processes_get_no_key(self):
        with mock.patch.dict(os.environ, {"ELEVENLABS_API_KEY": SENTINEL}):
            env = make_video.doctor.child_env()
        self.assertNotIn("ELEVENLABS_API_KEY", {k.upper() for k in env})
        self.assertNotIn(SENTINEL, json.dumps(env))


# ---------------------------------------------------------------- CLI

def run(cmd, env):
    proc = subprocess.run(cmd, capture_output=True, env=env)
    out = proc.stdout.decode("utf-8")
    err = proc.stderr.decode("utf-8", "replace")
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        raise AssertionError(f"stdout is not one JSON object (exit {proc.returncode}):\n{out}\n"
                             f"stderr:\n{err[-3000:]}")
    return proc.returncode, data, out, err


def board(lang="en", preset="explainer", engine=None, scenes=None):
    if engine is None:
        engine = {"name": "elevenlabs", "voice": VOICE}
    return {"slug": "eleven-test", "lang": lang, "preset": preset, "mode": "quick",
            "engine": engine,
            "scenes": scenes or [{"id": "s1", "narration": "Here are eight boxes."},
                                 {"id": "s2", "narration": "Look at the middle one."},
                                 {"id": "s3", "narration": "Half of them are gone."}]}


def fake_tool(directory, name, lines=()):
    """A fake executable found through the doctor's PATH lookup."""
    if os.name == "nt":
        path = directory / f"{name}.cmd"
        path.write_text("@echo off\r\n" + "".join(f"{line}\r\n" for line in lines),
                        encoding="utf-8")
    else:
        path = directory / name
        path.write_text("#!/bin/sh\n" + "".join(f"{line}\n" for line in lines),
                        encoding="utf-8")
        path.chmod(0o755)
    return path


# Runs make_video.main() with render() replaced by a stub that writes an empty
# video: ManimCE is not needed, everything before and after render runs.
RENDER_STUB = """
import sys
sys.path.insert(0, sys.argv[1])
import make_video as m

def render(board, functions, timing, preset, width, height, fps, media_dir, name):
    media_dir.mkdir(parents=True, exist_ok=True)
    video = media_dir / name
    video.write_bytes(b"")
    return video, 0.0, {}

m.render = render
sys.exit(m.main(sys.argv[2:]))
"""


class CliCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.cache = self.tmp / "cache"
        self.cache.mkdir()
        self.out = self.tmp / "out"

    def write_board(self, data):
        path = self.tmp / "storyboard.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return path

    def env(self, base, key=SENTINEL, **extra):
        env = clean_env(ELEVENLABS_API_BASE=base, VIDEO_EXPLAINER_CACHE=str(self.cache), **extra)
        env.pop("VIDEO_EXPLAINER_OFFLINE", None)
        if key is not None:
            env["ELEVENLABS_API_KEY"] = key
        return env

    def plan(self, data, base="http://127.0.0.1:9", key=SENTINEL):
        return run([sys.executable, str(SCRIPT), "plan", str(self.write_board(data)),
                    "--out", str(self.out)], self.env(base, key))

    def assert_no_key(self, *texts):
        for text in texts:
            self.assertNotIn(SENTINEL, text)
        self.assertEqual(files_containing(self.tmp, SENTINEL), [])


class PlanTests(CliCase):
    def test_plan_reports_characters_credits_and_cost_note_offline(self):
        fake = start_fake(self)
        code, data, out, err = self.plan(board(), base=fake.base)
        self.assertEqual(code, 0, data)
        self.assertEqual((data["engine"]["name"], data["engine"]["voice"]),
                         ("elevenlabs", VOICE))
        chars = sum(len(s["narration"]) for s in board()["scenes"])
        cost = data["narration_cost"]
        self.assertEqual(cost["characters"], chars)
        self.assertEqual(cost["estimated_credits"], chars)
        self.assertEqual(cost["model"], "eleven_multilingual_v2")
        self.assertEqual(cost["note"],
                         "about $0.08 per 1K characters for eleven_multilingual_v2 (checked "
                         "2026-10-11, https://elevenlabs.io/pricing/api); cached audio is "
                         "reused, so preview and final pay once")
        self.assertFalse(any("ELEVENLABS_API_KEY" in n for n in data["notices"]),
                         data["notices"])
        self.assertEqual(fake.requests, [])  # plan never calls the API
        self.assert_no_key(out, err)

    def test_plan_uses_the_fallback_chinese_rate(self):
        data = board(lang="zh-TW", scenes=[{"id": f"s{i}", "narration": "測" * 30}
                                           for i in range(3)])
        code, result, _, _ = self.plan(data)
        self.assertEqual(code, 0, result)
        self.assertEqual(result["speech_rate"],
                         {"zh_hanzi_per_second": 3.05, "engine": "elevenlabs"})

    def test_plan_without_key_adds_a_notice(self):
        code, data, out, err = self.plan(board(), key=None)
        self.assertEqual(code, 0, data)
        self.assertTrue(any("ELEVENLABS_API_KEY" in n for n in data["notices"]),
                        data["notices"])
        self.assertIn("narration_cost", data)

    def test_key_does_not_change_the_default_engine(self):
        for lang, expected in (("zh-TW", "edge-tts"), ("en", "kokoro")):
            data = board(lang=lang)
            data["engine"] = None
            code, data, out, err = self.plan(data)
            self.assertEqual(code, 0, data)
            self.assertEqual(data["engine"]["name"], expected)
            self.assertNotIn("narration_cost", data)
            self.assert_no_key(out, err)

    def test_publishing_presets_get_a_licence_notice(self):
        for preset, expected in (("youtube", True), ("short", True), ("explainer", False)):
            code, data, _, _ = self.plan(board(preset=preset))
            self.assertEqual(code, 0, data)
            licence = [n for n in data["notices"] if "elevenlabs.io" in n]
            self.assertEqual(bool(licence), expected, (preset, data["notices"]))
            if expected:
                self.assertIn("commercial", licence[0])
                self.assertIn("free plan", licence[0])


class ValidationTests(CliCase):
    def assert_invalid(self, engine, *needles):
        code, data, out, err = self.plan(board(engine=engine))
        self.assertEqual(code, 1, data)
        self.assertFalse(data["ok"])
        text = " ".join(data["errors"])
        for needle in needles:
            self.assertIn(needle, text)
        # The storyboard holds OTHER_KEY, which differs from the environment
        # key, so redaction cannot hide an echo: validate() must not print it.
        for value in (SENTINEL, OTHER_KEY):
            self.assertNotIn(value, out + err)
            if self.out.exists():
                self.assertEqual(files_containing(self.out, value), [])
        return text

    def test_key_like_fields_in_the_engine_object_are_rejected(self):
        for field in ("api_key", "apiKey", "xi-api-key", "token", "secret", "Authorization"):
            with self.subTest(field=field):
                self.assert_invalid({"name": "elevenlabs", "voice": VOICE, field: OTHER_KEY},
                                    field, "ELEVENLABS_API_KEY")

    def test_key_like_fields_are_rejected_for_every_engine(self):
        self.assert_invalid({"name": "kokoro", "voice": "af_heart", "api_key": OTHER_KEY},
                            "api_key")

    def test_missing_voice_asks_for_a_voice_id(self):
        for engine in ({"name": "elevenlabs"}, "elevenlabs", {"name": "elevenlabs", "voice": ""}):
            with self.subTest(engine=engine):
                self.assert_invalid(engine, "ElevenLabs voice ID")

    def test_voice_id_must_be_a_plain_id(self):
        self.assert_invalid({"name": "elevenlabs", "voice": "../v1/user?x=1"},
                            "ElevenLabs voice ID")


class SynthesisTests(CliCase):
    """`preview` and `final` with fake media tools and a stubbed render."""

    def setUp(self):
        super().setUp()
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        self.dump = self.tmp / "child-env.txt"
        if os.name == "nt":
            dump = f'echo [%ELEVENLABS_API_KEY%]>>"{self.dump}"'
        else:
            dump = f'echo "[$ELEVENLABS_API_KEY]" >> "{self.dump}"'
        fake_tool(self.bin, "uv")
        fake_tool(self.bin, "ffmpeg", [dump])
        fake_tool(self.bin, "ffprobe", [dump, "echo 1.5"])
        self.scenes = self.tmp / "scenes.py"
        self.scenes.write_text("def s1(ctx): pass\ndef s2(ctx): pass\ndef s3(ctx): pass\n",
                               encoding="utf-8")

    def command(self, name, base, key=SENTINEL, data=None, stub=RENDER_STUB):
        env = self.env(base, key, VIDEO_EXPLAINER_DOCTOR_PATH=str(self.bin))
        return run([sys.executable, "-c", stub, str(SCRIPTS), name,
                    str(self.write_board(data or board())), str(self.scenes),
                    "--out", str(self.out)], env)

    def test_preview_and_final_keep_the_key_out_of_every_output(self):
        fake = start_fake(self)
        code, preview, out1, err1 = self.command("preview", fake.base)
        self.assertEqual(code, 0, preview)
        self.assertEqual(preview["engine"]["name"], "elevenlabs")
        self.assertEqual(len(fake.requests), 3)
        code, final, out2, err2 = self.command("final", fake.base)
        self.assertEqual(code, 0, final)
        self.assertEqual(len(fake.requests), 3)  # final reuses the cached audio
        self.assertTrue(all(s["audio_reused"] for s in final["scenes"]), final)
        cached = list((self.out / "work" / "audio" / "cache").glob("*.mp3"))
        self.assertEqual(len(cached), 3)
        self.assertTrue(all(p.read_bytes() == FAKE_MP3 for p in cached))
        for name in ("preview.json", "final.json"):
            self.assertTrue((self.out / name).is_file(), name)
        # The media tools ran, but without the key in their environment.
        self.assertTrue(self.dump.read_text().strip(), "fake tools did not run")
        self.assert_no_key(out1, err1, out2, err2)

    def test_render_children_get_no_key_and_redact_still_masks_it(self):
        # The stubbed render starts a child with the inherited environment, as
        # ManimCE's LaTeX, dvisvgm and ffmpeg calls do, and asks redact() to
        # mask the key after narration has finished.
        report = self.tmp / "render-child.txt"
        stub = RENDER_STUB.replace('    video.write_bytes(b"")\n', f"""\
    video.write_bytes(b"")
    import subprocess
    probe = "import os; print([k for k in os.environ if k.upper() == 'ELEVENLABS_API_KEY'])"
    child = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True)
    masked = m.redact("a " + {SENTINEL!r} + " b")
    open({str(report)!r}, "w").write(child.stdout.strip() + "|" + masked)
""")
        fake = start_fake(self)
        code, data, out, err = self.command("preview", fake.base, stub=stub)
        self.assertEqual(code, 0, data)
        self.assertEqual(len(fake.requests), 3)
        self.assertEqual(report.read_text(), "[]|a [redacted] b")
        self.assert_no_key(out, err)

    def test_missing_key_stops_preview_with_exit_2(self):
        fake = start_fake(self)
        code, data, out, err = self.command("preview", fake.base, key=None)
        self.assertEqual(code, 2, data)
        self.assertTrue(any("ELEVENLABS_API_KEY" in e for e in data["errors"]), data)
        self.assertEqual(fake.requests, [])

    def test_http_errors_stop_with_exit_2_and_no_key(self):
        for mode, status in (("401", "401"), ("echo", "400"), ("500", "500")):
            with self.subTest(mode=mode):
                fake = start_fake(self, mode)
                code, data, out, err = self.command("preview", fake.base)
                self.assertEqual(code, 2, data)
                self.assertTrue(any(status in e for e in data["errors"]), data)
                self.assert_no_key(out, err)

    def test_unexpected_error_output_is_redacted(self):
        # A bug path: main() prints the traceback and adds "error"; both pass
        # through redact().
        code_text = RENDER_STUB.replace(
            "m.render = render",
            "def boom(*a, **k):\n    raise ValueError('leak ' + __import__('os').environ"
            "['ELEVENLABS_API_KEY'])\nm.cmd_plan = boom")
        env = self.env("http://127.0.0.1:9")
        code, data, out, err = run([sys.executable, "-c", code_text, str(SCRIPTS), "plan",
                                    str(self.write_board(board())), "--out", str(self.out)], env)
        self.assertEqual(code, 2, data)
        self.assertIn("[redacted]", data["error"])
        self.assertIn("[redacted]", err)
        self.assert_no_key(out, err)


class DoctorTests(unittest.TestCase):
    def doctor(self, key):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        env = clean_env(VIDEO_EXPLAINER_DOCTOR_PATH=str(tmp), VIDEO_EXPLAINER_CACHE=str(tmp),
                        VIDEO_EXPLAINER_FONT_DIRS=str(tmp), VIDEO_EXPLAINER_OFFLINE="1")
        if key is not None:
            env["ELEVENLABS_API_KEY"] = key
        proc = subprocess.run([sys.executable, str(DOCTOR), "--quick"], capture_output=True,
                              env=env)
        out = proc.stdout.decode("utf-8")
        self.assertNotIn(SENTINEL, out + proc.stderr.decode("utf-8", "replace"))
        self.assertNotIn(str(len(SENTINEL)), json.dumps(
            json.loads(out)["capabilities"]["elevenlabs_api_key"]))
        return json.loads(out)["capabilities"]["elevenlabs_api_key"]

    def test_doctor_reports_only_whether_the_key_is_set(self):
        cap = self.doctor(SENTINEL)
        self.assertEqual(cap, {"available": True, "hint": None})
        for key in (None, ""):
            cap = self.doctor(key)
            self.assertFalse(cap["available"])
            self.assertIn("ELEVENLABS_API_KEY", cap["hint"])


if __name__ == "__main__":
    unittest.main()
