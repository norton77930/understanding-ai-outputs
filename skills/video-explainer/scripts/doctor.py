#!/usr/bin/env python3
"""Report what this machine can do for a video-explainer job.

Usage:
    python doctor.py [--quick]

Prints one JSON object (UTF-8) and exits 0 when the minimum set (uv, ffmpeg,
ffprobe) is present, 2 otherwise. Standard library only.

Output keys:
    ready         true when the minimum set is present
    capabilities  uv, ffmpeg, ffprobe, manim, kokoro_models, edge_tts_network,
                  latex. Each is {"available": bool, "hint": str|null}; the
                  hint is an install or fix hint when the capability is
                  missing. A probe that was not run (--quick) adds
                  "skipped": true.
                  latex is optional (it never changes `ready`) and also has
                  "path" (the latex executable or null) and "dvisvgm" (bool).
                  It is available only when both latex and dvisvgm are on PATH:
                  then scene code may use MathTex/Tex. It is a PATH lookup, so
                  --quick does not skip it. The doctor never installs LaTeX.
    font          First available Traditional Chinese font, in the order
                  Microsoft JhengHei, PingFang TC, Noto Sans CJK TC; else null
    font_path     Path of the matching font file, or null
    font_hint     Install hint when font is null, else null
    cache_dir     Where model files are looked up (see below)

Flags:
    --quick       Skip the slow probes (manim import through `uv run`, and the
                  edge-tts network check). They report available=false,
                  skipped=true. Run --quick first: the full manim probe
                  installs ManimCE (same pins as make_video.py's inline
                  dependency block, about 300 MB) into the uv cache, so run
                  it only after the user agrees to that install.

Environment overrides (used by the tests; also handy for debugging):
    VIDEO_EXPLAINER_DOCTOR_PATH   PATH used to look up uv, ffmpeg, ffprobe, latex
                                  and dvisvgm instead of the real PATH. Empty means nothing
                                  is found.
    VIDEO_EXPLAINER_FONT_DIRS     os.pathsep-separated directories searched for
                                  font files instead of the OS defaults (the
                                  fc-list lookup is skipped too).
    VIDEO_EXPLAINER_OFFLINE=1     The edge-tts network probe reports
                                  unavailable without connecting.
    VIDEO_EXPLAINER_CACHE         Cache directory for model files. Default:
                                  <user cache dir>/understanding-ai-outputs/
                                  video-explainer, where the user cache dir is
                                  %LOCALAPPDATA% (Windows), ~/Library/Caches
                                  (macOS) or $XDG_CACHE_HOME / ~/.cache (Linux).

Kokoro models count as present when the cache dir (searched recursively)
holds a kokoro*.onnx file and a voices*.bin file.
"""

import argparse
import contextlib
import glob
import json
import os
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path

EDGE_TTS_HOST = ("speech.platform.bing.com", 443)
NETWORK_TIMEOUT = 3
MANIM_TIMEOUT = 300

FONT_EXTENSIONS = {".ttc", ".ttf", ".otf", ".otc"}
# (display name, file-name pattern on lower-cased stems, fc-list family name)
FONTS = [
    ("Microsoft JhengHei", re.compile(r"^msjh"), "Microsoft JhengHei"),
    ("PingFang TC", re.compile(r"^pingfang"), "PingFang TC"),
    # NotoSansCJK-Regular.ttc holds every CJK variant, TC included.
    ("Noto Sans CJK TC", re.compile(r"^notosans(cjk(tc)?|tc)($|[-_.\[])"), "Noto Sans CJK TC"),
]


def report(available, hint=None, skipped=False):
    cap = {"available": bool(available), "hint": None if available else hint}
    if skipped:
        cap["skipped"] = True
    return cap


# --- executables ------------------------------------------------------------

def search_path():
    """PATH used for executable lookup (None means the real PATH)."""
    return os.environ.get("VIDEO_EXPLAINER_DOCTOR_PATH")


def find_tool(name):
    return shutil.which(name, path=search_path())


TOOL_HINTS = {
    "uv": "Install uv: https://docs.astral.sh/uv/getting-started/installation/",
    "ffmpeg": ("Install ffmpeg and put it on PATH "
               "(Windows: winget install Gyan.FFmpeg; macOS: brew install ffmpeg; "
               "Debian/Ubuntu: sudo apt install ffmpeg)."),
    "ffprobe": "ffprobe ships with ffmpeg; install ffmpeg and put it on PATH.",
}


