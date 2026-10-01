"""Alignment and error rates for Vietnamese OCR.

Two things here that ordinary CER code does not do, and that this thesis needs:

1. Error CATEGORISATION. A substitution is split into base-letter, tone-mark
   and letter-diacritic errors, so an aggregate rate can be decomposed into
   the parts of the script that carry meaning in Vietnamese.

2. RUNAWAY HANDLING. A document VLM that falls into a repetition loop emits
   thousands of junk characters and produces a per-page CER of 20 or 40. A
   handful of those pages will swing a macro-average by tens of points and
   make a baseline look unstable for reasons that have nothing to do with
   recognition. Runaway pages are flagged, capped, and reported as their own
   number rather than being allowed to silently dominate the mean.
"""

from __future__ import annotations

import math
import re
import random
from dataclasses import dataclass, field

try:  # pragma: no cover - import guard
    from .normalize import Grapheme, canonical, graphemes
except ImportError:  # running as a plain script
    from normalize import Grapheme, canonical, graphemes  # type: ignore

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None

EQUAL, SUB, INS, DEL = 0, 1, 2, 3


# --- Alignment ---------------------------------------------------------------


def align(ref: list, hyp: list) -> list[tuple[int, int, int]]:
    """Minimal-cost Levenshtein alignment.

    Returns a list of (op, ref_index, hyp_index); index is -1 where absent.
    Uses numpy for the DP when available; the pure-Python path is identical in
    result, only slower. Never substitute difflib.SequenceMatcher here -- it
    does not minimise edit distance, so its opcodes give different (smaller)
    error counts and your CER would not be comparable to anyone else's.
    """
    n, m = len(ref), len(hyp)
    if n == 0:
        return [(INS, -1, j) for j in range(m)]
    if m == 0:
        return [(DEL, i, -1) for i in range(n)]

    if np is not None:
        # bt[i][j]: 0 equal, 1 sub, 2 ins (from left), 3 del (from above)
        bt = np.zeros((n + 1, m + 1), dtype=np.uint8)
        prev = np.arange(m + 1, dtype=np.int32)
        bt[0, 1:] = INS
        hyp_arr = hyp
        for i in range(1, n + 1):
            cur = np.empty(m + 1, dtype=np.int32)
            cur[0] = i
            bt[i, 0] = DEL
            r = ref[i - 1]
            same = np.fromiter((r == h for h in hyp_arr), dtype=bool, count=m)
            diag = prev[:-1] + (~same)
            for j in range(1, m + 1):
                d = diag[j - 1]
                up = prev[j] + 1
                left = cur[j - 1] + 1
                best = d
                op = EQUAL if same[j - 1] else SUB
                if up < best:
                    best, op = up, DEL
                if left < best:
                    best, op = left, INS
                cur[j] = best
                bt[i, j] = op
            prev = cur
    else:  # pragma: no cover
        bt = [[0] * (m + 1) for _ in range(n + 1)]
        prev = list(range(m + 1))
        for j in range(1, m + 1):
            bt[0][j] = INS
        for i in range(1, n + 1):
            cur = [i] + [0] * m
            bt[i][0] = DEL
            r = ref[i - 1]
            for j in range(1, m + 1):
                eq = r == hyp[j - 1]
                best = prev[j - 1] + (0 if eq else 1)
                op = EQUAL if eq else SUB
                if prev[j] + 1 < best:
                    best, op = prev[j] + 1, DEL
                if cur[j - 1] + 1 < best:
                    best, op = cur[j - 1] + 1, INS
                cur[j] = best
                bt[i][j] = op
            prev = cur

    ops: list[tuple[int, int, int]] = []
    i, j = n, m
    while i > 0 or j > 0:
        if i == 0:
            ops.append((INS, -1, j - 1)); j -= 1; continue
        if j == 0:
            ops.append((DEL, i - 1, -1)); i -= 1; continue
        op = int(bt[i][j]) if np is None else int(bt[i, j])
        if op in (EQUAL, SUB):
            ops.append((op, i - 1, j - 1)); i -= 1; j -= 1
        elif op == DEL:
            ops.append((DEL, i - 1, -1)); i -= 1
        else:
            ops.append((INS, -1, j - 1)); j -= 1
    ops.reverse()
    return ops


