# Decision record: declared models, primary endpoint, serving plan

Written 2026-09-25. The YAML block below is machine-read by `promote.py`, `register_base.py`,
`serve.sh` and `evaluate_test.py`. `evaluate_test.py` freezes this file: the first line it writes to
`test_access.log` records this file's git blob sha, and every later access refuses to run if the
committed file differs from that version.

## This registration is post hoc

The test set was accessed before this file existed:

| # | when (UTC) | version | view | sets | evidence |
|---|---|---|---|---|---|
| 1 | 2026-09-17 21:03 → 09-19 20:02 | base | fixed-crop | test + gold | `training/finals/ledger.jsonl`, `finals/test__base_7dea718d/` |
| 2 | 2026-09-18 11:08 → 09-19 17:06 | final | fixed-crop | test + gold | `training/finals/ledger.jsonl`, `finals/test__…_exp_lr2e4/` |
| 3 | 2026-09-24 06:11 → 10:56 (scored 11:13) | base | end-to-end | test | `backend/reports/eval/d4/state.json` (run tag 606c4796) |
| 4 | 2026-09-24 11:14 → 18:43 | final | end-to-end | test | same |

Under the 25/09 access definition (one access covers both views and both sets), base and final each
have **two** accesses. Their results were known when this file was written:

| comparison | Δ CER (micro, relative) | 95% CI |
|---|---|---|
| test, fixed-crop | −47.3% | [−52.4, −42.0] |
| test, end-to-end | −49.4% | [−53.1, −45.5] |
| gold, fixed-crop | −52.7% | [−68.6, −38.0] |

Two choices that could have been bent toward the result have no room to move:
- **Aggregation.** `viet-ocr-eval compare` pairs only `cer_micro`, so micro is the only aggregation
  with a paired interval.
- **Decision rule.** In every row, both the point estimate and the whole interval clear −20%. Either
  rule gives "met".

Target 2 (the reduction is mostly in diacritics) was also settled after its results were known
(`training/work/analysis/protocol_1.1`). The reading chosen is **largest**, judged on test with the
same strictness as target 1: met only if diacritics are the largest category in at least 95% of
resamples. Test: 100% of resamples, share 83.2% [76.5, 92.2], so met. Gold is reported beside it and
does **not** meet that rule: 93.3% of resamples, share 55.3% [37.5, 76.1]. One page causes this,
`003/page_25`, where the base model loops "(or)" to the 1,024-token cap. The rule that drops pages
over 2x the reference (gold 100%) was set post hoc and is only a sensitivity analysis.

The model choice itself was made on dev before access 1. `exp_lr2e4` had the lowest dev CER micro
(1.62%, 150 dev pages / 1,323 regions) of the runs finished at that time: base LoRA, `exp_lm_only`,
`exp_lr2e4` and `exp_r32`. The four runs of the final week were dev-only and changed nothing.

## Markup rule (decided 2026-09-25, post hoc)

`evaluate_test.py` aborts an access whose report has more markup characters (viet-ocr-eval 1.1
`health.markup_chars`) than allowed below. For the final model, any markup aborts: it was trained
on plain text, so markup reaching the scorer would mean the plain-text path is broken.

The untrained base model gets no abort. It writes some dot-below letters as LaTeX, for example
`nh\(\underset{\cdot}{i}\)t`, and emits `___` blank lines. Its test reports already held 143
markup characters on 33 pages (fixed-crop) and 149 on 32 pages (end-to-end), under 0.1% of its
character errors. The adapted model emits none. Markup can change base's error count by at most
that many edits, so it cannot carry the result. Base's markup count is reported next to its results.

## Serving plan: H, the Paddle engine for everything (decided 2026-09-25)

vLLM is not used. The LoRA adapter is never merged (decision D1, 2026-09-23). Every number comes
from one engine, `training/ocrtrain/infer.Engine`, with the adapter applied at runtime:
- **fixed-crop view:** the training harness (`evaluate_final.py generate`), base and adapted;
- **end-to-end view:** the backend with its native-Paddle recognition server
  (`backend/recognizer_server/recognition_server.py`, which wraps the same Engine), base and adapted.