LATEX_HINT = ("Optional: LaTeX is only needed for formulas (MathTex/Tex). Scenes work "
              "without it, using plain Text. If the user wants formulas, they can install "
              "a TeX distribution that provides both `latex` and `dvisvgm` (for example "
              "MiKTeX or TeX Live) and put them on PATH. This skill never installs it.")


def probe_tool(name):
    return report(find_tool(name), TOOL_HINTS[name])


def probe_latex():
    """Optional LaTeX: ManimCE's MathTex/Tex runs `latex`, then `dvisvgm`.
    Only looks them up; installs nothing."""
    latex, dvisvgm = find_tool("latex"), find_tool("dvisvgm")
    cap = report(latex and dvisvgm, LATEX_HINT if not (latex and dvisvgm) else None)
    if latex and not dvisvgm:
        cap["hint"] = "latex was found but dvisvgm was not. " + LATEX_HINT
    cap["path"] = latex
    cap["dvisvgm"] = bool(dvisvgm)
    return cap


MAKE_VIDEO = Path(__file__).resolve().parent / "make_video.py"
# Approximate disk use measured on Windows (uv cache, Python 3.12).
MANIM_INSTALL_MB = 300
FULL_INSTALL_MB = 520


def make_video_pins():
    """(requires-python, manim requirement) from make_video.py's PEP 723 block,
    with spaces after commas and before operators: a .cmd/.bat shim for uv
    would otherwise read the bare < and > as redirection."""
    text = MAKE_VIDEO.read_text(encoding="utf-8")
    block = re.search(r"^# /// script$(.*?)^# ///$", text, re.M | re.S).group(1)
    python = re.search(r'^#\s*requires-python\s*=\s*"([^"]+)"', block, re.M).group(1)
    manim = re.search(r'^#\s*"(manim\s*[<>=!~][^"]*)"', block, re.M).group(1)

    def spaced(spec):
        return re.sub(r"\s*,\s*", ", ", re.sub(r"\s*([<>=!~]=?)\s*", r" \1", spec)).strip()

    return spaced(python), spaced(manim)


def manim_command(uv_path):
    python, manim = make_video_pins()
    return [uv_path, "run", "--no-project", "--python", python, "--with", manim,
            "python", "-c", "import manim"]


def manim_install_note():
    _, manim = make_video_pins()
    return (f"The full probe installs ManimCE ({manim}, about {MANIM_INSTALL_MB} MB) into the "
            f"uv cache; the first preview installs about {FULL_INSTALL_MB} MB in total "
            "(ManimCE, Kokoro, edge-tts).")


def probe_manim(uv_path, quick):
    if quick:
        return report(False, "Not probed (--quick). " + manim_install_note() +
                      " Run without --quick after the user agrees to the install.", skipped=True)
    if not uv_path:
        return report(False, "Install uv first; ManimCE is installed through `uv run`. " +
                      manim_install_note())
    cmd = manim_command(uv_path)
    try:
        proc = subprocess.run(cmd, capture_output=True, stdin=subprocess.DEVNULL,
                              timeout=MANIM_TIMEOUT)
        ok = proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        ok = False
    shown = " ".join(f'"{a}"' if " " in a else a for a in ["uv", *cmd[1:]])
    return report(ok, f"`{shown}` failed; check the network and re-run it to see the error. " +
                  manim_install_note())


# --- network ----------------------------------------------------------------

def probe_network(quick):
    hint = ("edge-tts needs internet access to speech.platform.bing.com:443. "
            "Offline, zh-TW narration falls back to Kokoro (mainland accent).")
    if quick:
        return report(False, "Not probed (--quick). Run without --quick to check.", skipped=True)
    if os.environ.get("VIDEO_EXPLAINER_OFFLINE") == "1":
        return report(False, hint)
    try:
        with socket.create_connection(EDGE_TTS_HOST, timeout=NETWORK_TIMEOUT):
            pass
    except OSError:
        return report(False, hint)
    return report(True)


# --- models -----------------------------------------------------------------