def edit_distance(ref: list, hyp: list) -> int:
    return sum(1 for op, _, _ in align(ref, hyp) if op != EQUAL)


# --- Per-page counts ---------------------------------------------------------


@dataclass
class PageCounts:
    page_id: str = ""
    # character level
    ref_chars: int = 0
    char_edits: int = 0
    # syllable ("word") level
    ref_tokens: int = 0
    token_edits: int = 0
    # categorised grapheme-level substitutions
    base_sub: int = 0
    tone_sub: int = 0
    letter_sub: int = 0
    base_ins: int = 0
    base_del: int = 0
    # whitespace
    ref_spaces: int = 0
    ws_errors: int = 0
    # denominators for the diacritic rates
    ref_diacritic_graphemes: int = 0
    ref_tone_graphemes: int = 0
    # health
    runaway: bool = False
    empty_hyp: bool = False
    markup_chars: int = 0
    hyp_chars: int = 0
    strata: dict = field(default_factory=dict)

    @property
    def cer(self) -> float:
        return self.char_edits / self.ref_chars if self.ref_chars else 0.0

    @property
    def wer(self) -> float:
        return self.token_edits / self.ref_tokens if self.ref_tokens else 0.0


RUNAWAY_LENGTH_RATIO = 3.0
RUNAWAY_MIN_REF = 50


def detect_runaway(ref: str, hyp: str, ratio: float = RUNAWAY_LENGTH_RATIO) -> bool:
    """Flag hypotheses that are implausibly longer than the reference.

    A 0.9B VLM on an out-of-domain dense page can loop on an n-gram until it
    hits max_new_tokens. Those pages are a decoding failure, not a recognition
    result, and mixing them into the mean is what makes a baseline swing by
    tens of CER points between seeds.
    """
    if len(ref) < RUNAWAY_MIN_REF:
        return False
    return len(hyp) > ratio * len(ref)


_MARKUP_PATTERNS = [
    re.compile(r"^[ \t]{0,3}#{1,6}[ \t]", re.M),   # Markdown heading marker
    re.compile(r"\*\*|__"),                         # paired emphasis markers
    re.compile(r"</?[A-Za-z][A-Za-z0-9]*(?:\s[^<>]*)?>"),  # HTML tags
    re.compile(r"\$\$|\\\(|\\\)|\\\[|\\\]"),       # LaTeX display / inline delimiters
]


def count_markup(text: str) -> int:
    """Characters of unambiguous markup in a hypothesis. AUDIT ONLY.

    Nothing is stripped. The count exists so that a base model emitting
    Markdown and an adapted model that learned plain-text targets cannot
    silently turn a formatting difference into an apparent recognition gain.
    """
    return sum(len(m.group(0)) for pat in _MARKUP_PATTERNS for m in pat.finditer(text))


