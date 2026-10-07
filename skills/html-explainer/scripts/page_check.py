#!/usr/bin/env python3
"""Check one self-contained HTML explainer page against the file rules.

Usage:
    python page_check.py FILE [--max-kb N]

Reads FILE (UTF-8) and prints one JSON object on stdout (UTF-8). Exit code:
0 = every rule passed, 1 = at least one issue, 2 = usage or input error
(missing or unreadable file, input that is not UTF-8, bad flag; these print
a message on stderr and no JSON). An unexpected internal error exits 2 with
{"file": str, "error": str, "pass": false} on stdout.
Python standard library only.

Output shape:
    {"file": str, "size_kb": float, "lang": str|null, "title": str|null,
     "issues": [{"rule": str, "line": int|null, "message": str}],
     "stats": {"words": int, "cjk_chars": int, "controls": int,
               "external": [str]},
     "pass": bool}
"line" is the 1-based line of the offending tag (or CSS text), or null when
the issue is about the whole file or about something that is absent.

Rules (the "rule" ids):
- external-host: an external resource is not on cdnjs.cloudflare.com,
  cdn.jsdelivr.net/npm/ or unpkg.com.
- unpinned-version: an allowed-host URL has no exact version in the place
  that host uses for it (x.y.z with an optional "-prerelease" suffix):
  cdn.jsdelivr.net/npm/<name or @scope/name>@x.y.z/...,
  unpkg.com/<name or @scope/name>@x.y.z/...,
  cdnjs.cloudflare.com/ajax/libs/<name>/x.y.z/...
- local-resource: a resource is a relative or file: path. "data:" URLs and
  "#" fragments are allowed.
- bad-url: a resource URL that cannot be parsed (for example "http://[::1/x").
- missing-lang: no non-empty lang attribute on <html>.
- missing-title: no non-empty <title>.
- missing-viewport: no <meta name="viewport"> with width=device-width.
- missing-dark-mode: no "prefers-color-scheme: dark" query in an inline
  <style>.
- no-interaction: no <button>, <select>, <details>, or <input> of type range,
  checkbox, radio or number.
- inline-handler: an event handler attribute: "on" + 3 or more letters
  (onclick, oncut and so on). "on", "one", "only" and the plain words
  online, onset, onward(s) are not handlers.
- too-large: file size is over --max-kb (default 500; 1 KB = 1024 bytes).

Resources checked:
- <script src>; <link href> with rel stylesheet, preload, modulepreload,
  prefetch, prerender, manifest or any *icon*; <link rel=preconnect or
  dns-prefetch> (host only, no version needed);
- src of <img>, <iframe>, <source>, <embed>, <video>, <audio>, <track>;
  srcset of <img> and <source>; <video poster>; <object data>;
- href and xlink:href of <image>, <use>, <feImage>, <script> inside <svg>;
- CSS @import and url() in inline <style> blocks and style attributes;
- inline <script> text (a text scan, comments included): import/export ...
  from "x", import "x" and import("x") with an absolute or ./ ../ / path
  (bare names such as "d3" are skipped); fetch("x") and new URL("x") with an
  absolute http(s) or // URL; every quoted URL or path in a
  <script type="importmap">.
<a href> is not a resource.

Stats: "words" counts non-CJK words in visible text (script, style and title
text excluded); "cjk_chars" counts CJK ideographs, kana and hangul in that
text; "controls" counts the interactive controls above; "external" lists the
distinct http(s) or protocol-relative URLs found, in document order.
"""

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from urllib.parse import urlsplit

EXIT_PASS, EXIT_FAIL, EXIT_USAGE = 0, 1, 2

DEFAULT_MAX_KB = 500.0

ALLOWED_HOSTS = {
    "cdnjs.cloudflare.com": "/",
    "cdn.jsdelivr.net": "/npm/",
    "unpkg.com": "/",
}
_VER = r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?"
_PKG = r"(?:@[^/@\s]+/)?[^/@\s]+"
PIN_RULES = {  # host: (exact-version path pattern, example for the message)
    "cdn.jsdelivr.net": (re.compile(rf"/npm/{_PKG}@{_VER}(?:/|$)"),
                         "/npm/<name>@1.2.3/..."),
    "unpkg.com": (re.compile(rf"/{_PKG}@{_VER}(?:/|$)"), "/<name>@1.2.3/..."),
    "cdnjs.cloudflare.com": (re.compile(rf"/ajax/libs/[^/@\s]+/{_VER}(?:/|$)"),
                             "/ajax/libs/<name>/1.2.3/..."),
}
RESOURCE_LINK_RELS = frozenset(
    "stylesheet preload icon modulepreload prefetch prerender manifest".split())
