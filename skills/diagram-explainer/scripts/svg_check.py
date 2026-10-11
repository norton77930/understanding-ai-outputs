#!/usr/bin/env python3
"""Check a hand-written SVG diagram: safe, self-contained and readable.

Usage:
    python svg_check.py [FILE|-] [--display-width N] [--min-font-px N]
                        [--floor-width N] [--floor-font-px N] [--sheet]

Reads FILE (or stdin when FILE is omitted or "-") and prints one JSON object
on stdout (UTF-8). Exit code: 0 = pass, 1 = check failed, 2 = usage or input
error. Python standard library only.

Output shape:
    {"viewbox": [x, y, width, height] | null,
     "limits": {"display_width", "min_font_px", "floor_width",
                "floor_font_px", "min_font_size", "floor_font_size",
                "min_contrast", "max_bytes"},
     "counts": {"texts", "bytes"},
     "texts": [{"text", "line", "font_size", "color", "background",
                "contrast"}],
     "issues": [{"rule", "line", "message"}],
     "warnings": [{"rule", "line", "message"}],
     "pass": bool}

pass is true when issues is empty. Warnings never fail the check.

The checker is a floor, not a style guide: it rejects what breaks the image
for every reader (unsafe or external content, no canvas, unreadable text) and
leaves the design to the author.

Rules (issue "rule" values):
    not-xml             the file is not well-formed XML
    not-svg             the root element is not <svg> in the SVG namespace
    doctype             a DOCTYPE or ENTITY declaration (rejected before
                        parsing, so no entity is ever expanded)
    no-viewbox          no viewBox, or a viewBox that is not four numbers
                        with a positive width and height
    script              a <script> element
    event-handler       an on* event attribute (onclick, onload, ...)
    foreign-object      a <foreignObject> element
    external-reference  href or xlink:href other than "#..." or
                        "data:image/...", url(...) to anything else, or any
                        @import
    no-background       no opaque shape covers the whole viewBox (and no
                        CSS background on the root), so the image changes
                        with the host page (light or dark)
    low-contrast        text color against the color under it is below
                        4.5:1 (WCAG AA), when both colors resolve
    small-text          text smaller than the font-size floor (see below)

    The low-contrast threshold is the same for all text sizes.

Warnings (warning "rule" values; never a failure):
    text-outside        text that probably falls outside the viewBox
    cannot-place        text under a transform other than translate(), on a
                        textPath, or in a nested <svg>: its position and
                        contrast are not checked
    unresolved-color    a text color or the color under it does not resolve
                        (gradient, hsl(), unknown name): contrast not checked
    large-file          the file is larger than about 200 KB
    small-text-advisory text above the floor but below the recommended size

Font size has two tiers, both in viewBox units:
    recommendation (warning small-text-advisory):
        min_font_size = min_font_px * max(1, viewBox width / display_width)
        defaults 12 and 800. A diagram is usually shown about 800 px wide (a
        chat reply, a GitHub README column, a doc page), and 12 px is the
        smallest text that reads comfortably there. A 1600-wide viewBox shown
        800 px wide halves every size, so 24 units are recommended.
    floor (issue small-text):
        floor_font_size = floor_font_px * max(1, viewBox width / floor_width)
        defaults 11 and 1200. Calibrated on the hand-written SVGs that the
        maintainer rated 4-5 for presentation in the first blind rating
        (viewBox 1000-1240 wide, smallest text 12-13 units): all pass, and
        their smallest text is 11.6 or more on this scale. Text below the
        floor is too small on any normal screen.
    Text below the floor gets the issue only. A viewBox narrower than the
    width is usually shown at its own size or larger, so the tier stays at
    its px value. Flags: --display-width and --min-font-px set the
    recommendation, --floor-width and --floor-font-px set the floor.
    --sheet is --display-width 1600 for an overview sheet (an explicit
    --display-width wins); the floor does not change.

Method (APPROXIMATE, not a renderer):
    - Styles: presentation attributes, then <style> rules with simple
      selectors (tag, .class, #id, and compounds such as text.label; comma
      lists), then the style attribute. Rules inside @media and selectors
      with combinators or pseudo-classes are ignored. fill, color,
      font-size, text-anchor and fill-opacity inherit; opacity multiplies.
    - Colors: #rgb, #rgba, #rrggbb, #rrggbbaa, rgb()/rgba(), currentColor
      and a small set of names (see NAMED_COLORS).
    - Text runs: each <text>, and each <tspan> with x, y or dy, starts a
      line. Width is estimated per character: CJK and other wide
      characters 1 em, everything else 0.6 em. text-anchor is honored.
    - The color under a text is found at the center of its line: the
      canvas background, then every rect, circle, ellipse and polygon
      (bounding box) painted before the text that contains that point.
      Paths are not used as text backgrounds.
"""