def score_page(
    ref_raw: str,
    hyp_raw: str,
    page_id: str = "",
    *,
    cap_runaway: bool = True,
    strata: dict | None = None,
    **norm_kwargs,
) -> PageCounts:
    ref = canonical(ref_raw, **norm_kwargs)
    hyp = canonical(hyp_raw, **norm_kwargs)

    c = PageCounts(page_id=page_id, strata=dict(strata or {}))
    c.markup_chars = count_markup(hyp_raw)
    c.ref_chars = len(ref)
    c.hyp_chars = len(hyp)
    c.empty_hyp = len(hyp.strip()) == 0 and len(ref.strip()) > 0
    c.runaway = detect_runaway(ref, hyp)

    if c.runaway and cap_runaway:
        # Cap the damage at "everything wrong" instead of letting a loop
        # contribute CER 40. The page still counts, and still shows up in the
        # runaway rate, which is the number that should be reported.
        c.char_edits = c.ref_chars
        c.ref_tokens = len(ref.split())
        c.token_edits = c.ref_tokens
        c.ref_spaces = ref.count(" ")
        c.ws_errors = c.ref_spaces
        g_ref = graphemes(ref)
        c.ref_diacritic_graphemes = sum(1 for g in g_ref if g.has_diacritic)
        c.ref_tone_graphemes = sum(1 for g in g_ref if g.tone)
        # Deliberately NOT attributed to any error category. A repetition loop
        # is a decoding failure; calling its output "base-letter errors" would
        # pollute the breakdown that RQ2 depends on. The page still counts in
        # CER and in the runaway rate.
        return c

    # --- character level, on graphemes so diacritics travel with their letter
    g_ref, g_hyp = graphemes(ref), graphemes(hyp)
    c.ref_diacritic_graphemes = sum(1 for g in g_ref if g.has_diacritic)
    c.ref_tone_graphemes = sum(1 for g in g_ref if g.tone)
    c.ref_spaces = sum(1 for g in g_ref if g.base == " ")

    ops = align(g_ref, g_hyp)
    for op, ri, hi in ops:
        if op == EQUAL:
            continue
        c.char_edits += 1
        if op == SUB:
            a, b = g_ref[ri], g_hyp[hi]
            if a.base == " " or b.base == " ":
                c.ws_errors += 1
            elif a.base != b.base:
                c.base_sub += 1
            elif a.tone != b.tone:
                c.tone_sub += 1
            elif a.letter != b.letter:
                c.letter_sub += 1
        elif op == DEL:
            if g_ref[ri].base == " ":
                c.ws_errors += 1
            else:
                c.base_del += 1
        else:  # INS
            if g_hyp[hi].base == " ":
                c.ws_errors += 1
            else:
                c.base_ins += 1

    # --- syllable level. In Vietnamese, whitespace separates SYLLABLES, not
    # words, so this is a syllable error rate. Report it as WER for
    # comparability with the literature, but say what it measures.
    rt, ht = ref.split(), hyp.split()
    c.ref_tokens = len(rt)
    c.token_edits = edit_distance(rt, ht)
    return c


# --- Corpus aggregation ------------------------------------------------------


def _ratio(num: int, den: int) -> float:
    return num / den if den else float("nan")


def aggregate(pages: list[PageCounts]) -> dict:
    """Micro rates are primary. Macro is reported alongside so that a gap
    between the two immediately reveals outlier-driven instability."""
    n = len(pages)
    tot_chars = sum(p.ref_chars for p in pages)
    tot_edits = sum(p.char_edits for p in pages)
    tot_tokens = sum(p.ref_tokens for p in pages)
    tot_tok_edits = sum(p.token_edits for p in pages)
    tot_dia = sum(p.ref_diacritic_graphemes for p in pages)
    tot_tone = sum(p.ref_tone_graphemes for p in pages)
    tot_spaces = sum(p.ref_spaces for p in pages)

    dia_err = sum(p.tone_sub + p.letter_sub for p in pages)
    tone_err = sum(p.tone_sub for p in pages)

    per_page_cer = [p.cer for p in pages]
    return {
        "n_pages": n,
        "cer_micro": _ratio(tot_edits, tot_chars),
        "cer_macro": sum(per_page_cer) / n if n else float("nan"),
        "cer_macro_sd": _sd(per_page_cer),
        "cer_median": _median(per_page_cer),
        "wer_micro": _ratio(tot_tok_edits, tot_tokens),
        "der": _ratio(dia_err, tot_dia),
        "ter": _ratio(tone_err, tot_tone),
        "wser": _ratio(sum(p.ws_errors for p in pages), tot_spaces),
        "breakdown": {
            "base_sub": sum(p.base_sub for p in pages),
            "tone_sub": tone_err,
            "letter_diacritic_sub": sum(p.letter_sub for p in pages),
            "base_ins": sum(p.base_ins for p in pages),
            "base_del": sum(p.base_del for p in pages),
            "whitespace": sum(p.ws_errors for p in pages),
        },
        "health": {
            "runaway_pages": sum(1 for p in pages if p.runaway),
            "runaway_rate": _ratio(sum(1 for p in pages if p.runaway), n),
            "empty_pages": sum(1 for p in pages if p.empty_hyp),
            "empty_rate": _ratio(sum(1 for p in pages if p.empty_hyp), n),
            "markup_pages": sum(1 for p in pages if p.markup_chars > 0),
            "markup_chars": sum(p.markup_chars for p in pages),
        },
        "denominators": {
            "ref_chars": tot_chars,
            "ref_tokens": tot_tokens,
            "ref_diacritic_graphemes": tot_dia,
            "ref_tone_graphemes": tot_tone,
            "ref_spaces": tot_spaces,
        },
    }


