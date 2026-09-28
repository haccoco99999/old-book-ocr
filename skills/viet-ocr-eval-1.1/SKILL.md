---
name: viet-ocr-eval
description: >
  The locked evaluation protocol for Vietnamese OCR — character, syllable,
  diacritic, tone and whitespace error rates with paired bootstrap confidence
  intervals, plus normalization, split-leakage checks and run-health reporting.
  Use this skill whenever the task involves measuring, comparing, reporting or
  debugging Vietnamese OCR or HTR quality: computing CER, WER, DER or TER,
  comparing a fine-tuned model against a base model, scoring PaddleOCR-VL,
  Tesseract, TrOCR or any other recogniser on VieBookRead or similar corpora,
  building or checking a train/test split, writing up OCR results, or
  investigating why an error rate moved between runs. Use it even when the
  request sounds like a small one-off ("just compute CER on these files",
  "how did the adapted model do") — the whole point is that every number in
  the project comes out of the same definitions, and a single ad-hoc
  calculation is what breaks that.
---

# viet-ocr-eval

## Why this exists

An OCR thesis lives or dies on one comparison: base model versus adapted model,
same test set, same metric. That comparison is fragile in a way that is easy to
miss, because nothing ever errors out. Someone normalizes NFC in July and NFD in
September. Someone collapses line breaks in one run and not the other. Someone
reports DER over all characters on Tuesday and over diacritic-bearing characters
on Friday. Each number looks reasonable on its own. Together they do not measure
the same thing, and by the time that surfaces the GPU hours are spent.

This skill is one set of definitions, in code, with a self-test. Use it for
every number that will appear in the thesis.

It also encodes three things ordinary CER tooling gets wrong for Vietnamese:
tone marks and letter diacritics are separate error categories, tone placement
style is not an error, and a repetition loop is a decoding failure rather than
ten thousand recognition errors.

## Before anything else

```bash
python3 scripts/evaluate.py selftest
```

Assertions covering the behaviour documented below. Run it after any
edit to `normalize.py` or `metrics.py`, and once at the start of a session that
will produce reported numbers. If it fails, stop — the definitions have drifted
and everything measured since the last passing run is suspect.

## Workflow

### 1. Check the split before scoring anything

```bash
python3 scripts/evaluate.py verify train.jsonl test.jsonl
```

Exits non-zero on book-level or page-level leakage, and audits the test
references for non-NFC text, non-Latin-script pages and empty entries. Run it
after every repartition. Pages from one book share typeface, paper and scan
session, so a page-level split quietly leaks the test distribution into
training — this is the check that catches it.

### 2. Score each run

Build a JSONL manifest, one object per page:

```json
{"page_id": "bk012_p041", "book_id": "bk012",
 "ref": "Nước Việt Nam ta có một nền văn hiến lâu đời.",
 "hyp": "Nuoc Việt Nam ta có một nên văn hiên lâu đời.",
 "strata": {"degradation": "high", "decade": "1890"}}
```

`ref_path` and `hyp_path` work instead of inline text for long pages.

```bash
python3 scripts/evaluate.py score test_base.jsonl    --run-name base
python3 scripts/evaluate.py score test_adapted.jsonl --run-name adapted
```

Each writes `report_<name>.json` (per-page detail, for error analysis) and
`report_<name>.md` (the table, ready to paste).

### 3. Compare

```bash
python3 scripts/evaluate.py compare report_base.json report_adapted.json
```

This is the number the thesis claim rests on. It pairs the two runs page by
page, bootstraps the **relative change** and reports a confidence interval on
the difference — not two separate intervals left for a reader to eyeball for
overlap. Pairing removes page difficulty as a source of variance, which matters
on a small gold set.

`compare` refuses to pair runs scored with different normalization settings.
Do not work around that; re-score both instead.

Since protocol 1.1, `compare` also reports TER and a **"where the reduction came
from"** table: the absolute reduction in character edits split by category, with
the tone + letter-diacritic share, its bootstrap CI, and the fraction of
resamples in which diacritics removed more edits than any other category. That
is the measurement for a claim of the form "most of the improvement is in
diacritics". If insertions, whitespace or runaway pages account for more of the
reduction than diacritics, it says so — usually a sign the adapted model learned
a labelling or formatting convention rather than reading better.

## The metrics

| metric | numerator | denominator |
|---|---|---|
| **CER** | character edits | reference characters |
| **WER** | syllable edits | reference syllables |
| **DER** | tone + letter-diacritic substitutions | reference graphemes bearing any diacritic |
| **TER** | tone substitutions only | reference graphemes bearing a tone mark |
| **WSER** | space ins/del/sub | reference spaces |

Always print the denominator next to the rate. "DER 4.1%" is unreadable without
knowing whether the denominator was all characters or only diacritic-bearing
ones — and both conventions exist in the literature.