import argparse
import json
import re
import sys
import unicodedata
from xml.parsers import expat

EXIT_PASS, EXIT_FAIL, EXIT_USAGE = 0, 1, 2

SVG_NS = "http://www.w3.org/2000/svg"
DEFAULT_LIMITS = {"display_width": 800, "min_font_px": 12,
                  "floor_width": 1200, "floor_font_px": 11}
# An overview sheet is opened full screen or zoomed, not shown 800 px wide.
SHEET_DISPLAY_WIDTH = 1600
MIN_CONTRAST = 4.5
MAX_BYTES = 200 * 1024
DEFAULT_FONT_SIZE = 16.0

# Elements whose content is not painted where it stands.
NOT_RENDERED = {"defs", "symbol", "clipPath", "mask", "pattern", "marker",
                "linearGradient", "radialGradient", "filter", "title", "desc",
                "metadata", "style", "script", "foreignObject"}
INHERITED = ("fill", "fill-opacity", "color", "font-size", "text-anchor")
STYLE_PROPS = INHERITED + ("opacity", "background", "background-color")

NAMED_COLORS = {
    "black": (0, 0, 0), "white": (255, 255, 255), "gray": (128, 128, 128),
    "grey": (128, 128, 128), "silver": (192, 192, 192),
    "darkgray": (169, 169, 169), "darkgrey": (169, 169, 169),
    "lightgray": (211, 211, 211), "lightgrey": (211, 211, 211),
    "dimgray": (105, 105, 105), "dimgrey": (105, 105, 105),
    "red": (255, 0, 0), "darkred": (139, 0, 0), "maroon": (128, 0, 0),
    "green": (0, 128, 0), "darkgreen": (0, 100, 0), "lime": (0, 255, 0),
    "blue": (0, 0, 255), "navy": (0, 0, 128), "darkblue": (0, 0, 139),
    "yellow": (255, 255, 0), "orange": (255, 165, 0), "purple": (128, 0, 128),
    "teal": (0, 128, 128), "olive": (128, 128, 0), "aqua": (0, 255, 255),
    "cyan": (0, 255, 255), "fuchsia": (255, 0, 255), "magenta": (255, 0, 255),
    "pink": (255, 192, 203), "brown": (165, 42, 42),
    "whitesmoke": (245, 245, 245), "gainsboro": (220, 220, 220),
}

_NUMBER = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"
_LENGTH_RE = re.compile(rf"^({_NUMBER})(px|%)?$")
_FONT_SIZE_RE = re.compile(rf"^({_NUMBER})(px|pt|em|rem|%)?$")
_TRANSLATE_RE = re.compile(rf"translate\(\s*({_NUMBER})(?:\s*,?\s*({_NUMBER}))?\s*\)")
_TRANSLATES_ONLY_RE = re.compile(
    rf"^\s*(?:translate\(\s*{_NUMBER}(?:\s*,?\s*{_NUMBER})?\s*\)\s*,?\s*)+$")