def _sd(xs: list[float]) -> float:
    if len(xs) < 2:
        return float("nan")
    mu = sum(xs) / len(xs)
    return math.sqrt(sum((x - mu) ** 2 for x in xs) / (len(xs) - 1))


def _median(xs: list[float]) -> float:
    if not xs:
        return float("nan")
    s = sorted(xs)
    k = len(s) // 2
    return s[k] if len(s) % 2 else (s[k - 1] + s[k]) / 2


# --- Uncertainty and paired comparison ---------------------------------------


def bootstrap_ci(pages: list[PageCounts], metric="cer_micro", n_boot=1000, seed=13):
    """Percentile CI by resampling PAGES, not characters.

    Pages are the independent unit; characters within a page are not. A
    character-level bootstrap would report an interval several times too
    narrow, which is how small gold sets end up with unjustifiably confident
    claims.
    """
    rng = random.Random(seed)
    n = len(pages)
    if n == 0:
        return (float("nan"), float("nan"))
    draws = []
    for _ in range(n_boot):
        sample = [pages[rng.randrange(n)] for _ in range(n)]
        draws.append(aggregate(sample)[metric])
    draws.sort()
    lo = draws[int(0.025 * n_boot)]
    hi = draws[min(int(0.975 * n_boot), n_boot - 1)]
    return (lo, hi)


def book_of(page_id: str) -> str:
    """The book a page belongs to, from a `<book>/<page>` page id (VieBookRead's form)."""
    if "/" not in page_id:
        raise ValueError(f"page id {page_id!r} has no '<book>/' prefix, so it cannot be clustered by book")
    return page_id.split("/", 1)[0]


def _groups(pairs, cluster: str):
    """Index groups for the bootstrap: None resamples pages; "book" resamples whole books."""
    if cluster == "page":
        return None
    if cluster != "book":
        raise ValueError(f"unknown cluster unit {cluster!r}")
    by_book: dict = {}
    for i, (b, _) in enumerate(pairs):
        by_book.setdefault(book_of(b.page_id), []).append(i)
    return list(by_book.values())


def _draw(rng, n, groups):
    if groups is None:
        return [rng.randrange(n) for _ in range(n)]
    return [i for _ in range(len(groups)) for i in groups[rng.randrange(len(groups))]]


def paired_delta(
    base: list[PageCounts],
    adapted: list[PageCounts],
    metric="cer_micro",
    n_boot=1000,
    seed=13,
    cluster="page",
):
    """Paired bootstrap on the SAME pages.

    This is the number the thesis claim rests on. "Relative CER reduction of
    at least 20%" is a statement about a difference, so it needs a confidence
    interval on the difference -- not two separate intervals that a reader is
    left to eyeball for overlap. Pairing also removes page difficulty as a
    source of variance, which makes the test considerably more sensitive on a
    small gold set.

    cluster="book" resamples whole books instead of pages. Pages of one book
    share typeface, paper and scan, so they are not independent; the book
    interval is the honest one when the claim is about unseen books.
    """
    by_id = {p.page_id: p for p in adapted}
    pairs = [(b, by_id[b.page_id]) for b in base if b.page_id in by_id]
    if not pairs:
        raise ValueError("no page_id overlap between the two runs")
    groups = _groups(pairs, cluster)

    b_all = aggregate([b for b, _ in pairs])[metric]
    a_all = aggregate([a for _, a in pairs])[metric]
    abs_delta = a_all - b_all
    rel_delta = abs_delta / b_all if b_all else float("nan")

    rng = random.Random(seed)
    n = len(pairs)
    rels, wins = [], 0
    for _ in range(n_boot):
        idx = _draw(rng, n, groups)
        bb = aggregate([pairs[i][0] for i in idx])[metric]
        aa = aggregate([pairs[i][1] for i in idx])[metric]
        r = (aa - bb) / bb if bb else float("nan")
        rels.append(r)
        if aa < bb:
            wins += 1
    rels.sort()
    return {
        "metric": metric,
        "cluster": cluster,
        "n_clusters": n if groups is None else len(groups),
        "n_paired_pages": n,
        "base": b_all,
        "adapted": a_all,
        "absolute_delta": abs_delta,
        "relative_delta": rel_delta,
        "relative_delta_ci95": (
            rels[int(0.025 * n_boot)],
            rels[min(int(0.975 * n_boot), n_boot - 1)],
        ),
        "p_adapted_better": wins / n_boot,
    }