def cache_dir():
    override = os.environ.get("VIDEO_EXPLAINER_CACHE")
    if override:
        return Path(override)
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = str(Path.home() / "Library" / "Caches")
    else:
        base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "understanding-ai-outputs" / "video-explainer"


def probe_kokoro(cache):
    found_model = found_voices = False
    if cache.is_dir():
        for _, _, files in os.walk(cache):
            for f in files:
                low = f.lower()
                if low.startswith("kokoro") and low.endswith(".onnx"):
                    found_model = True
                elif low.startswith("voices") and low.endswith(".bin"):
                    found_voices = True
    return report(
        found_model and found_voices,
        f"Kokoro model files (about 350-380 MB per language set: kokoro*.onnx and voices*.bin) are not in {cache}. "
        "Ask the user to approve the download before fetching them.",
    )


# --- fonts ------------------------------------------------------------------

def default_font_dirs():
    home = Path.home()
    if sys.platform == "win32":
        windir = os.environ.get("WINDIR") or os.environ.get("SystemRoot") or r"C:\Windows"
        dirs = [Path(windir) / "Fonts"]
        local = os.environ.get("LOCALAPPDATA")
        if local:
            dirs.append(Path(local) / "Microsoft" / "Windows" / "Fonts")
        return dirs
    if sys.platform == "darwin":
        dirs = [Path("/System/Library/Fonts"), Path("/Library/Fonts"), home / "Library" / "Fonts"]
        pattern = "/System/Library/AssetsV2/com_apple_MobileAsset_Font*"
        dirs.extend(Path(p) for p in sorted(glob.glob(pattern)))
        return dirs
    return [Path("/usr/share/fonts"), Path("/usr/local/share/fonts"),
            home / ".fonts", home / ".local" / "share" / "fonts"]


def font_dirs():
    override = os.environ.get("VIDEO_EXPLAINER_FONT_DIRS")
    if override is not None:
        return [Path(p) for p in override.split(os.pathsep) if p], True
    return default_font_dirs(), False


def list_font_files(dirs):
    files = []
    for d in dirs:
        if not d.is_dir():
            continue
        for root, subdirs, names in os.walk(d):
            subdirs.sort()
            for name in sorted(names):
                stem, ext = os.path.splitext(name)
                if ext.lower() in FONT_EXTENSIONS:
                    files.append((stem.lower(), os.path.join(root, name)))
    return files


def fc_list_lines():
    fc_list = find_tool("fc-list")
    if not fc_list:
        return []
    try:
        proc = subprocess.run([fc_list], capture_output=True, stdin=subprocess.DEVNULL,
                              timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return []
    return proc.stdout.decode("utf-8", errors="replace").splitlines()


def select_font():
    dirs, overridden = font_dirs()
    files = list_font_files(dirs)
    fc_lines = [] if overridden or sys.platform in ("win32", "darwin") else fc_list_lines()
    for name, pattern, family in FONTS:
        for stem, path in files:
            if pattern.match(stem):
                return name, path
        for line in fc_lines:
            if family.lower() in line.lower():
                return name, line.split(":", 1)[0].strip()
    return None, None


FONT_HINT = ("No Traditional Chinese font found. Install one of: Microsoft JhengHei (Windows), "
             "PingFang TC (macOS), Noto Sans CJK TC "
             "(Linux: sudo apt install fonts-noto-cjk).")


# --- main -------------------------------------------------------------------

def build_report(quick):
    caps = {name: probe_tool(name) for name in ("uv", "ffmpeg", "ffprobe")}
    cache = cache_dir()
    caps["manim"] = probe_manim(find_tool("uv"), quick)
    caps["kokoro_models"] = probe_kokoro(cache)
    caps["edge_tts_network"] = probe_network(quick)
    caps["latex"] = probe_latex()
    font, font_path = select_font()
    return {
        "ready": all(caps[n]["available"] for n in ("uv", "ffmpeg", "ffprobe")),
        "capabilities": caps,
        "font": font,
        "font_path": font_path,
        "font_hint": None if font else FONT_HINT,
        "cache_dir": str(cache),
    }


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(AttributeError, ValueError):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Report what this machine can do for a video job.")
    parser.add_argument("--quick", action="store_true",
                        help="skip the manim import and network probes")
    args = parser.parse_args(argv)
    result = build_report(args.quick)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ready"] else 2


if __name__ == "__main__":
    sys.exit(main())