_DOCTYPE_RE = re.compile(r"<!\s*(DOCTYPE|ENTITY)\b", re.IGNORECASE)
_URL_RE = re.compile(r"url\(\s*(['\"]?)([^'\")]*)\1\s*\)", re.IGNORECASE)
_IMPORT_RE = re.compile(r"@import\b", re.IGNORECASE)
_IMPORT_STMT_RE = re.compile(r"@import\b[^;]*;?", re.IGNORECASE)
_SELECTOR_RE = re.compile(r"^(\*|[A-Za-z][\w-]*)?((?:[.#][\w-]+)*)$")
_HEX_RE = re.compile(r"^#([0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
_RGB_RE = re.compile(r"^rgba?\(\s*([^)]*)\)$", re.IGNORECASE)


class InputError(Exception):
    pass


class Node:
    __slots__ = ("tag", "ns", "attrs", "children", "line", "parent")

    def __init__(self, tag, ns, attrs, line, parent):
        self.tag, self.ns, self.attrs = tag, ns, attrs
        self.line, self.parent, self.children = line, parent, []


class Report:
    def __init__(self):
        self.issues, self.warnings = [], []

    def issue(self, rule, line, message):
        self.issues.append({"rule": rule, "line": line, "message": message})

    def warn(self, rule, line, message):
        self.warnings.append({"rule": rule, "line": line, "message": message})


# ---------------------------------------------------------------- parsing


def _split_name(name):
    if "}" in name:
        ns, local = name.split("}", 1)
        return ns, local
    return None, name


def parse_xml(text):
    """Return the root Node. Raises expat.ExpatError when not well-formed."""
    parser = expat.ParserCreate(namespace_separator="}")
    parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    stack, holder = [], []

    def start(name, attrs):
        ns, local = _split_name(name)
        node = Node(local, ns, {_split_name(k)[1]: v for k, v in attrs.items()},
                    parser.CurrentLineNumber, stack[-1] if stack else None)
        if stack:
            stack[-1].children.append(node)
        else:
            holder.append(node)
        stack.append(node)

    def end(_name):
        stack.pop()

    def chars(data):
        if stack:
            kids = stack[-1].children
            if kids and isinstance(kids[-1], str):
                kids[-1] += data
            else:
                kids.append(data)

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.CharacterDataHandler = chars
    parser.Parse(text, True)
    return holder[0]


def iter_nodes(node):
    yield node
    for child in node.children:
        if isinstance(child, Node):
            yield from iter_nodes(child)


# ---------------------------------------------------------------- styles


def parse_declarations(text):
    decls = {}
    for part in text.split(";"):
        if ":" not in part:
            continue
        prop, value = part.split(":", 1)
        prop = prop.strip().lower()
        value = re.sub(r"!\s*important\s*$", "", value.strip(), flags=re.I).strip()
        if prop == "font":
            size = _font_shorthand_size(value)
            if size:
                decls["font-size"] = size
        elif prop:
            decls[prop] = value
    return decls


def _font_shorthand_size(value):
    for token in value.split():
        token = token.split("/")[0]
        if _FONT_SIZE_RE.match(token):
            return token
    return None


def _strip_at_rules(css):
    """Drop @media/@supports/... blocks and @import lines; keep plain rules."""
    out, i = [], 0
    while i < len(css):
        if css[i] == "@":
            semi, brace = css.find(";", i), css.find("{", i)
            if brace == -1 or (semi != -1 and semi < brace):
                i = len(css) if semi == -1 else semi + 1
                continue
            depth, j = 0, brace
            while j < len(css):
                depth += {"{": 1, "}": -1}.get(css[j], 0)
                j += 1
                if depth == 0:
                    break
            i = j
            continue
        out.append(css[i])
        i += 1
    return "".join(out)


def parse_stylesheet(css):
    """Return [(specificity, order, (tag, classes, ids), decls)]."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    rules, order = [], 0
    for selectors, body in re.findall(r"([^{}]+)\{([^{}]*)\}", _strip_at_rules(css)):
        decls = parse_declarations(body)
        for sel in selectors.split(","):
            match = _SELECTOR_RE.match(sel.strip())
            if not match or not sel.strip():
                continue
            tag = match.group(1)
            parts = re.findall(r"([.#])([\w-]+)", match.group(2))
            classes = {name for kind, name in parts if kind == "."}
            ids = {name for kind, name in parts if kind == "#"}
            spec = (len(ids), len(classes), 1 if tag and tag != "*" else 0)
            rules.append((spec, order, (tag, classes, ids), decls))
            order += 1
    rules.sort(key=lambda r: (r[0], r[1]))
    return rules


def _matches(node, selector):
    tag, classes, ids = selector
    if tag and tag != "*" and tag != node.tag:
        return False
    if classes and not classes <= set(node.attrs.get("class", "").split()):
        return False
    return not ids or ids == {node.attrs.get("id")}


def specified_style(node, rules):
    spec = {}
    for prop in STYLE_PROPS:
        if prop in node.attrs:
            spec[prop] = node.attrs[prop].strip()
    for _spec, _order, selector, decls in rules:
        if _matches(node, selector):
            spec.update(decls)
    if "style" in node.attrs:
        spec.update(parse_declarations(node.attrs["style"]))
    return spec


def font_size(value, parent):
    match = _FONT_SIZE_RE.match(value.strip().lower())
    if not match:
        return None
    number, unit = float(match.group(1)), match.group(2)
    if unit == "pt":
        return number * 4 / 3
    if unit in ("em", "rem"):
        return None if parent is None else number * parent
    if unit == "%":
        return None if parent is None else number * parent / 100
    return number


def computed_style(node, rules, parent_style):
    spec = specified_style(node, rules)
    style = dict(parent_style)
    for prop in INHERITED:
        value = spec.get(prop)
        if value is None or value.lower() == "inherit":
            continue
        if prop == "font-size":
            style[prop] = font_size(value, parent_style.get("font-size"))
        else:
            style[prop] = value
    style["opacity"] = parent_style["opacity"] * _number(spec.get("opacity"), 1.0)
    style["background"] = spec.get("background-color") or spec.get("background")
    return style


ROOT_STYLE = {"fill": "black", "fill-opacity": "1", "color": "black",
              "font-size": DEFAULT_FONT_SIZE, "text-anchor": "start",
              "opacity": 1.0, "background": None}


def _number(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------- colors


def parse_color(value, current=None):
    """Return (r, g, b, a) with a in 0..1, "none", or None when unknown."""
    if value is None:
        return None
    value = value.strip()
    low = value.lower()
    if low in ("none", "transparent"):
        return "none"
    if low == "currentcolor":
        return parse_color(current) if current else None
    if low in NAMED_COLORS:
        return NAMED_COLORS[low] + (1.0,)
    match = _HEX_RE.match(value)
    if match:
        digits = match.group(1)
        if len(digits) in (3, 4):
            digits = "".join(c * 2 for c in digits)
        channels = [int(digits[i:i + 2], 16) for i in range(0, len(digits), 2)]
        alpha = channels[3] / 255 if len(channels) == 4 else 1.0
        return tuple(channels[:3]) + (alpha,)
    match = _RGB_RE.match(value)
    if match:
        parts = [p for p in re.split(r"[\s,/]+", match.group(1).strip()) if p]
        if len(parts) not in (3, 4):
            return None
        try:
            rgb = [float(p[:-1]) * 2.55 if p.endswith("%") else float(p)
                   for p in parts[:3]]
            alpha = 1.0
            if len(parts) == 4:
                a = parts[3]
                alpha = float(a[:-1]) / 100 if a.endswith("%") else float(a)
        except ValueError:
            return None
        return tuple(max(0, min(255, round(c))) for c in rgb) + (max(0.0, min(1.0, alpha)),)
    return None


def blend(top, alpha, bottom):
    return tuple(round(t * alpha + b * (1 - alpha)) for t, b in zip(top, bottom))


def luminance(rgb):
    def channel(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def hex_color(rgb):
    return "#{:02x}{:02x}{:02x}".format(*rgb)


# ---------------------------------------------------------------- geometry


def parse_view_box(value):
    if value is None:
        return None
    parts = [p for p in re.split(r"[\s,]+", value.strip()) if p]
    if len(parts) != 4:
        return None
    try:
        box = [float(p) for p in parts]
    except ValueError:
        return None
    if box[2] <= 0 or box[3] <= 0:
        return None
    return [int(v) if v.is_integer() else v for v in box]


def length(value, ref, default=None):
    if value is None:
        return default
    first = re.split(r"[\s,]+", value.strip())[0] if value.strip() else ""
    match = _LENGTH_RE.match(first)
    if not match:
        return None
    number = float(match.group(1))
    return number * ref / 100 if match.group(2) == "%" else number


def translate_of(node):
    """(dx, dy) of the node's transform, or None for anything but translate()."""
    value = node.attrs.get("transform", "").strip()
    if not value:
        return 0.0, 0.0
    if not _TRANSLATES_ONLY_RE.match(value):
        return None
    dx = dy = 0.0
    for tx, ty in _TRANSLATE_RE.findall(value):
        dx += float(tx)
        dy += float(ty or 0)
    return dx, dy


def char_em(ch):
    if unicodedata.combining(ch):
        return 0.0
    return 1.0 if unicodedata.east_asian_width(ch) in ("W", "F") else 0.6


# ---------------------------------------------------------------- analysis


class Segment:
    def __init__(self, text, style, line):
        self.text, self.style, self.line = text, style, line


class TextLine:
    def __init__(self, x, y, anchor, placeable):
        self.x, self.y, self.anchor, self.placeable = x, y, anchor, placeable
        self.segments = []


class Analyzer:
    def __init__(self, root, view_box, limits, report):
        self.root, self.vb, self.limits, self.report = root, view_box, limits, report
        css = "".join(c for n in iter_nodes(root) if n.tag == "style"
                      for c in n.children if isinstance(c, str))
        self.css = css
        self.rules = parse_stylesheet(css)
        self.shapes = []          # (kind, geometry, color rgba | None, alpha)
        self.base = "none"        # canvas color from the root CSS background
        self.base_raw = None
        self.has_background = False
        self.texts = []

    # -- walk

    def run(self):
        style = computed_style(self.root, self.rules, ROOT_STYLE)
        if style["background"]:
            color = parse_color(style["background"])
            if color != "none":
                self.has_background = True
                self.base = color[:3] if color and color[3] >= 1 else None
                self.base_raw = style["background"]
        self.walk(self.root, style, (0.0, 0.0), root=True)

    def walk(self, node, style, offset, root=False):
        for child in node.children:
            if not isinstance(child, Node):
                continue
            if child.tag in NOT_RENDERED:
                continue
            cstyle = computed_style(child, self.rules, style)
            coff = self.child_offset(child, offset)
            if child.tag == "text":
                self.text(child, cstyle, coff)
            elif child.tag == "svg":
                self.walk(child, cstyle, None)
            else:
                self.shape(child, cstyle, coff)
                self.walk(child, cstyle, coff)

    @staticmethod
    def child_offset(node, offset):
        move = translate_of(node)
        if offset is None or move is None:
            return None
        return offset[0] + move[0], offset[1] + move[1]

    # -- shapes

    def shape(self, node, style, offset):
        if offset is None or self.vb is None:
            return
        vw, vh = self.vb[2], self.vb[3]
        a = node.attrs
        geometry = None
        if node.tag == "rect":
            x, y = length(a.get("x"), vw, 0.0), length(a.get("y"), vh, 0.0)
            w, h = length(a.get("width"), vw), length(a.get("height"), vh)
            if None not in (x, y, w, h) and w > 0 and h > 0:
                geometry = ("box", x + offset[0], y + offset[1], w, h)
        elif node.tag in ("circle", "ellipse"):
            cx, cy = length(a.get("cx"), vw, 0.0), length(a.get("cy"), vh, 0.0)
            if node.tag == "circle":
                rx = ry = length(a.get("r"), vw)
            else:
                rx, ry = length(a.get("rx"), vw), length(a.get("ry"), vh)
            if None not in (cx, cy, rx, ry) and rx > 0 and ry > 0:
                geometry = ("ellipse", cx + offset[0], cy + offset[1], rx, ry)
        elif node.tag == "polygon":
            nums = [float(n) for n in re.findall(_NUMBER, a.get("points", ""))]
            xs, ys = nums[0::2], nums[1::2]
            if len(xs) >= 3 and len(ys) == len(xs):
                geometry = ("box", min(xs) + offset[0], min(ys) + offset[1],
                            max(xs) - min(xs), max(ys) - min(ys))
        if geometry is None:
            return
        fill = style["fill"]
        color = None if fill.strip().lower().startswith("url(") else \
            parse_color(fill, style["color"])
        if color == "none":
            return
        alpha = style["opacity"] * _number(style["fill-opacity"], 1.0)
        if color is not None:
            alpha *= color[3]
            color = color[:3]
        if alpha <= 0:
            return
        self.shapes.append((geometry, color, alpha, fill))
        if geometry[0] == "box" and alpha >= 1 and self.covers(geometry):
            self.has_background = True

    def covers(self, geometry):
        _kind, x, y, w, h = geometry
        vx, vy, vw, vh = self.vb
        return x <= vx and y <= vy and x + w >= vx + vw and y + h >= vy + vh

    def color_under(self, px, py, shapes):
        """(color, unknown fill) at a point. color is rgb, None (unknown) or
        "none" (transparent); unknown fill is the value that did not resolve."""
        state, unknown = self.base, self.base_raw
        for geometry, color, alpha, raw in shapes:
            kind, gx, gy, gw, gh = geometry
            if kind == "box":
                inside = gx <= px <= gx + gw and gy <= py <= gy + gh
            else:
                inside = ((px - gx) / gw) ** 2 + ((py - gy) / gh) ** 2 <= 1
            if not inside:
                continue
            if color is None:
                unknown = raw
            if alpha >= 1:
                state = color
            elif color is None or state is None:
                state = None
            elif state != "none":
                state = blend(color, alpha, state)
        return state, unknown

    # -- text

    def text(self, node, style, offset):
        vw, vh = (self.vb[2], self.vb[3]) if self.vb else (0, 0)
        x, y = length(node.attrs.get("x"), vw, 0.0), length(node.attrs.get("y"), vh, 0.0)
        if x is not None and y is not None:
            y += self._dy(node, style)
        placeable = offset is not None and x is not None and y is not None
        lines = [TextLine(x, y, style["text-anchor"], placeable)]
        self.collect(node, style, lines, offset)
        shapes = list(self.shapes)
        for line in lines:
            self.check_line(line, offset, shapes)

    def _dy(self, node, style):
        value = node.attrs.get("dy")
        if not value:
            return 0.0
        first = re.split(r"[\s,]+", value.strip())[0]
        if first.endswith("em"):
            size = style["font-size"]
            return _number(first[:-2], 0.0) * (size or DEFAULT_FONT_SIZE)
        return length(first, self.vb[3] if self.vb else 0, 0.0) or 0.0

    def collect(self, node, style, lines, offset):
        vw, vh = (self.vb[2], self.vb[3]) if self.vb else (0, 0)
        for child in node.children:
            if isinstance(child, str):
                text = re.sub(r"\s+", " ", child)
                if text.strip():
                    lines[-1].segments.append(Segment(text, style, node.line))
                continue
            if child.tag in NOT_RENDERED:
                continue
            cstyle = computed_style(child, self.rules, style)
            if child.tag == "textPath" or translate_of(child) != (0.0, 0.0):
                lines[-1].placeable = False
            elif child.tag == "tspan" and any(k in child.attrs for k in ("x", "y", "dy")):
                prev = lines[-1]
                x = length(child.attrs["x"], vw) if "x" in child.attrs else prev.x
                y = length(child.attrs["y"], vh) if "y" in child.attrs else prev.y
                if y is not None:
                    y += self._dy(child, cstyle)
                lines.append(TextLine(x, y, cstyle["text-anchor"],
                                      offset is not None and None not in (x, y)
                                      and prev.placeable))
            self.collect(child, cstyle, lines, offset)

    def check_line(self, line, offset, shapes):
        segments = [s for s in line.segments if s.text.strip()]
        if not segments:
            return
        segments[0].text = segments[0].text.lstrip()
        segments[-1].text = segments[-1].text.rstrip()
        center = None
        if self.vb is None:
            pass  # no canvas to place against; no-viewbox reports it
        elif line.placeable:
            sizes = [s.style["font-size"] or DEFAULT_FONT_SIZE for s in segments]
            width = sum(sum(char_em(c) for c in s.text) * size
                        for s, size in zip(segments, sizes))
            x0 = line.x + offset[0]
            if line.anchor == "middle":
                x0 -= width / 2
            elif line.anchor == "end":
                x0 -= width
            top_size = max(sizes)
            baseline = line.y + offset[1]
            center = (x0 + width / 2, baseline - 0.35 * top_size)
            self.check_inside(segments, x0, width, baseline, top_size)
        else:
            self.report.warn("cannot-place", segments[0].line,
                             f"text {self._quote(segments)}: a transform other than "
                             "translate(), a textPath or a nested <svg>; position and "
                             "contrast are not checked")
        for seg in segments:
            self.check_segment(seg, center, shapes)

    def check_inside(self, segments, x0, width, baseline, size):
        vx, vy, vw, vh = self.vb
        top, bottom = baseline - 0.8 * size, baseline + 0.2 * size
        sides = [side for side, out in (("left", x0 < vx), ("right", x0 + width > vx + vw),
                                        ("top", top < vy), ("bottom", bottom > vy + vh))
                 if out]
        if sides:
            self.report.warn(
                "text-outside", segments[0].line,
                f"text {self._quote(segments)} probably crosses the {' and '.join(sides)} "
                f"edge (estimated box x {x0:.0f} to {x0 + width:.0f}, y {top:.0f} to "
                f"{bottom:.0f}; viewBox {vx:g} {vy:g} {vw:g} {vh:g}); move or shorten it, "
                "or check the render")

    def check_segment(self, seg, center, shapes):
        style = seg.style
        entry = {"text": seg.text.strip(), "line": seg.line,
                 "font_size": None if style["font-size"] is None
                 else round(style["font-size"], 2),
                 "color": None, "background": None, "contrast": None}
        self.texts.append(entry)
        self.check_size(entry)
        fill = parse_color(style["fill"], style["color"])
        if fill == "none":
            return
        under, unknown = self.color_under(*center, shapes) if center else ("none", None)
        if under == "none":
            return  # transparent canvas: no-background already reports it
        if fill is None or under is None:
            what = (f"text color {style['fill']!r}" if fill is None
                    else f"the fill under it ({unknown!r})")
            self.report.warn("unresolved-color", seg.line,
                             f"text {entry['text']!r}: {what} does not resolve to one "
                             "color, so contrast is not checked; check it in the render")
            return
        if isinstance(fill, tuple) and isinstance(under, tuple):
            alpha = fill[3] * style["opacity"] * _number(style["fill-opacity"], 1.0)
            color = blend(fill[:3], alpha, under)
            ratio = contrast(color, under)
            entry.update(color=hex_color(color), background=hex_color(under),
                         contrast=round(ratio, 2))
            if ratio < MIN_CONTRAST:
                self.report.issue(
                    "low-contrast", seg.line,
                    f"text {entry['text']!r}: {hex_color(color)} on {hex_color(under)} "
                    f"is {ratio:.2f}:1, below {MIN_CONTRAST}:1; darken the text or "
                    "lighten what is under it (or the reverse)")

    def check_size(self, entry):
        limits, size = self.limits, entry["font_size"]
        floor, advised = limits["floor_font_size"], limits["min_font_size"]
        if floor is None or size is None or size >= max(floor, advised):
            return
        width = limits["display_width"]
        shown = size * min(1.0, width / self.vb[2])
        where = (f"it shows at about {shown:.3g} px when the image is {width:g} px wide")
        if size < floor:
            self.report.issue(
                "small-text", entry["line"],
                f"text {entry['text']!r} is {size:g} units, below the floor {floor:g}; "
                f"{where}. Use font-size {max(floor, advised):g} or more")
        else:
            self.report.warn(
                "small-text-advisory", entry["line"],
                f"text {entry['text']!r} is {size:g} units, below the recommended "
                f"{advised:g}; {where}. Use {advised:g} or more if the layout allows")

    @staticmethod
    def _quote(segments):
        text = "".join(s.text for s in segments).strip()
        return repr(text if len(text) <= 40 else text[:39] + "…")


def check_content(root, report):
    """Active content: nothing that runs or embeds another document."""
    for node in iter_nodes(root):
        if node.tag == "script":
            report.issue("script", node.line,
                         "<script> element; an SVG diagram must not run code")
        elif node.tag == "foreignObject":
            report.issue("foreign-object", node.line,
                         "<foreignObject> element; draw with SVG shapes and <text> "
                         "(HTML inside SVG does not render everywhere)")
        for name, value in node.attrs.items():
            if name.lower().startswith("on"):
                report.issue("event-handler", node.line,
                             f"event attribute {name}= on <{node.tag}>; remove it")
            elif name == "href" and not _local_target(value):
                report.issue("external-reference", node.line,
                             f"<{node.tag}> links to {value.strip()!r}; use \"#id\" or "
                             "data:image/..., so the file stands alone")
            else:
                check_css_urls(value, node.line, report)
        if node.tag == "style":
            css = "".join(c for c in node.children if isinstance(c, str))
            for match in _IMPORT_RE.finditer(css):
                report.issue("external-reference", node.line + css.count("\n", 0, match.start()),
                             "@import in <style> loads an outside stylesheet; put the "
                             "rules in the file")
            check_css_urls(_IMPORT_STMT_RE.sub("", css), node.line, report)


def _local_target(value):
    value = value.strip()
    return value.startswith("#") or value.lower().startswith("data:image/")


def check_css_urls(text, line, report):
    for match in _URL_RE.finditer(text):
        target = match.group(2).strip()
        if not _local_target(target):
            report.issue("external-reference", line + text.count("\n", 0, match.start()),
                         f"url({target}) points outside the file; use url(#id) or "
                         "data:image/...")


def analyze(raw, limits):
    report = Report()
    limits = dict(limits)
    limits.update(min_font_size=None, floor_font_size=None, min_contrast=MIN_CONTRAST,
                  max_bytes=MAX_BYTES)
    result = {"viewbox": None, "limits": limits,
              "counts": {"texts": 0, "bytes": len(raw)}, "texts": []}
    text = raw.decode("utf-8-sig")
    doctype = _DOCTYPE_RE.search(text)
    if doctype:
        report.issue("doctype", text.count("\n", 0, doctype.start()) + 1,
                     f"{doctype.group(1).upper()} declaration; remove it (an SVG "
                     "needs none, and entities can expand without limit)")
        return finish(result, report)
    try:
        root = parse_xml(text)
    except expat.ExpatError as exc:
        report.issue("not-xml", exc.lineno, f"not well-formed XML: {exc}")
        return finish(result, report)
    if root.tag != "svg" or root.ns != SVG_NS:
        message = (f'root is <svg> without xmlns="{SVG_NS}"; a browser shows it as '
                   "plain XML" if root.tag == "svg" else
                   f"root is <{root.tag}>, not <svg xmlns=\"{SVG_NS}\">")
        report.issue("not-svg", root.line, message)
        return finish(result, report)
    check_content(root, report)
    view_box = parse_view_box(root.attrs.get("viewBox"))
    result["viewbox"] = view_box
    if view_box is None:
        found = root.attrs.get("viewBox")
        report.issue("no-viewbox", root.line,
                     "no viewBox; add viewBox=\"0 0 WIDTH HEIGHT\" so the image scales"
                     if found is None else
                     f"viewBox {found!r} is not four numbers with a positive width "
                     "and height")
    else:
        limits["min_font_size"] = round(
            limits["min_font_px"] * max(1.0, view_box[2] / limits["display_width"]), 2)
        limits["floor_font_size"] = round(
            limits["floor_font_px"] * max(1.0, view_box[2] / limits["floor_width"]), 2)
    analyzer = Analyzer(root, view_box, limits, report)
    analyzer.run()
    if view_box and not analyzer.has_background:
        report.issue("no-background", root.line,
                     "no opaque shape covers the whole viewBox, so the host page shows "
                     "through (light or dark); add a first <rect> as large as the "
                     "viewBox with an opaque fill")
    result["texts"] = analyzer.texts
    result["counts"]["texts"] = len(analyzer.texts)
    if len(raw) > MAX_BYTES:
        report.warn("large-file", 1,
                    f"{len(raw) / 1024:.0f} KB, above about {MAX_BYTES // 1024} KB; "
                    "remove embedded images or repeated shapes if you can")
    return finish(result, report)


def finish(result, report):
    result["issues"] = sorted(report.issues, key=lambda i: i["line"])
    result["warnings"] = report.warnings
    result["pass"] = not report.issues
    return result


def read_input(path):
    try:
        if path is None or path == "-":
            raw = sys.stdin.buffer.read()
        else:
            with open(path, "rb") as fh:
                raw = fh.read()
        raw.decode("utf-8-sig")
        return raw
    except (OSError, UnicodeDecodeError) as exc:
        raise InputError(f"cannot read input {path or '-'}: {exc}")


def _positive(value):
    try:
        number = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a number: {value!r}")
    if number <= 0:
        raise argparse.ArgumentTypeError(f"must be above 0: {value!r}")
    return int(number) if number.is_integer() else number


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Check a hand-written SVG (safety, canvas, readable text) and print JSON.")
    parser.add_argument("file", nargs="?", default=None,
                        help="SVG file, or - for stdin (default: stdin)")
    helps = {"display_width": "recommendation (warning): width in px the image is "
                              "usually shown at",
             "min_font_px": "recommendation (warning): smallest text in px at "
                            "--display-width",
             "floor_width": "floor (issue): widest viewBox that keeps --floor-font-px "
                            "as is",
             "floor_font_px": "floor (issue): smallest text in viewBox units up to "
                              "--floor-width"}
    for key, default in DEFAULT_LIMITS.items():
        parser.add_argument("--" + key.replace("_", "-"), dest=key, type=_positive,
                            metavar="N", default=None,
                            help=f"{helps[key]} (default {default})")
    parser.add_argument("--sheet", action="store_true",
                        help=f"overview sheet: same as --display-width "
                             f"{SHEET_DISPLAY_WIDTH} (an explicit --display-width wins)")
    args = parser.parse_args(argv)  # argparse exits with 2 on usage errors
    if args.sheet and args.display_width is None:
        args.display_width = SHEET_DISPLAY_WIDTH
    for key, default in DEFAULT_LIMITS.items():
        if getattr(args, key) is None:
            setattr(args, key, default)

    try:
        raw = read_input(args.file)
    except InputError as exc:
        print(f"svg_check: {exc}", file=sys.stderr)
        return EXIT_USAGE

    result = analyze(raw, {key: getattr(args, key) for key in DEFAULT_LIMITS})
    out = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    sys.stdout.buffer.write(out.encode("utf-8"))
    sys.stdout.buffer.flush()
    return EXIT_PASS if result["pass"] else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
