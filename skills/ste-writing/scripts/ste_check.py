#!/usr/bin/env python3
"""Measure STE-style writing metrics for English text (self-check).

Usage:
    python ste_check.py [FILE|-] [--strictness relaxed|strict]
                        [--lang auto|en|other] [--replacements PATH]

Reads FILE (or stdin when FILE is omitted or "-") and prints JSON metrics on
stdout (UTF-8). Exit code: 0 = pass (or metrics not available), 1 = fail,
2 = usage or input error. Python standard library only.

Output shape:
    {"language": "en"|"other", "metrics_available": bool, "strictness": str,
     "sentences": [{"text", "kind", "words", "limit", "over_limit", "passive",
                    "progressive", "perfect", "noun_clusters",
                    "replacement_hits"}],
     "totals": {"sentences", "over_limit", "passive", "progressive", "perfect",
                "noun_clusters", "replacement_hits", "over_limit_ratio",
                "passive_progressive_ratio"},
     "pass": bool}
When metrics are not available, sentences is [], totals is {}, pass is null
and a "note" string explains why.

Method (all detection is APPROXIMATE and heuristic, not a grammar parser):
- Exempt content is removed before measuring: fenced code blocks, inline
  code, blockquote lines (starting with ">") and Markdown heading lines.
- Language "auto": if more than 30% of the letters (after exempt removal) are
  CJK ideographs, kana or hangul, the language is "other" and no metrics are
  computed. "--lang en" and "--lang other" force the choice.
- Sentences split on . ! ? followed by whitespace or end of text. Each list
  item line is its own unit. e.g. / i.e. / etc. and a few more do not split.
- A unit is "procedural" if it is a numbered list item or starts with a verb
  from a small built-in list of instruction verbs; otherwise "descriptive".
  Limits: procedural 20 words, descriptive 25. Exactly the limit is not over.
  The list marker is not counted as a word.
- passive: a form of "be", optionally one -ly adverb, then a word ending in
  -ed or a built-in irregular past participle. progressive: "be" + a word
  ending in -ing. perfect: have/has/had (optional -ly adverb) + participle.
  Misses and false positives are possible (e.g. adjectives that end in -ed).
- noun_clusters: runs of 4 or more consecutive alphabetic words that are not in
  a built-in stoplist (function words, auxiliaries, -ly adverbs, instruction
  verbs). Very rough: other verbs and adjectives can join a run.
- replacement list: a Markdown table; the first column of each data row is
  the term (case-insensitive, whole words, may have several words). Header and
  separator rows are skipped. Without a list, replacement hits are zero.
- Totals: over_limit_ratio = over_limit / sentences;
  passive_progressive_ratio = (passive + progressive) / sentences (0.0 when
  there are no sentences).
- pass, relaxed: over_limit_ratio <= 0.10 and passive_progressive_ratio <= 0.05.
  pass, strict: relaxed AND no replacement hits AND no perfect forms AND no noun
  clusters AND no passive in procedural sentences.
"""

import argparse
import json
import re
import sys

EXIT_PASS, EXIT_FAIL, EXIT_USAGE = 0, 1, 2

LIMITS = {"procedural": 20, "descriptive": 25}
MAX_OVER_LIMIT_RATIO = 0.10
MAX_PASSIVE_PROGRESSIVE_RATIO = 0.05
CJK_THRESHOLD = 0.30
NOUN_CLUSTER_MIN = 4

INSTRUCTION_VERBS = frozenset("""
open close run set install make remove check add start stop use do click
select enter turn push pull connect disconnect replace apply keep read write
create delete
""".split())

BE_FORMS = frozenset("am is are was were be been being".split())
HAVE_FORMS = frozenset("have has had".split())

IRREGULAR_PARTICIPLES = frozenset("""
done made set put shown known given taken written seen built sent kept held
found run been gone got gotten begun broken chosen drawn driven eaten fallen
felt hidden left lost met paid read said sold stood told thought understood
worn won
""".split())

# Words ending in -ed or -ing that are not verb forms in the patterns above.
NOT_PARTICIPLES = frozenset("""
need feed seed speed bleed breed weed heed reed deed greed creed indeed
hundred bed red shed sled
""".split())
NOT_PROGRESSIVE = frozenset("""
being thing something nothing anything everything morning evening king ring
string spring wing sing bring ceiling building
""".split())

ABBREVIATIONS = ("e.g.", "i.e.", "etc.", "vs.", "cf.", "approx.", "no.")

FUNCTION_WORDS = frozenset("""
a an the this that these those some any each every no not
of in on at by for with without from to into onto over under about after before
between through during against within upon per via than as like
i you he she it we they me him her us them my your his its our their
and or but nor so yet if then else when while where which who whom whose what
how why because since although though unless until whether
am is are was were be been being have has had do does did
can could will would shall should may might must
also only just very too more most less least much many few all both either
neither other another such same here there now once again still even ever
never always often
""".split())

