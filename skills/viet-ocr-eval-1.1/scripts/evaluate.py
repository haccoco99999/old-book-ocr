#!/usr/bin/env python3
"""viet-ocr-eval CLI.

  score    <manifest.jsonl> --run-name base          -> report.json + report.md
  compare  <base.json> <adapted.json>                -> paired delta + CI
  verify   <train.jsonl> <test.jsonl>                -> split leakage + encoding audit
  selftest                                           -> assert metric definitions

Manifest format, one JSON object per line:

  {"page_id": "bk012_p041", "book_id": "bk012",
   "ref": "...", "hyp": "...",
   "strata": {"degradation": "high", "decade": "1890"}}

`ref_path` / `hyp_path` may be used instead of inline text.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import unicodedata
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from metrics import (  # noqa: E402
    aggregate, bootstrap_ci, paired_delta, reduction_shares, score_page,
)
from normalize import canonical  # noqa: E402

NORM_KEYS = ("collapse_whitespace", "canonical_tone", "lowercase")


def load_manifest(path: str) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as fh:
        for ln, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise SystemExit(f"{path}:{ln}: bad JSON ({e})")
    return rows


def _text(row: dict, key: str) -> str:
    if key in row and row[key] is not None:
        return row[key]
    p = row.get(f"{key}_path")
    if p:
        with open(p, encoding="utf-8") as fh:
            return fh.read()
    return ""


# --- score -------------------------------------------------------------------


def cmd_score(args):
    rows = load_manifest(args.manifest)
    norm = {k: getattr(args, k) for k in NORM_KEYS}
    pages = [
        score_page(
            _text(r, "ref"),
            _text(r, "hyp"),
            page_id=r.get("page_id") or f"row{i}",
            strata=r.get("strata"),
            cap_runaway=not args.no_cap_runaway,
            **norm,
        )
        for i, r in enumerate(rows)
    ]

    report = {
        "run_name": args.run_name,
        "manifest": os.path.abspath(args.manifest),
        "protocol_version": "1.1",
        "normalization": norm,
        "cap_runaway": not args.no_cap_runaway,
        "overall": aggregate(pages),
        "strata": {},
        "pages": [
            {
                "page_id": p.page_id,
                "cer": p.cer,
                "wer": p.wer,
                "ref_chars": p.ref_chars,
                "char_edits": p.char_edits,
                "tone_sub": p.tone_sub,
                "letter_diacritic_sub": p.letter_sub,
                "base_sub": p.base_sub,
                "base_ins": p.base_ins,
                "base_del": p.base_del,
                "ws_errors": p.ws_errors,
                "ref_diacritic_graphemes": p.ref_diacritic_graphemes,
                "ref_tone_graphemes": p.ref_tone_graphemes,
                "ref_spaces": p.ref_spaces,
                "ref_tokens": p.ref_tokens,
                "token_edits": p.token_edits,
                "runaway": p.runaway,
                "empty_hyp": p.empty_hyp,
                "markup_chars": p.markup_chars,
                "strata": p.strata,
            }
            for p in pages
        ],
    }

    if args.bootstrap:
        for m in ("cer_micro", "der", "wer_micro"):
            lo, hi = bootstrap_ci(pages, m, args.bootstrap, args.seed)
            report["overall"].setdefault("ci95", {})[m] = [lo, hi]

    keys = set()
    for p in pages:
        keys.update(p.strata.keys())
    for k in sorted(keys):
        buckets = defaultdict(list)
        for p in pages:
            buckets[str(p.strata.get(k, "unknown"))].append(p)
        report["strata"][k] = {v: aggregate(ps) for v, ps in sorted(buckets.items())}

    out = args.out or f"report_{args.run_name}.json"
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    md = os.path.splitext(out)[0] + ".md"
    with open(md, "w", encoding="utf-8") as fh:
        fh.write(render_markdown(report))
    print(render_markdown(report))
    print(f"\n[written] {out}\n[written] {md}", file=sys.stderr)


def _pct(x):
    return "n/a" if x != x else f"{100 * x:.2f}"


def render_markdown(r: dict) -> str:
    o = r["overall"]
    b, h, d = o["breakdown"], o["health"], o["denominators"]
    ci = o.get("ci95", {})

    def ci_str(m):
        if m not in ci:
            return ""
        lo, hi = ci[m]
        return f" [{_pct(lo)}–{_pct(hi)}]"

    lines = [
        f"# viet-ocr-eval — {r['run_name']}",
        "",
        f"protocol {r['protocol_version']} · normalization {r['normalization']} "
        f"· runaway capped: {r['cap_runaway']} · n = {o['n_pages']} pages",
        "",
        "| metric | % | denominator |",
        "|---|---|---|",
        f"| CER (micro) | {_pct(o['cer_micro'])}{ci_str('cer_micro')} | "
        f"{d['ref_chars']} chars |",
        f"| CER (macro ± sd) | {_pct(o['cer_macro'])} ± {_pct(o['cer_macro_sd'])} | "
        f"per page |",
        f"| CER (median page) | {_pct(o['cer_median'])} | per page |",
        f"| WER (syllable) | {_pct(o['wer_micro'])}{ci_str('wer_micro')} | "
        f"{d['ref_tokens']} syllables |",
        f"| **DER** | {_pct(o['der'])}{ci_str('der')} | "
        f"{d['ref_diacritic_graphemes']} diacritic graphemes |",
        f"| TER (tone only) | {_pct(o['ter'])} | "
        f"{d['ref_tone_graphemes']} tone-bearing graphemes |",
        f"| WSER (whitespace) | {_pct(o['wser'])} | {d['ref_spaces']} spaces |",
        "",
        "## Error breakdown (counts)",
        "",
        "| category | count | share |",
        "|---|---|---|",
    ]
    tot = sum(b.values()) or 1
    label = {
        "base_sub": "base letter (substitution)",
        "tone_sub": "tone mark",
        "letter_diacritic_sub": "letter diacritic (circumflex/breve/horn/stroke)",
        "base_ins": "insertion",
        "base_del": "deletion",
        "whitespace": "whitespace",
    }
    for k, v in b.items():
        lines.append(f"| {label[k]} | {v} | {100 * v / tot:.1f}% |")

    lines += [
        "",
        "## Run health",
        "",
        f"- runaway pages: {h['runaway_pages']} ({_pct(h['runaway_rate'])}%)",
        f"- empty outputs: {h['empty_pages']} ({_pct(h['empty_rate'])}%)",
        f"- pages with markup in the hypothesis: {h.get('markup_pages', 0)} "
        f"({h.get('markup_chars', 0)} markup characters)",
    ]
    if h.get("markup_chars", 0):
        lines.append(
            "- **markup present in hypotheses.** Heading markers, emphasis "
            "markers or tags are being scored as recognition errors. Convert "
            "model output to plain text before scoring, or this run is not "
            "comparable with one that emits plain text."
        )
    gap = abs(o["cer_macro"] - o["cer_micro"])
    if gap == gap and gap > 0.05:
        lines.append(
            f"- **macro and micro CER differ by {_pct(gap)} points** — a small "
            "number of pages is driving the average. Inspect the worst pages "
            "before reporting a mean."
        )

    for name, buckets in r.get("strata", {}).items():
        lines += ["", f"## Stratified by `{name}`", "",
                  "| value | n | CER | DER | WSER |", "|---|---|---|---|---|"]
        for v, s in buckets.items():
            lines.append(
                f"| {v} | {s['n_pages']} | {_pct(s['cer_micro'])} | "
                f"{_pct(s['der'])} | {_pct(s['wser'])} |"
            )
    return "\n".join(lines) + "\n"


# --- compare -----------------------------------------------------------------


def _pages_from_report(path: str):
    from metrics import PageCounts

    with open(path, encoding="utf-8") as fh:
        r = json.load(fh)
    fields = set(PageCounts.__dataclass_fields__)
    out = []
    for p in r["pages"]:
        pc = PageCounts(page_id=p["page_id"])
        for k, v in p.items():
            if k == "letter_diacritic_sub":
                pc.letter_sub = v
            elif k in fields:  # skip cer/wer, which are computed properties
                setattr(pc, k, v)
        out.append(pc)
    return r, out


def cmd_compare(args):
    rb, pb = _pages_from_report(args.base)
    ra, pa = _pages_from_report(args.adapted)

    if rb["normalization"] != ra["normalization"]:
        raise SystemExit(
            "refusing to compare: the two runs used different normalization "
            f"settings ({rb['normalization']} vs {ra['normalization']}). "
            "Re-score both with the same settings."
        )

    res = {m: paired_delta(pb, pa, m, args.bootstrap, args.seed)
           for m in ("cer_micro", "der", "ter", "wer_micro", "wser")}

    print(f"# Paired comparison — {rb['run_name']} vs {ra['run_name']}")
    print(f"\nn = {res['cer_micro']['n_paired_pages']} paired pages · "
          f"{args.bootstrap} bootstrap resamples\n")
    print("| metric | base % | adapted % | rel. change | 95% CI on rel. change |")
    print("|---|---|---|---|---|")
    for m, r in res.items():
        lo, hi = r["relative_delta_ci95"]
        print(f"| {m} | {_pct(r['base'])} | {_pct(r['adapted'])} | "
              f"{100 * r['relative_delta']:+.1f}% | "
              f"[{100 * lo:+.1f}%, {100 * hi:+.1f}%] |")

    c = res["cer_micro"]
    lo, hi = c["relative_delta_ci95"]
    print()
    if hi <= -0.20:
        print("**Target met.** The whole 95% interval clears a 20% relative "
              "CER reduction.")
    elif c["relative_delta"] <= -0.20:
        print(f"**Point estimate meets the target ({100 * c['relative_delta']:.1f}%) "
              f"but the interval reaches {100 * hi:+.1f}%.** Report the interval, "
              "not just the point estimate — on a small gold set this is the "
              "honest form of the claim.")
    else:
        print(f"**Target not met**: {100 * c['relative_delta']:+.1f}% "
              f"[{100 * lo:+.1f}%, {100 * hi:+.1f}%].")

    # --- where the reduction came from (proposal target 2) -----------------
    sh = reduction_shares(pb, pa, args.bootstrap, args.seed)
    label = {
        "tone_sub": "tone mark", "letter_sub": "letter diacritic",
        "diacritic": "**tone + letter diacritic**", "base_sub": "base letter",
        "base_ins": "insertion", "base_del": "deletion",
        "ws_errors": "whitespace", "runaway": "runaway pages (capped)",
    }
    print("\n## Where the reduction came from\n")
    print(f"Total character edits removed: {sh['total_reduction']} "
          f"(base − adapted, {sh['n_paired_pages']} paired pages)\n")
    print("| category | edits removed | share of reduction |")
    print("|---|---|---|")
    for k in ("diacritic", "tone_sub", "letter_sub", "base_sub", "base_ins",
              "base_del", "ws_errors", "runaway"):
        v = sh["share"][k]
        share = "n/a" if v != v else f"{100 * v:.1f}%"
        print(f"| {label[k]} | {sh['reduction'][k]} | {share} |")
    lo, hi = sh["diacritic_share_ci95"]
    print()
    if sh["total_reduction"] <= 0:
        print("Total edits did not fall, so shares are undefined.")
    else:
        print(f"Diacritic share 95% CI: [{_pct(lo)}%, {_pct(hi)}%]. "
              f"Diacritics removed more edits than every other category in "
              f"{100 * sh['p_diacritic_largest']:.1f}% of resamples.")
        big = max(("base_ins", "base_del", "ws_errors", "runaway"),
                  key=lambda k: sh["share"][k])
        if sh["share"][big] > sh["share"]["diacritic"]:
            print(f"\n**Most of the reduction is in `{big}`, not in diacritics.** "
                  "Check whether the adapted model is learning a formatting or "
                  "labelling convention (dropped headers or page numbers, removed "
                  "markup, modernised hyphenation) rather than reading better.")

    mb = sum(p.markup_chars for p in pb)
    ma = sum(p.markup_chars for p in pa)
    if mb or ma:
        print(f"\n**Markup in hypotheses: base {mb} chars, adapted {ma} chars.** "
              "Part of the difference may be formatting, not recognition.")

    if args.out:
        res["reduction_shares"] = sh
        res["markup_chars"] = {"base": mb, "adapted": ma}
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(res, fh, ensure_ascii=False, indent=2)


# --- verify ------------------------------------------------------------------


def cmd_verify(args):
    train = load_manifest(args.train)
    test = load_manifest(args.test)
    problems = []

    def books(rows):
        return {r.get("book_id") for r in rows if r.get("book_id")}

    tb, sb = books(train), books(test)
    if not tb or not sb:
        problems.append(
            "book_id missing from one or both manifests — split leakage cannot "
            "be checked. VieBookRead pages from one book share typeface, paper "
            "and scan conditions, so a page-level split leaks the test "
            "distribution into training and inflates the result."
        )
    overlap = tb & sb
    if overlap:
        problems.append(
            f"BOOK LEAKAGE: {len(overlap)} book(s) appear in both splits, e.g. "
            f"{sorted(overlap)[:5]}. Split by book, not by page."
        )

    tp = {r.get("page_id") for r in train}
    sp = {r.get("page_id") for r in test}
    if tp & sp:
        problems.append(f"PAGE LEAKAGE: {len(tp & sp)} page_id(s) in both splits.")
    if len(sp) != len(test):
        problems.append("duplicate page_id in the test manifest")

    nfc_bad = other_script = empty = 0
    for r in test:
        t = _text(r, "ref")
        if not t.strip():
            empty += 1
        if unicodedata.normalize("NFC", t) != t:
            nfc_bad += 1
        letters = [c for c in t if c.isalpha()]
        if letters:
            latin = sum(
                1 for c in letters if "LATIN" in unicodedata.name(c, "")
            )
            if latin / len(letters) < 0.9:
                other_script += 1

    print(f"train: {len(train)} pages / {len(tb)} books")
    print(f"test:  {len(test)} pages / {len(sb)} books")
    print(f"test refs not in NFC: {nfc_bad}")
    print(f"test refs mostly non-Latin script: {other_script}")
    print(f"test refs empty: {empty}")
    if other_script:
        print("  -> VieBookRead contains occasional non-Vietnamese pages. "
              "Filter them or make them their own stratum; do not let them sit "
              "unlabelled in the main test number.")
    if problems:
        print("\nPROBLEMS")
        for p in problems:
            print(f"  - {p}")
        sys.exit(1)
    print("\nOK — no leakage detected.")


# --- selftest ----------------------------------------------------------------


def cmd_selftest(args):
    from metrics import score_page as sp

    fails = []

    def check(name, got, want):
        if got != want:
            fails.append(f"{name}: got {got!r}, want {want!r}")

    # tone placement style must not cost anything
    check("tone style hoa", canonical("hòa bình"), canonical("hoà bình"))
    check("tone style thuy", canonical("thúy"), canonical("thuý"))
    check("tone style quy", canonical("qúy"), canonical("quý"))

    # NFC vs NFD input must be identical
    check("nfd input", canonical(unicodedata.normalize("NFD", "tiếng Việt")),
          canonical("tiếng Việt"))

    # whitespace collapsing
    check("ws collapse", canonical("a  \n b\t c"), "a b c")

    # a pure tone error is a DER hit, not a base-letter error
    p = sp("má", "mà", "t1")
    check("tone sub counted", (p.tone_sub, p.base_sub, p.letter_sub), (1, 0, 0))
    check("tone denominator", p.ref_tone_graphemes, 1)

    # a letter-diacritic error (a vs a-circumflex) is its own category
    p = sp("an", "ân", "t2")
    check("letter diac", (p.letter_sub, p.tone_sub, p.base_sub), (1, 0, 0))

    # d-with-stroke vs d is a letter-diacritic error, not a different letter
    p = sp("đi", "di", "t3")
    check("d stroke", (p.letter_sub, p.base_sub), (1, 0))

    # combined: e-circumflex-acute vs e-circumflex -> tone only
    p = sp("tiếng", "tiêng", "t4")
    check("tone on stacked", (p.tone_sub, p.base_sub, p.letter_sub), (1, 0, 0))

    # word-splitting is a whitespace error, not two base errors
    p = sp("Hà Nội", "HàNội", "t5")
    check("ws delete", (p.ws_errors, p.base_sub, p.base_del), (1, 0, 0))

    # runaway detection and capping
    p = sp("x" * 100, "y" * 500, "t6")
    check("runaway flagged", p.runaway, True)
    check("runaway capped at CER 1.0", round(p.cer, 6), 1.0)
    p = sp("x" * 100, "y" * 500, "t7", cap_runaway=False)
    check("uncapped runaway exceeds 1.0", p.cer > 1.0, True)

    # perfect match
    p = sp("Nguyễn Trãi viết Bình Ngô đại cáo", "Nguyễn Trãi viết Bình Ngô đại cáo", "t8")
    check("identity", (p.char_edits, p.cer), (0, 0.0))

    # empty hypothesis
    p = sp("một hai ba", "", "t9")
    check("empty hyp flagged", p.empty_hyp, True)
    check("empty hyp CER 1.0", round(p.cer, 6), 1.0)

    # markup audit counts, never strips
    p = sp("Chương một", "# Chương một", "t10")
    check("markup counted", p.markup_chars, 2)
    p = sp("a * b", "a * b", "t11")
    check("lone asterisk not markup", p.markup_chars, 0)

    # reduction shares: adapted fixes only tone errors -> diacritic share 1.0
    from metrics import reduction_shares
    base = [sp("má mà mả", "ma ma ma", f"s{i}") for i in range(20)]
    adap = [sp("má mà mả", "má mà mả", f"s{i}") for i in range(20)]
    r = reduction_shares(base, adap, n_boot=50)
    check("share tone-only fix", round(r["share"]["diacritic"], 6), 1.0)
    check("share tone-only largest", r["p_diacritic_largest"], 1.0)

    # adapted fixes only whitespace -> diacritic share 0
    base = [sp("Hà Nội đẹp", "HàNội đẹp", f"w{i}") for i in range(20)]
    adap = [sp("Hà Nội đẹp", "Hà Nội đẹp", f"w{i}") for i in range(20)]
    r = reduction_shares(base, adap, n_boot=50)
    check("share ws-only fix", round(r["share"]["ws_errors"], 6), 1.0)
    check("share ws-only diacritic", round(r["share"]["diacritic"], 6), 0.0)

    if fails:
        print("SELFTEST FAILED")
        for f in fails:
            print("  -", f)
        sys.exit(1)
    print("selftest OK — metric definitions behave as documented")


# --- argparse ----------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser(prog="viet-ocr-eval", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("score")
    s.add_argument("manifest")
    s.add_argument("--run-name", required=True)
    s.add_argument("--out")
    s.add_argument("--bootstrap", type=int, default=1000,
                   help="resamples for the CI; 0 to skip")
    s.add_argument("--seed", type=int, default=13)
    s.add_argument("--no-collapse-whitespace", dest="collapse_whitespace",
                   action="store_false", default=True)
    s.add_argument("--no-canonical-tone", dest="canonical_tone",
                   action="store_false", default=True)
    s.add_argument("--lowercase", action="store_true", default=False)
    s.add_argument("--no-cap-runaway", action="store_true", default=False)
    s.set_defaults(func=cmd_score)

    c = sub.add_parser("compare")
    c.add_argument("base")
    c.add_argument("adapted")
    c.add_argument("--bootstrap", type=int, default=1000)
    c.add_argument("--seed", type=int, default=13)
    c.add_argument("--out")
    c.set_defaults(func=cmd_compare)

    v = sub.add_parser("verify")
    v.add_argument("train")
    v.add_argument("test")
    v.set_defaults(func=cmd_verify)

    t = sub.add_parser("selftest")
    t.set_defaults(func=cmd_selftest)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