HOST_ONLY_LINK_RELS = frozenset("preconnect dns-prefetch".split())
MEDIA_SRC_TAGS = frozenset("img iframe source embed video audio track".split())
SVG_HREF_TAGS = frozenset("image use feimage script".split())
CONTROL_INPUT_TYPES = frozenset("range checkbox radio number".split())
CONTROL_TAGS = frozenset("button select details".split())

# An event handler attribute is "on" + 3 or more letters (the shortest real
# one is oncut). The plain words in NOT_HANDLERS are not handlers.
_HANDLER_RE = re.compile(r"on[a-z]{3,}")
NOT_HANDLERS = frozenset("online onset onward onwards".split())
_JS_URL_RES = (  # (pattern, absolute URLs only); group 2 is the URL
    # import/export ... from "x", and the side-effect form import "x"
    (re.compile(r"""\b(?:import|export)\s*(?:[\w$*{}\s,]+?\s*from\s*)?(["'])([^"'\n]+)\1"""),
     False),
    (re.compile(r"""\bimport\s*\(\s*(["'`])([^"'`\n]+)\1"""), False),
    (re.compile(r"""\bfetch\s*\(\s*(["'`])([^"'`\n]+)\1"""), True),
    (re.compile(r"""\bnew\s+URL\s*\(\s*(["'`])([^"'`\n]+)\1"""), True),
)
_SRCSET_URL_RE = re.compile(r"[\s,]*(\S*)")
_JSON_URL_RE =re.compile(r'"((?:https?:)?//[^"\s]+|\.{0,2}/[^"\s]*)"')
_VIEWPORT_RE = re.compile(r"width\s*=\s*device-width", re.IGNORECASE)
_DARK_RE = re.compile(r"prefers-color-scheme\s*:\s*dark", re.IGNORECASE)
_CSS_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_CSS_URL_RE = re.compile(
    r"""@import\s*(?:url\(\s*)?(?:"([^"]*)"|'([^']*)'|([^)\s;"']+))"""
    r"""|\burl\(\s*(?:"([^"]*)"|'([^']*)'|([^)\s"']*))""",
    re.IGNORECASE)
_WORD_RE = re.compile(r"[^\W_]+(?:['’-][^\W_]+)*")


class InputError(Exception):
    pass


def _is_cjk(ch):
    cp = ord(ch)
    return (0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF
            or 0x3040 <= cp <= 0x30FF or 0xAC00 <= cp <= 0xD7AF
            or 0xF900 <= cp <= 0xFAFF)


