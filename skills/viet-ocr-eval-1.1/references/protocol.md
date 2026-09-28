# The locked protocol

Read this before the first baseline run, and again before writing the results
chapter. Everything here is a decision that is cheap to make once and expensive
to change later, because changing it invalidates every number measured before it.

## Contents

1. What gets frozen, and when
2. Splitting the corpus
3. The gold subset
4. Decoding settings and seeds
5. What to report
6. The results table template
7. Failure modes that have cost other people their comparison

---

## 1. What gets frozen, and when

Freeze in this order. Each step depends on the one above it.

| # | Artefact | Freeze before | Recorded as |
|---|---|---|---|
| 1 | Test split (page ids + book ids) | any training run | `test.jsonl`, committed |
| 2 | Normalization settings | the first baseline | `protocol_version` + `normalization` in every report |
| 3 | Decoding settings | the first baseline | `decode.json`, committed |
| 4 | Gold subset ids | the first comparison | `gold.jsonl`, committed |

Once frozen, a change means re-running everything on both sides. Reports carry
`protocol_version` and `normalization`, and `compare` refuses to pair two runs
whose normalization differs. That refusal is the point: it makes the failure
loud instead of silent.

## 2. Splitting the corpus

**Split by book, not by page.** Pages from one book share typeface, paper stock,
ink, binding and scan session. A page-level split puts near-identical pages on
both sides and reports a number that will not survive contact with a new book.

Run `evaluate.py verify train.jsonl test.jsonl` after any repartition. It exits
non-zero on book or page overlap.

VieBookRead is mainly Vietnamese but contains occasional pages in other
languages. `verify` counts pages whose reference is mostly non-Latin. Either
exclude them or give them their own stratum — leaving them unlabelled in the
headline number means a reader cannot tell whether a difference came from
adaptation or from a handful of foreign-script pages.

## 3. The gold subset

VieBookRead's page-level labels are distantly supervised: they were produced by
aligning scanned pages against reference ebook text with LLM assistance, not
transcribed by annotators. CHURRO excluded the dataset from its training
collection for exactly this reason.

This is survivable, and the way to survive it is to say so first and measure
around it:

- Sample **200–300 pages** from the locked test set, stratified by book and by
  degradation level, and verify them by hand. Verification is fast: you are
  correcting an already-close transcript, not typing from scratch. The review
  UI is the natural place to do it, which also dogfoods the product.
- Report every headline number **twice**: on the full locked test set
  (pseudo-GT, large n, narrow interval, some label noise) and on the gold
  subset (clean labels, small n, wide interval).
- The claim you defend is the **agreement between the two**, not either alone.
  If both show the same direction and roughly the same magnitude, label noise
  is not driving the result and you can say so with evidence.

Record who verified each gold page and when. If a second person verifies an
overlapping slice, report inter-annotator agreement on it — a few dozen pages
is enough and it answers the obvious question before it is asked.

Never let an LLM produce or edit gold-subset text. Evaluating an LLM-based
recogniser against LLM-authored ground truth is a circular argument, and it is
the first thing a reviewer will look for.

## 4. Decoding settings and seeds

Fix and commit:

```json
{"temperature": 0.0, "top_p": 1.0, "do_sample": false, "seed": 13,
 "max_new_tokens": 2048, "repetition_penalty": 1.0}
```

`max_new_tokens` needs a real ceiling. Without one, a repetition loop runs until
the context limit and produces a page-level CER in the tens.

**Run the baseline at three seeds before trusting it.** A published LoRA
fine-tune of this model family reported baseline CER of 19.74 on one run and
62.22 on another over the same eval set, while the fine-tuned model sat at 3.23
on both. The instability was in the base model's decoding, not in the data. If
your baseline moves like that, a "20% relative reduction" is unfalsifiable, and
fixing it is a prerequisite, not an optimisation.

Acceptance gate: across three seeds, the standard deviation of micro-CER should
be under 10% of its mean. If it is not, look at the runaway rate first.

## 5. What to report

Always, in this order:

1. **Micro CER** — total edits over total reference characters. Primary.
2. **Macro CER ± sd, and median page CER** — a large macro/micro gap means a few
   pages are carrying the average. `score` prints a warning when the gap exceeds
   5 points.
3. **WER (syllable-delimited)** — say what it measures. Whitespace separates
   syllables in Vietnamese, not words, so this is a syllable error rate. Report
   it for comparability with the literature and name it honestly in the text.
4. **DER and TER** — the thesis contribution. DER over all diacritic-bearing
   graphemes; TER over tone-bearing graphemes only.
5. **WSER** — whitespace errors over reference spaces.
6. **Run health** — runaway rate, empty-output rate. Never omit these. A model
   that gets a better CER by emitting less text is not better.
7. **Stratified table** — by degradation level at minimum.

Every rate needs its denominator printed next to it. `score` does this
automatically; keep it that way in the thesis tables. "DER 4.1%" means nothing
without knowing whether the denominator was all characters or only
diacritic-bearing ones.

## 6. The results table template

For the comparison chapter, the load-bearing table is the paired one:

| metric | base | adapted | rel. change | 95% CI on rel. change |
|---|---|---|---|---|
| CER (micro) | | | | |
| DER | | | | |
| TER | | | | |
| WER (syllable) | | | | |
| WSER | | | | |

produced by `evaluate.py compare`. The confidence interval is on the
**difference**, computed by resampling the paired pages — not two separate
intervals left for the reader to eyeball for overlap. Pairing also removes page
difficulty as a source of variance, which matters a lot on 250 gold pages.

State the claim in the form the interval supports:

- interval entirely below −20%: the target is met, say so plainly;
- point estimate below −20% but the interval crosses it: report the interval and
  say the point estimate meets the target while the evidence at this sample size
  does not settle it. This is the honest form and it is not a weak result.

## 7. Failure modes that have cost other people their comparison

**LoRA merge artefacts.** In the same published fine-tune referenced above, a
LoRA-to-safetensors merge silently dropped modules and made the merged model's
CER meaningless; only the runtime-adapter path gave usable numbers. Before the
full evaluation run, score a 20-page smoke set with the adapter applied at
runtime and with the merged checkpoint, and confirm the two agree to within a
rounding error. If they disagree, the merge is broken — not the model.

**Training format not matching inference format.** PaddleOCR-VL is two-stage:
layout analysis, then VLM recognition over the detected regions. If training
feeds full pages while inference feeds region crops, the distributions differ
and the result cannot be attributed to adaptation. Verify this before spending
GPU hours.

**Layout errors masquerading as recognition errors.** LoRA touches the
recogniser, not the layout stage. If a region is missed, its text is absent and
shows up as deletions in CER, swamping whatever the adapter did. Score twice:
once end-to-end from the page, and once with regions held fixed (same crops for
both models). The second isolates what the adaptation actually changed; the
first is what a user experiences. Report both and the gap between them is itself
a finding.

**Silent normalization drift.** Someone re-runs eval months later with
`--lowercase` or without `--canonical-tone` and the number moves by a point.
Every report records its settings and `compare` refuses mismatched pairs — do
not work around that refusal.