# --- Where did the reduction come from? ---------------------------------------

SHARE_CATEGORIES = (
    "tone_sub", "letter_sub", "base_sub", "base_ins", "base_del",
    "ws_errors", "runaway",
)


def _category_counts(pages: list[PageCounts]) -> dict:
    """Every character edit lands in exactly one category.

    Runaway pages are capped at CER 1.0 and deliberately kept out of the
    recognition categories, so their edits form a category of their own. With
    it, the categories sum exactly to total character edits.
    """
    out = {k: 0 for k in SHARE_CATEGORIES}
    for p in pages:
        if p.runaway:
            out["runaway"] += p.char_edits
            continue
        out["tone_sub"] += p.tone_sub
        out["letter_sub"] += p.letter_sub
        out["base_sub"] += p.base_sub
        out["base_ins"] += p.base_ins
        out["base_del"] += p.base_del
        out["ws_errors"] += p.ws_errors
    out["total"] = sum(p.char_edits for p in pages)
    return out


def _shares(base_counts: dict, adapted_counts: dict) -> dict:
    total = base_counts["total"] - adapted_counts["total"]
    red = {k: base_counts[k] - adapted_counts[k] for k in SHARE_CATEGORIES}
    red["diacritic"] = red["tone_sub"] + red["letter_sub"]
    if total <= 0:
        share = {k: float("nan") for k in red}
    else:
        share = {k: v / total for k, v in red.items()}
    return {"total_reduction": total, "reduction": red, "share": share}


def reduction_shares(base, adapted, n_boot=1000, seed=13, cluster="page"):
    """Decompose the absolute reduction in character edits by error category.

    This is the measurement for the proposal's second target: that the largest
    share of the reduction falls in tone marks and other diacritics. The
    diacritic share is (reduction in tone errors + reduction in letter-
    diacritic errors) / reduction in total character edits, on paired pages.

    Shares can be negative (a category got worse) or exceed 1 (other
    categories got worse). They are undefined when total edits did not fall.
    """
    by_id = {p.page_id: p for p in adapted}
    pairs = [(b, by_id[b.page_id]) for b in base if b.page_id in by_id]
    if not pairs:
        raise ValueError("no page_id overlap between the two runs")

    groups = _groups(pairs, cluster)
    point = _shares(_category_counts([b for b, _ in pairs]),
                    _category_counts([a for _, a in pairs]))

    others = [k for k in SHARE_CATEGORIES if k not in ("tone_sub", "letter_sub")]
    rng = random.Random(seed)
    n = len(pairs)
    draws, largest = [], 0
    for _ in range(n_boot):
        idx = _draw(rng, n, groups)
        r = _shares(_category_counts([pairs[i][0] for i in idx]),
                    _category_counts([pairs[i][1] for i in idx]))
        d = r["share"]["diacritic"]
        if d == d:
            draws.append(d)
            if all(r["reduction"]["diacritic"] > r["reduction"][k] for k in others):
                largest += 1
    draws.sort()
    ci = ((draws[int(0.025 * len(draws))],
           draws[min(int(0.975 * len(draws)), len(draws) - 1)])
          if draws else (float("nan"), float("nan")))
    point.update({
        "n_paired_pages": n,
        "cluster": cluster,
        "diacritic_share_ci95": ci,
        "p_diacritic_largest": largest / n_boot,
        "n_valid_resamples": len(draws),
    })
    return point