def classify_url(url, host_only=False):
    """Return (rule, message, is_external) for a resource URL, rule None if ok.

    host_only: check only the host (preconnect and dns-prefetch links)."""
    url = url.strip()
    if not url or url.startswith("#"):
        return None, None, False
    try:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
    except ValueError as exc:
        return "bad-url", f"{url} is not a valid URL ({exc})", False
    scheme = parts.scheme.lower()
    if scheme == "data":
        return None, None, False
    if scheme in ("http", "https") or url.startswith("//"):
        prefix = ALLOWED_HOSTS.get(host)
        if host_only and prefix is not None:
            return None, None, True
        if prefix is None or not parts.path.startswith(prefix):
            allowed = "cdnjs.cloudflare.com, cdn.jsdelivr.net/npm/, unpkg.com"
            where = host + parts.path if host == "cdn.jsdelivr.net" else host
            return ("external-host",
                    f"{where or url} is not an allowed host ({allowed})", True)
        pattern, example = PIN_RULES[host]
        if not pattern.match(parts.path):
            return ("unpinned-version",
                    f"{url} has no exact version (use https://{host}{example})", True)
        return None, None, True
    if len(scheme) > 1 and scheme != "file":
        return "external-host", f"{url} uses the {scheme}: scheme", False
    return "local-resource", f"{url} is a local path; keep the page self-contained", False


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.issues = []
        self.external = []
        self.lang = None
        self.html_line = None
        self.title_parts = []
        self.title_line = None
        self.has_viewport = False
        self.has_dark_mode = False
        self.controls = 0
        self.text_parts = []
        self._style_parts = None
        self._style_line = 1
        self._script_parts = None
        self._script_type = ""
        self._script_line = 1
        self._in_title = False
        self._svg_depth = 0
        self._skip_text = 0  # inside script or style

    def issue(self, rule, line, message):
        self.issues.append({"rule": rule, "line": line, "message": message})

    def check_url(self, url, line, host_only=False):
        rule, message, external = classify_url(url, host_only)
        url = url.strip()
        if external and url not in self.external:
            self.external.append(url)
        if rule:
            self.issue(rule, line, message)

    def check_css(self, css, base_line):
        css = _CSS_COMMENT_RE.sub(lambda m: re.sub(r"[^\n]", " ", m.group()), css)
        for m in _CSS_URL_RE.finditer(css):
            url = next(g for g in m.groups() if g is not None)
            self.check_url(url, base_line + css.count("\n", 0, m.start()))

    def check_srcset(self, srcset, line):
        # As in the HTML spec: a candidate is a URL (a run of non-space
        # characters, trailing commas removed), then descriptors up to a comma.
        pos = 0
        while True:
            m = _SRCSET_URL_RE.match(srcset, pos)
            url = m.group(1)
            if not url:
                break
            pos = m.end()
            if url.endswith(","):
                url = url.rstrip(",")
            else:
                comma = srcset.find(",", pos)
                pos = len(srcset) if comma < 0 else comma + 1
            self.check_url(url, line)

    def check_script(self, js, base_line, script_type):
        if script_type == "importmap":
            found = [(m.start(1), m.group(1)) for m in _JSON_URL_RE.finditer(js)]
        else:
            found = []
            for pattern, absolute_only in _JS_URL_RES:
                for m in pattern.finditer(js):
                    url = m.group(2).strip()
                    if url.startswith(("http:", "https:", "//")) or (
                            not absolute_only and url.startswith(("./", "../", "/"))):
                        found.append((m.start(2), url))
            found.sort()
        for pos, url in found:
            self.check_url(url, base_line + js.count("\n", 0, pos))

    def handle_starttag(self, tag, attrs):
        line = self.getpos()[0]
        a = {k: (v if v is not None else "") for k, v in attrs}
        for name in a:
            if _HANDLER_RE.fullmatch(name) and name not in NOT_HANDLERS:
                self.issue("inline-handler", line,
                           f"<{tag}> has inline handler attribute {name}; "
                           "use addEventListener")
        if "style" in a:
            self.check_css(a["style"], line)

        if tag == "html" and self.html_line is None:
            self.html_line = line
            self.lang = a.get("lang", "").strip() or None
        elif tag == "title" and not self._svg_depth and self.title_line is None:
            self.title_line = line
            self._in_title = True
        elif tag == "meta":
            if (a.get("name", "").strip().lower() == "viewport"
                    and _VIEWPORT_RE.search(a.get("content", ""))):
                self.has_viewport = True
        elif tag == "style":
            self._style_parts = []
            self._style_line = line + self.get_starttag_text().count("\n")
            self._skip_text += 1
        elif tag == "script":
            self._skip_text += 1
            self._script_parts = []
            self._script_type = a.get("type", "").strip().lower()
            self._script_line = line + self.get_starttag_text().count("\n")
            if "src" in a:
                self.check_url(a["src"], line)
        elif tag == "svg":
            self._svg_depth += 1
        elif tag == "link":
            rels = set(a.get("rel", "").lower().split())
            if rels & RESOURCE_LINK_RELS or any("icon" in r for r in rels):
                self.check_url(a.get("href", ""), line)
            elif rels & HOST_ONLY_LINK_RELS:
                self.check_url(a.get("href", ""), line, host_only=True)
        elif tag == "object":
            self.check_url(a.get("data", ""), line)

        if tag in MEDIA_SRC_TAGS:
            self.check_url(a.get("src", ""), line)
        if tag in ("img", "source"):
            self.check_srcset(a.get("srcset", ""), line)
        if tag == "video":
            self.check_url(a.get("poster", ""), line)
        if self._svg_depth and tag in SVG_HREF_TAGS:
            for key in ("href", "xlink:href"):
                self.check_url(a.get(key, ""), line)

        if tag in CONTROL_TAGS or (
                tag == "input" and a.get("type", "").strip().lower() in CONTROL_INPUT_TYPES):
            self.controls += 1

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag == "style" and self._style_parts is not None:
            css = "".join(self._style_parts)
            self._style_parts = None
            self._skip_text = max(0, self._skip_text - 1)
            if _DARK_RE.search(_CSS_COMMENT_RE.sub("", css)):
                self.has_dark_mode = True
            self.check_css(css, self._style_line)
        elif tag == "script":
            self._skip_text = max(0, self._skip_text - 1)
            if self._script_parts is not None:
                js = "".join(self._script_parts)
                self._script_parts = None
                self.check_script(js, self._script_line, self._script_type)
        elif tag == "svg":
            self._svg_depth = max(0, self._svg_depth - 1)

    def handle_data(self, data):
        if self._style_parts is not None:
            self._style_parts.append(data)
        elif self._script_parts is not None:
            self._script_parts.append(data)
        elif self._in_title:
            self.title_parts.append(data)
        elif not self._skip_text:
            self.text_parts.append(data)