STOPLIST = FUNCTION_WORDS | INSTRUCTION_VERBS

_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:['’\-][A-Za-z0-9]+)*")
_ALPHA_RE = re.compile(r"[A-Za-z]+")
_LIST_RE = re.compile(r"^\s*(?:(\d+[.)])|[-*+])\s+(.*)$")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_SEPARATOR_CELL_RE = re.compile(r"^:?-{1,}:?$")


class InputError(Exception):
    pass


# --- exempt content -------------------------------------------------------

def strip_exempt(text):
    """Remove fenced code, blockquote and heading lines, and inline code."""
    kept = []
    fence = None
    for line in text.splitlines():
        stripped = line.lstrip()
        if fence is None:
            m = re.match(r"(`{3,}|~{3,})", stripped)
            if m:
                fence = m.group(1)[0] * len(m.group(1))
                continue
            if stripped.startswith(">") or stripped.startswith("#"):
                continue
            kept.append(line)
        else:
            if stripped.startswith(fence):
                fence = None
    text = "\n".join(kept)
    text = re.sub(r"``.+?``|`[^`\n]*`", "", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)  # links keep their label
    return text.replace("*", "")


# --- language -------------------------------------------------------------

def _is_cjk(ch):
    cp = ord(ch)
    return (0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF
            or 0x3040 <= cp <= 0x30FF or 0xAC00 <= cp <= 0xD7AF
            or 0xF900 <= cp <= 0xFAFF)


def detect_language(text):
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return "en"
    cjk = sum(1 for c in letters if _is_cjk(c))
    return "other" if cjk / len(letters) > CJK_THRESHOLD else "en"


# --- splitting ------------------------------------------------------------

def split_units(text):
    """Return a list of (sentence_text, is_numbered_item)."""
    units = []
    paragraph = []

    def flush():
        if paragraph:
            for s in split_sentences(" ".join(paragraph)):
                units.append((s, False))
            paragraph.clear()

    for line in text.splitlines():
        if not line.strip():
            flush()
            continue
        m = _LIST_RE.match(line)
        if m:
            flush()
            for s in split_sentences(m.group(2)):
                units.append((s, m.group(1) is not None))
        else:
            paragraph.append(line.strip())
    flush()
    return units


def split_sentences(text):
    protected = text
    for i, abbr in enumerate(ABBREVIATIONS):
        protected = re.sub(re.escape(abbr), f"\x00{i}\x00", protected,
                           flags=re.IGNORECASE)
    parts = _SENTENCE_SPLIT_RE.split(protected.strip())
    result = []
    for part in parts:
        for i, abbr in enumerate(ABBREVIATIONS):
            part = part.replace(f"\x00{i}\x00", abbr)
        part = part.strip()
        if _WORD_RE.search(part):
            result.append(part)
    return result


# --- per-sentence measures ------------------------------------------------

def _is_participle(tok):
    if tok in IRREGULAR_PARTICIPLES:
        return True
    return tok.endswith("ed") and len(tok) >= 4 and tok not in NOT_PARTICIPLES


def _is_ing(tok):
    return tok.endswith("ing") and len(tok) > 4 and tok not in NOT_PROGRESSIVE


def count_verb_forms(tokens):
    passive = progressive = perfect = 0
    for i, tok in enumerate(tokens):
        if tok not in BE_FORMS and tok not in HAVE_FORMS:
            continue
        j = i + 1
        if j + 1 < len(tokens) and tokens[j].endswith("ly") and len(tokens[j]) > 3:
            j += 1
        if j >= len(tokens):
            continue
        nxt = tokens[j]
        if tok in BE_FORMS:
            if _is_participle(nxt) and nxt != "been":
                passive += 1
            elif _is_ing(nxt):
                progressive += 1
        elif _is_participle(nxt):
            perfect += 1
    return passive, progressive, perfect


def find_noun_clusters(sentence):
    clusters = []
    run = []
    # Tokenize on whitespace so that digits or hyphens break a run.
    for raw in re.findall(r"\S+", sentence):
        core = raw.strip(".,;:!?()[]{}\"'“”‘’")
        punct_after = raw.rstrip(".,;:!?)]}\"'”’") != raw
        word = core.lower()
        is_cluster_word = (
            _ALPHA_RE.fullmatch(core) is not None
            and word not in STOPLIST
            and not (word.endswith("ly") and len(word) > 3)
        )
        if is_cluster_word:
            run.append(core)
            if punct_after:
                _close_run(run, clusters)
        else:
            _close_run(run, clusters)
    _close_run(run, clusters)
    return clusters


def _close_run(run, clusters):
    if len(run) >= NOUN_CLUSTER_MIN:
        clusters.append(" ".join(run))
    run.clear()


def load_replacements(path):
    try:
        with open(path, encoding="utf-8-sig") as fh:
            lines = fh.read().splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise InputError(f"cannot read replacement list {path}: {exc}")
    rows = []
    for line in lines:
        line = line.strip()
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            rows.append(cells)
    terms = []
    for i, cells in enumerate(rows):
        if all(_SEPARATOR_CELL_RE.match(c) for c in cells if c) and any(cells):
            continue
        if i + 1 < len(rows) and all(
                _SEPARATOR_CELL_RE.match(c) for c in rows[i + 1] if c) and any(rows[i + 1]):
            continue  # header row
        term = cells[0].strip("`* ").lower() if cells else ""
        if term:
            words = term.split()
            pattern = r"(?<!\w)" + r"\s+".join(re.escape(w) for w in words) + r"(?!\w)"
            terms.append((term, re.compile(pattern, re.IGNORECASE)))
    return terms


def measure_sentence(text, numbered, replacements):
    words = _WORD_RE.findall(text)
    tokens = [w.lower() for w in words]
    first = tokens[0] if tokens else ""
    kind = "procedural" if numbered or first in INSTRUCTION_VERBS else "descriptive"
    limit = LIMITS[kind]
    passive, progressive, perfect = count_verb_forms(tokens)
    hits = []
    for term, pattern in replacements:
        hits.extend(term for _ in pattern.finditer(text))
    return {
        "text": text,
        "kind": kind,
        "words": len(words),
        "limit": limit,
        "over_limit": len(words) > limit,
        "passive": passive,
        "progressive": progressive,
        "perfect": perfect,
        "noun_clusters": find_noun_clusters(text),
        "replacement_hits": hits,
    }


def build_totals(sentences):
    n = len(sentences)
    over = sum(s["over_limit"] for s in sentences)
    passive = sum(s["passive"] for s in sentences)
    progressive = sum(s["progressive"] for s in sentences)
    return {
        "sentences": n,
        "over_limit": over,
        "passive": passive,
        "progressive": progressive,
        "perfect": sum(s["perfect"] for s in sentences),
        "noun_clusters": sum(len(s["noun_clusters"]) for s in sentences),
        "replacement_hits": sum(len(s["replacement_hits"]) for s in sentences),
        "over_limit_ratio": round(over / n, 4) if n else 0.0,
        "passive_progressive_ratio": round((passive + progressive) / n, 4) if n else 0.0,
    }


def evaluate_pass(strictness, sentences, totals):
    ok = (totals["over_limit_ratio"] <= MAX_OVER_LIMIT_RATIO
          and totals["passive_progressive_ratio"] <= MAX_PASSIVE_PROGRESSIVE_RATIO)
    if strictness == "strict":
        ok = (ok
              and totals["replacement_hits"] == 0
              and totals["perfect"] == 0
              and totals["noun_clusters"] == 0
              and not any(s["kind"] == "procedural" and s["passive"] for s in sentences))
    return ok


def analyze(text, strictness="relaxed", lang="auto", replacements=()):
    cleaned = strip_exempt(text)
    language = detect_language(cleaned) if lang == "auto" else lang
    if language == "other":
        return {
            "language": "other",
            "metrics_available": False,
            "strictness": strictness,
            "sentences": [],
            "totals": {},
            "pass": None,
            "note": "Metrics are available for English text only.",
        }
    sentences = [measure_sentence(t, numbered, replacements)
                 for t, numbered in split_units(cleaned)]
    totals = build_totals(sentences)
    return {
        "language": "en",
        "metrics_available": True,
        "strictness": strictness,
        "sentences": sentences,
        "totals": totals,
        "pass": evaluate_pass(strictness, sentences, totals),
    }


def read_input(path):
    try:
        if path is None or path == "-":
            raw = sys.stdin.buffer.read()
        else:
            with open(path, "rb") as fh:
                raw = fh.read()
        return raw.decode("utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        raise InputError(f"cannot read input {path or '-'}: {exc}")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Measure STE-style writing metrics and print JSON.")
    parser.add_argument("file", nargs="?", default=None,
                        help="input file, or - for stdin (default: stdin)")
    parser.add_argument("--strictness", choices=("relaxed", "strict"),
                        default="relaxed")
    parser.add_argument("--lang", choices=("auto", "en", "other"), default="auto")
    parser.add_argument("--replacements", metavar="PATH", default=None,
                        help="Markdown table with the replacement list")
    args = parser.parse_args(argv)  # argparse exits with 2 on usage errors

    try:
        replacements = load_replacements(args.replacements) if args.replacements else []
        text = read_input(args.file)
    except InputError as exc:
        print(f"ste_check: {exc}", file=sys.stderr)
        return EXIT_USAGE

    result = analyze(text, args.strictness, args.lang, replacements)
    out = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    sys.stdout.buffer.write(out.encode("utf-8"))
    sys.stdout.buffer.flush()
    return EXIT_FAIL if result["pass"] is False else EXIT_PASS


if __name__ == "__main__":
    sys.exit(main())