**Micro is primary** (total edits over total characters). Macro (mean of
per-page rates) is reported alongside, with its standard deviation and the
median page. A large micro/macro gap means a handful of pages is carrying the
average, and `score` prints a warning when the gap exceeds five points.

### Error categories

Substitutions are decomposed, which is the point of the whole exercise:

- **base letter** — `n` read as `u`
- **tone mark** — `má` read as `mà`, `tiếng` read as `tiềng`
- **letter diacritic** — `an` read as `ân`, `đi` read as `di`
- **whitespace** — `Hà Nội` read as `HàNội`
- insertions, deletions

`ma / má / mà` mean *ghost / mother / but*. A model losing tone marks on faded
pages is failing differently from one confusing letterforms, and an aggregate
CER cannot tell those apart. This decomposition is what lets the thesis
attribute an improvement to the parts of the script that carry meaning.

### Run health, and why it is not optional

Every report includes the runaway rate and the empty-output rate.

A compact document VLM on an out-of-domain dense page can fall into a repetition
loop and emit text until it hits the token ceiling. Scored naively that page
gets a CER of 20 or 40, and a few such pages will swing a macro average by tens
of points — which looks exactly like an unstable baseline. The scorer flags
those pages, caps them at CER 1.0, keeps them out of the error breakdown (a
decoding failure is not a base-letter error), and reports the rate separately.

Report the health numbers next to the accuracy numbers. A model that improves
CER by emitting less text has not improved.

Health also includes a **markup audit**: characters of heading markers, paired
`**`/`__`, HTML tags and LaTeX delimiters found in the raw hypothesis. Nothing
is stripped — the scorer never alters a hypothesis — but a non-zero count means
formatting is being scored as recognition error. Convert model output to plain
text upstream and re-score. `compare` prints the markup counts of both runs,
because a base model that emits Markdown against an adapted model trained on
plain-text targets produces an apparent gain that is purely formatting. `__`
can occasionally be a genuine blank line in old print; inspect before acting.

## Normalization

`canonical()` is applied identically to reference and hypothesis. Defaults:

- NFC, then a conservative character fold (quote and dash variants, zero-width
  characters, exotic spaces)
- **tone-position canonicalisation** — `hòa` and `hoà` are both correct
  Vietnamese and must not cost error rate
- **whitespace collapsed** — ebook line breaks never match scanned-page line
  breaks; leaving them in means layout noise dominates CER. Word joining and
  splitting survive collapsing, so the whitespace behaviour that matters is
  preserved
- case preserved

This is a **scoring** form, not an orthographic recommendation. Never apply it
to exported text or to text shown to a proofreader.

The flags `--no-canonical-tone`, `--no-collapse-whitespace` and `--lowercase`
exist for ablations. Results from different settings are not comparable, and
`compare` enforces that.

## Reading a result

Work down in this order. Stop at the first thing that looks wrong — later
numbers are not meaningful until it is resolved.

1. **Runaway and empty rates.** Above a couple of percent, fix decoding before
   reading anything else.
2. **Micro vs macro CER.** A large gap means outliers, not a population.
3. **Micro CER**, with its interval.
4. **The breakdown.** If tone and letter-diacritic errors together are a small
   share, the model's problem is not diacritics and the thesis framing needs
   adjusting to match what the data says.
5. **Stratified table.** If the improvement sits entirely in one degradation
   stratum or one book, say so — that is a finding, not a flaw.
6. **The paired comparison**, last.

## Reference material

- `references/protocol.md` — what to freeze and when, book-level splitting, the
  gold-subset procedure for distantly supervised labels, decoding settings and
  seed policy, the results table template, and the failure modes that have cost
  other people their comparison (LoRA merge artefacts, train/inference format
  mismatch, layout errors masquerading as recognition errors). Read before the
  first baseline run and again before writing results.
- `references/vietnamese-orthography.md` — the two categories of diacritic, why
  `đ` needs special handling, why tone placement is not an error, syllable vs
  word boundaries, legacy encodings. Read when a normalization decision needs
  justifying in the thesis or before changing `normalize.py`.

## Two things worth knowing up front

**If the corpus uses distantly supervised labels** — VieBookRead's page text was
produced by aligning scans against reference ebooks with LLM assistance, not by
annotators — then CER measured against it includes label noise. Carve out a
200–300 page hand-verified gold subset, report every headline number on both,
and defend the agreement between them rather than either alone. Never let an
LLM author or edit gold text: evaluating an LLM-based recogniser against
LLM-authored ground truth is circular, and it is the first thing a reviewer
checks. `references/protocol.md` §3 has the procedure.

**Run the baseline at three seeds before trusting it.** A published LoRA
fine-tune of this model family reported baseline CER of 19.74 on one run and
62.22 on another over the same eval set, while the fine-tuned model sat at 3.23
on both — instability in the base model's decoding, not in the data. A relative
reduction claim measured against a baseline that moves like that is
unfalsifiable. Gate: standard deviation under 10% of the mean across three
seeds.