Why not vLLM: the adapter is in Paddle format, and PaddleOCR-VL merges have a documented failure
history (ERNIE issue #1405). The runtime adapter is verified tensor by tensor on every load. Served
outputs are byte-identical to the harness: 12/12 test crops and 1,323/1,323 dev regions. A
Paddle↔vLLM noise floor would therefore only measure a second engine that nothing reports from.

Consequences:
- There is no merge, so the weight-level merge check (addendum B.3a) and the converter check (4a) do
  not apply. `promote.py` instead checks the adapter file against the base weights and against what
  training recorded, then checks the served load report (see `parity` below).
- Calibration (addendum B, "calibrate first") does not apply. Both views run the same engine, so the
  fixed-crop test numbers are directly comparable with dev.
- `bench.py` reports the engine it used (Paddle recognition server, batch-1 generation).

## Machine-readable block

```yaml
decision:
  written_at: "2026-09-25"
  registration: post_hoc
  serving_plan: H
  engine: training/ocrtrain/infer.Engine (Paddle, runtime LoRA adapter)
  vllm: not_used

declared_versions:
  - name: paddleocr-vl-1.6-base
    role: baseline
    model_spec: base
    config: training/configs/base.yaml
    adapter_sha256: null
    serve: true
    test: true
    dev_reference_outputs: training/baselines/20260915-190721_se15963_073700d7_base/regions_seed13.jsonl
  - name: paddleocr-vl-1.6-vbr-lr2e4-s3000
    role: final
    model_spec: run
    run_dir: training/runs/20260917-154010_s2ea991_c57c0a6c_exp_lr2e4
    best_step: 3000
    adapter_sha256: e5d33196062527499e613a84396a0d7c3be1bce72f91466f6b7334466edf91bf
    serve: true
    test: true
    dev_reference_outputs: training/work/20260917-154010_s2ea991_c57c0a6c_exp_lr2e4/eval/step-003000/regions.jsonl
  - name: paddleocr-vl-1.6-vbr-lr2e4-seed14-s3000
    role: seed_replicate
    model_spec: run
    run_dir: training/runs/20260923-121505_s9f712b_6ecef906_exp_lr2e4_seed14
    best_step: 3000
    adapter_sha256: d58fdc2be71b83459a3480a2503bc2091b9b37b45e9f79661f3ef001df2e1b76
    serve: false          # dev only: reported descriptively on dev, never served, never run on test
    test: false

primary_endpoint:
  comparison: {baseline: paddleocr-vl-1.6-base, treatment: paddleocr-vl-1.6-vbr-lr2e4-s3000}
  seed_replicate: descriptive, dev only
  view: fixed-crop
  set: test
  metric: cer_micro
  aggregation: micro
  statistic: viet-ocr-eval compare, relative_delta and relative_delta_ci95 (paired page bootstrap, 1000 resamples, seed 13)
  threshold: -0.20
  threshold_source: thesis proposal, target 1 (at least a 20% relative CER reduction)
  decision_rule: met if and only if the upper bound of relative_delta_ci95 is <= -0.20
  registered: post_hoc

secondary_endpoints:
  - {view: end-to-end, set: test, metric: cer_micro, rule: same as primary}
  - {view: fixed-crop, set: gold, metric: cer_micro, rule: same as primary}
  - {view: both, set: test and gold, metrics: [der, ter, wer_micro, wser], report: relative_delta with CI}
  - name: target_2_diacritic_share
    source: viet-ocr-eval 1.1 compare, reduction_shares (share.diacritic with CI, p_diacritic_largest)
    reading: largest      # tone + letter diacritics remove more edits than every other error category
    set: test
    decision_rule: met if and only if p_diacritic_largest >= 0.95 (diacritics largest in at least 95% of 1000 paired page resamples, seed 13)
    also_reported: [diacritic share with its 95% CI, the majority reading (share > 50%), gold, the post-hoc len2x sensitivity sets]
    registered: post_hoc  # chosen 2026-09-25 by the author, after the protocol 1.1 results were known

gold:
  source: training/data/books-all/gold.jsonl (sha256 afa9a84a1bfe697dd0c9a43f427476607271fec650a1961914b26914507b9b44)
  size: 250 test pages, 23 books
  sampling: ocrdata.split.sample_gold, equal quota per test book, round-robin over the Azure-confidence difficulty tertiles, seeded
  verified_file: training/data/books-all/gold_verified.jsonl (sha256 b33afd0338619260a180fd6823bcc8bb04297e4aca1111bf02f8590782b613aa)
  verified_by: one annotator, the author (verified_by recorded per page); 2026-09-15 14:21Z to 2026-09-16 09:32Z; no second annotator (agreement pairs = 0)
  guideline: training/gold_review.py; the annotator corrects the pseudo label region by region to match the crop; text is typed by a person from the image, never produced or edited by an LLM (protocol.md section 3); the page reference is the verified region texts joined by newline in stored reading order
  selection_rule: earliest verification per page
  references_note: VieBookRead test references are LLM-corrected pseudo ground truth; gold is human-verified

parity:
  # promote.py / register_base.py, before a model_versions row is inserted or confirmed
  pages: 20                     # fixed: seeded sample (seed 13) of the 150-page dev evaluation subset
  reference: the harness's stored dev outputs for that version (dev_reference_outputs)
  served: the recognition server under the version's name, same crops, prompt "OCR:", decode.json
  threshold_relative_cer: 0.01  # abort unless |relative CER difference| < 1%
  expected: 0 pages changed (same engine; batch-1 greedy decoding)
  repeatability: not_applicable  # generation is batch 1, so batch composition cannot vary

calibration:
  noise_floor: not_applicable   # one engine (plan H); nothing to calibrate against

test_evaluation:
  markup_chars_limit:              # the largest health.markup_chars a report may have before the access aborts
    default: 0                     # any markup reaching the scorer aborts
    paddleocr-vl-1.6-base: null    # no abort: the base model's own LaTeX and underscores, reported with its results
  registered: post_hoc

fallback:
  plan: H is the plan of record, not a fallback
  thresholds: never changed after a failure is seen

test_accesses_before_this_file:
  - {version: paddleocr-vl-1.6-base, view: fixed-crop, sets: [test, gold], started: "2026-09-17T21:03:05Z", ended: "2026-09-19T20:02:29Z", evidence: training/finals/ledger.jsonl}
  - {version: paddleocr-vl-1.6-vbr-lr2e4-s3000, view: fixed-crop, sets: [test, gold], started: "2026-09-18T11:08:06Z", ended: "2026-09-19T17:06:15Z", evidence: training/finals/ledger.jsonl}
  - {version: paddleocr-vl-1.6-base, view: end-to-end, sets: [test], started: "2026-09-24T06:11:16Z", ended: "2026-09-24T11:13:51Z", evidence: backend/reports/eval/d4/state.json}
  - {version: paddleocr-vl-1.6-vbr-lr2e4-s3000, view: end-to-end, sets: [test], started: "2026-09-24T11:13:51Z", ended: "2026-09-24T18:43:16Z", evidence: backend/reports/eval/d4/state.json}
```