def analyze(raw, name, max_kb):
    text = raw.decode("utf-8-sig")  # UnicodeDecodeError handled by the caller
    parser = PageParser()
    parser.feed(text)
    parser.close()

    issues = parser.issues
    title = "".join(parser.title_parts).strip() or None
    size_kb = round(len(raw) / 1024, 2)

    if parser.lang is None:
        issues.append({"rule": "missing-lang", "line": parser.html_line,
                       "message": "<html> needs a non-empty lang attribute"})
    if title is None:
        issues.append({"rule": "missing-title", "line": parser.title_line,
                       "message": "the page needs a non-empty <title>"})
    if not parser.has_viewport:
        issues.append({"rule": "missing-viewport", "line": None,
                       "message": 'needs <meta name="viewport" content="width=device-width, ...">'})
    if not parser.has_dark_mode:
        issues.append({"rule": "missing-dark-mode", "line": None,
                       "message": "no @media (prefers-color-scheme: dark) rule in an inline <style>"})
    if parser.controls == 0:
        issues.append({"rule": "no-interaction", "line": None,
                       "message": "no button, range/checkbox/radio/number input, select or details"})
    if len(raw) > max_kb * 1024:
        issues.append({"rule": "too-large", "line": None,
                       "message": f"file is {size_kb} KB; the budget is {max_kb:g} KB"})

    visible = "".join(parser.text_parts)
    cjk = sum(1 for ch in visible if _is_cjk(ch))
    latin = "".join(" " if _is_cjk(ch) else ch for ch in visible)
    return {
        "file": name,
        "size_kb": size_kb,
        "lang": parser.lang,
        "title": title,
        "issues": issues,
        "stats": {
            "words": len(_WORD_RE.findall(latin)),
            "cjk_chars": cjk,
            "controls": parser.controls,
            "external": parser.external,
        },
        "pass": not issues,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Check one self-contained HTML page and print JSON.")
    ap.add_argument("file", help="HTML file to check")
    ap.add_argument("--max-kb", type=float, default=DEFAULT_MAX_KB,
                    help=f"size budget in KB (default {DEFAULT_MAX_KB:g})")
    args = ap.parse_args(argv)  # argparse exits with 2 on usage errors

    try:
        with open(args.file, "rb") as fh:
            raw = fh.read()
        result = analyze(raw, args.file, args.max_kb)
    except (OSError, UnicodeDecodeError) as exc:
        print(f"page_check: cannot read {args.file}: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except Exception as exc:  # noqa: BLE001 - keep the one-JSON contract
        write_json({"file": args.file, "error": f"internal error: {exc!r}",
                    "pass": False})
        return EXIT_USAGE

    write_json(result)
    return EXIT_PASS if result["pass"] else EXIT_FAIL


def write_json(obj):
    out = json.dumps(obj, ensure_ascii=False, indent=2) + "\n"
    sys.stdout.buffer.write(out.encode("utf-8"))
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    sys.exit(main())
