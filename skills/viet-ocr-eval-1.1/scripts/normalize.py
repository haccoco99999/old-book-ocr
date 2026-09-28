"""Canonical text form for Vietnamese OCR scoring.

Every metric in this skill is computed on the output of `canonical()`.
Applying the SAME transform to reference and hypothesis is what makes the
numbers comparable across runs, models and months.

This is a SCORING form, not an orthographic recommendation. Never apply it to
text that is shown to a user, exported, or stored as ground truth.
"""

from __future__ import annotations

import re
import unicodedata

# --- Vietnamese combining-mark inventory (post-NFD) -------------------------

TONE_MARKS = {
    "\u0300",  # huyen   (grave)
    "\u0301",  # sac     (acute)
    "\u0303",  # nga     (tilde)
    "\u0309",  # hoi     (hook above)
    "\u0323",  # nang    (dot below)
}

# Marks that are part of LETTER IDENTITY, not tone: a-breve, circumflex, horn.
LETTER_MARKS = {
    "\u0302",  # circumflex  -> a^ e^ o^
    "\u0306",  # breve       -> a(
    "\u031b",  # horn        -> o+ u+
}

# U+0110/U+0111 (D/d with stroke) have NO canonical decomposition, so NFD
# leaves them atomic and they would be scored as a wholly different base
# letter from "d". Decompose them ourselves with a private-use sentinel so
# "dinh" vs "dinh-with-stroke" is categorised as a letter-diacritic error.
D_STROKE = "\ue000"
_D_SPLIT = {"\u0110": "D" + D_STROKE, "\u0111": "d" + D_STROKE}
_D_JOIN = {v: k for k, v in _D_SPLIT.items()}

ALL_MARKS = TONE_MARKS | LETTER_MARKS | {D_STROKE}

VOWELS = set("aeiouyAEIOUY")

# --- Character folding -------------------------------------------------------

# Conservative default: only characters that carry no information difference
# for OCR scoring. Anything that could be a real recognition error stays.
DEFAULT_CHARMAP = {
    # apostrophes / quotes
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u2032": "'",
    "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u2033": '"',
    # dashes -> hyphen-minus
    "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-",
    "\u2014": "-", "\u2015": "-", "\u2212": "-",
    # ellipsis
    "\u2026": "...",
    # invisible / zero-width
    "\u200b": "", "\u200c": "", "\u200d": "", "\ufeff": "", "\u00ad": "",
    # non-breaking / exotic spaces -> plain space
    "\u00a0": " ", "\u2007": " ", "\u202f": " ", "\u2009": " ", "\u3000": " ",
}

_WS_RUN = re.compile(r"\s+")


def fold_chars(text: str, charmap: dict | None = None) -> str:
    cm = DEFAULT_CHARMAP if charmap is None else charmap
    return "".join(cm.get(ch, ch) for ch in text)


# --- Tone-placement canonicalisation ----------------------------------------
# Vietnamese admits two legal tone placements for oa/oe/uy nuclei:
#   hoa-with-grave-on-o   (traditional)  vs  hoa-with-grave-on-a   (modern)
# Both are correct. Counting them as errors inflates CER by a typesetting
# convention that has nothing to do with recognition quality.
#
# The fix is a MECHANICAL canonical position: within each maximal run of vowel
# letters in a token, move every tone mark onto the first vowel of that run.
# This is not standard orthography; it does not need to be. It is a normal
# form, applied identically to both sides, so the style difference cancels.


def canonicalize_tone_position(text_nfd: str) -> str:
    """Move tone marks to the first vowel of each vowel run. Input must be NFD
    (with D-stroke already split). Output is NFD."""
    out: list[str] = []
    i = 0
    n = len(text_nfd)
    while i < n:
        ch = text_nfd[i]
        if ch not in VOWELS:
            out.append(ch)
            i += 1
            continue

        # Collect a maximal vowel run: vowel letters plus their combining marks.
        run: list[tuple[str, list[str]]] = []
        while i < n and text_nfd[i] in VOWELS:
            base = text_nfd[i]
            i += 1
            marks: list[str] = []
            while i < n and text_nfd[i] in ALL_MARKS:
                marks.append(text_nfd[i])
                i += 1
            run.append((base, marks))

        # Pull every tone mark out of the run, keep letter marks in place.
        tones: list[str] = []
        stripped: list[tuple[str, list[str]]] = []
        for base, marks in run:
            keep = [m for m in marks if m not in TONE_MARKS]
            tones.extend(m for m in marks if m in TONE_MARKS)
            stripped.append((base, keep))

        # Re-attach tones to the first vowel(s) of the run. More than one tone
        # in a run only happens on malformed OCR output; spread them left to
        # right so the information is preserved rather than silently dropped.
        for idx, tone in enumerate(tones):
            pos = min(idx, len(stripped) - 1)
            stripped[pos][1].append(tone)

        for base, marks in stripped:
            out.append(base)
            # Stable mark order so identical content compares equal.
            out.extend(sorted(marks))
    return "".join(out)


# --- Public API --------------------------------------------------------------


def to_nfd(text: str) -> str:
    """NFD with D-stroke split out into base + sentinel mark."""
    text = unicodedata.normalize("NFD", text)
    for k, v in _D_SPLIT.items():
        text = text.replace(k, v)
    return text


def from_nfd(text: str) -> str:
    for k, v in _D_JOIN.items():
        text = text.replace(k, v)
    return unicodedata.normalize("NFC", text)


def canonical(
    text: str,
    *,
    collapse_whitespace: bool = True,
    canonical_tone: bool = True,
    lowercase: bool = False,
    charmap: dict | None = None,
) -> str:
    """The one normal form every metric is computed on. Returns NFC.

    collapse_whitespace: every run of whitespace becomes a single space, and
        leading/trailing space is stripped. Scanned-page line breaks never
        agree with ebook line breaks, so without this, layout differences
        would dominate CER and hide actual recognition errors. Word-joining
        and word-splitting errors survive collapsing, which is the whitespace
        behaviour that matters in Vietnamese.
    canonical_tone: apply the mechanical tone-position normal form above.
    lowercase: off by default. Report case-sensitive as the primary number.
    """
    text = unicodedata.normalize("NFC", text)
    text = fold_chars(text, charmap)
    text = to_nfd(text)
    if canonical_tone:
        text = canonicalize_tone_position(text)
    text = from_nfd(text)
    if lowercase:
        text = text.lower()
    if collapse_whitespace:
        text = _WS_RUN.sub(" ", text).strip()
    return text


# --- Grapheme view (used by the diacritic-aware categoriser) -----------------


class Grapheme:
    """One base letter plus its combining marks, split into tone vs letter."""

    __slots__ = ("base", "tone", "letter")

    def __init__(self, base: str, tone: frozenset, letter: frozenset):
        self.base = base
        self.tone = tone
        self.letter = letter

    @property
    def has_diacritic(self) -> bool:
        return bool(self.tone or self.letter)

    def __eq__(self, other):
        return (
            isinstance(other, Grapheme)
            and self.base == other.base
            and self.tone == other.tone
            and self.letter == other.letter
        )

    def __hash__(self):
        return hash((self.base, self.tone, self.letter))

    def __repr__(self):
        return f"<{self.base}{''.join(sorted(self.tone | self.letter))}>"


def graphemes(text: str) -> list[Grapheme]:
    """Split canonical text into graphemes. Pass text through canonical() first."""
    nfd = to_nfd(text)
    out: list[Grapheme] = []
    i, n = 0, len(nfd)
    while i < n:
        base = nfd[i]
        i += 1
        tone, letter = set(), set()
        while i < n and nfd[i] in ALL_MARKS:
            m = nfd[i]
            (tone if m in TONE_MARKS else letter).add(m)
            i += 1
        out.append(Grapheme(base, frozenset(tone), frozenset(letter)))
    return out
