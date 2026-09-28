# Prompt — build the training and fine-tuning source

> Paste everything below the line into Claude Code at the repo root.
> Edit the bracketed values first. This produces the run directories that
> `promote.py` (MLOps layer) consumes, so build it before or alongside that.

---

You are building the training source for a Vietnamese historical-book OCR
capstone. Hard deadline **[30 September 2026]**; training must be finished by
**[21 September]** to leave time for evaluation and writing. One machine, one
**24 GB GPU**. Prioritise a harness that runs a small sweep reliably over one
that supports every possible experiment.

## Context

- **Model**: PaddleOCR-VL-1.6, a 0.9B document VLM. Two stages — PP-DocLayoutV3
  for layout, then the VLM transcribes each detected region. **LoRA adapts only
  the VLM stage.**
- **Tooling**: ERNIEKit (`PaddlePaddle/ERNIE`) with `fine_tuning: LoRA`.
- **Corpus**: VieBookRead at `[/data/viebookread]`, 26.7 GB, CC-BY-NC-4.0.
  Contents: `page_input` (scanned page images), `final` (pseudo ground truth,
  page level), `json_raw` (**Azure Document Intelligence OCR output, including
  line- and word-level bounding polygons**), `epub` (ebook sources),
  `unlabelled` (raw PDFs).
- **Metrics**: a skill at `[./skills/viet-ocr-eval]` owns every metric
  definition. CLI: `evaluate.py selftest | verify | score | compare`.

## Hard constraints

1. **Train on region crops, not full pages.** Inference runs the VLM on layout
   regions; training must match that distribution or the result cannot be
   attributed to adaptation. Region crops also cut visual-token count by an
   order of magnitude (the vision encoder is dynamic-resolution, so a dense
   page costs thousands of tokens), give roughly 20–40× more training samples
   per page, and shorten targets enough to reduce repetition-loop behaviour.

2. **Use the Azure boxes in `json_raw`. Do not run your own layout detection
   for data preparation.** Azure Document Intelligence output already contains
   line-level polygons for every page. Running PP-DocLayoutV3 or Tesseract to
   recover boxes would be slower, less accurate, and would occupy the GPU that
   training needs.

3. **Never compute a metric yourself.** Every CER, WER, DER or confidence
   interval — including mid-training dev evaluation — comes from calling the
   `viet-ocr-eval` CLI as a subprocess. No edit-distance function anywhere in
   this codebase. One definition produces every number in the project, and a
   second implementation destroys that invisibly.

4. **Split by book, not by page.** Pages from one book share typeface, paper
   and scan session. Enforce with `viet-ocr-eval verify`; it must pass before
   any training starts.

5. **Filter the training set only. Never filter dev or test.**

6. **Decode settings are frozen and identical everywhere**: greedy,
   `temperature=0`, `do_sample=false`, `top_p=1.0`, explicit `max_new_tokens`,
   fixed seed. Committed as `decode.json` and referenced, never inlined.

## A. Data preparation

Build `prepare_data.py` producing region-level training pairs.

1. Parse `json_raw` → per page, the Azure line polygons and their text, in
   reading order.
2. Concatenate Azure line text per page → an anchor string.
3. **Semi-globally** align the anchor against the page's pseudo ground truth
   from `final` — gaps at the start and end are unpenalised, and any region is
   allowed to map to **empty**. The anchor provides positions, the ground truth
   provides the labels.
4. Project ground-truth spans back onto each line box. A region that mapped to
   empty gets **no label** and is dropped from training — never assign it a
   nearby span.
5. Crop `page_input` images by box (with a small configurable margin) → emit
   `(crop_path, text)` pairs.

**Why semi-global matters.** The ground truth comes from ebook text, not from a
faithful transcription of the printed page. Page numbers, running heads,
footers, footnotes and figure captions usually do not exist in it at all. Full
global alignment forces every character on both sides to match, so a running
head with no counterpart will not be left empty — it will absorb a span of body
text from the neighbouring region. You then train the model to read a header
while the label says something else.

The length-ratio filter below does **not** catch this: a short header absorbing
a short sentence stays well inside the bounds. The alignment has to allow empty
on its own, or the error passes through silently. Report the empty-mapped rate,
broken down by region type (header, footer, page number, caption).

**Reading order must be fixed and identical everywhere.** The order in which
regions are concatenated during data preparation must be the same order used at
evaluation time when region outputs are reassembled into a page. If the two
differ, alignment still runs and nothing errors — it is just systematically
wrong. Define the ordering once, in one function, and use it from both paths.

Group adjacent lines into blocks if the region size that inference actually
produces is larger than a single line — match whatever PP-DocLayoutV3 emits.
Make the grouping granularity a config option and record which was used.

**Filtering**, applied to training data only:

- drop regions that mapped to empty (see above)
- drop regions where the anchor/ground-truth length ratio falls outside
  `[0.5, 2.0]`
- drop regions whose anchor alignment cost exceeds a threshold
- drop non-Vietnamese pages

On that last point: the corpus is labelled Vietnamese, **French and English**,
and the books run from about **1850 to 2003**, so colonial-era French pages are
present. A Latin-script check will not catch French. Detect Vietnamese by the
density of characters that exist in Vietnamese and not in French: **horn
(U+031B, `ơ ư`), breve (U+0306, `ă`), `đ` (U+0111), hook above (U+0309) and dot
below (U+0323)**. Make the threshold a config value and report what it removed.

Keep the filter loose — reject only disasters. A tight filter removes exactly
the most degraded regions, which biases training toward easy material.
**Report the rejection rate broken down by publication era and by degradation
stratum**, and write it to `data_manifest.json`. That number goes in the thesis
limitations section.

**Stratification**: tag every page with its publication era from the book
metadata. Era is the primary stratification axis — it is objective, already
available, and it also captures orthographic drift (syllable hyphenation such
as `Việt-Nam` is common before 1960 and rare after 1975). Add an
image-statistics degradation tertile as a secondary axis.

Emit `train.jsonl`, `dev.jsonl`, `test.jsonl`, `gold.jsonl` in the manifest
format `viet-ocr-eval` expects, each carrying `page_id`, `book_id` and
`strata`.

## B. Run directory contract

Every run writes exactly this layout. `promote.py` depends on it.

```
runs/<run_id>/
├── resolved_config.yaml      fully merged config, no inheritance left
├── run.json                  run_id, git sha, config hash, seeds, split
│                             hashes, env capture, GPU model, start/end
├── data_manifest.json        split hashes, region counts, filter stats
├── train_metrics.jsonl       one line per logged step
├── checkpoints/
│   ├── step-000800/          adapter weights only
│   ├── step-001600/
│   └── last/                 adapter + optimizer + scheduler + RNG state
├── best/                     best by dev CER
│   ├── lora_config.json
│   ├── lora_model_state.*
│   └── SHA256SUMS
└── eval/
    └── dev_step-NNNNNN.json  viet-ocr-eval reports
```

`run_id` = `{date}_{git_sha7}_{config_hash8}_{short_name}`. Deterministic,
sortable, and it tells you at a glance whether two runs shared a config.

**Checkpoint policy**: save every N steps; keep the best K by dev CER plus
`last/`. Strip optimizer state from everything except `last/` — it is several
times the size of the adapter and is only needed to resume. With a 26.7 GB
corpus and a sweep, disk fills faster than expected. Checkpoints are immutable:
hash on write, never overwrite.

## C. Configuration

Layered YAML: `configs/base.yaml` plus per-experiment override files. At
startup, merge, resolve, hash, and write `resolved_config.yaml` into the run
directory. Everything downstream reads the resolved file, never the source.

Must be configurable and must be recorded: LoRA rank, alpha, dropout, target
modules, learning rate, schedule, warmup, epochs, per-device batch size,
gradient accumulation, `max_pixels` / resize policy, prompt template, region
grouping granularity, seed, precision, gradient checkpointing.

Two settings deserve attention because they are how you fit on 24 GB:
`max_pixels` (the dominant driver of memory — visual token count scales with
it) and gradient accumulation (keep per-device batch small, accumulate to a
real effective batch).

**Target modules**: a published LoRA fine-tune of this model family found that
the visual head was excluded by the default paddleformers module regex, so
those modules were never adapted and later failed to load. Make the target
module list explicit in config, log the resolved list of matched modules at
startup, and **fail loudly if the count is zero or differs from the previous
run with the same config**.

## D. Training harness

`train.py --config configs/exp_r32.yaml`

- Wraps ERNIEKit. Do not reimplement the training loop.
- Dev evaluation every N steps: generate with the frozen decode settings, write
  a manifest, call `viet-ocr-eval score`, store the report under `eval/`, log
  CER / DER / **runaway rate** / **empty rate** to `train_metrics.jsonl`.
- Track runaway and empty rate as first-class training signals, not
  afterthoughts. A model improving CER while emitting less text is not
  improving, and a rising runaway rate during training is an early warning.
- Resume cleanly from `last/`, restoring optimizer, scheduler and RNG state.
- Fail fast: validate config, check disk space and VRAM headroom, and confirm
  the split passes `verify` before the first step.

`sweep.py` runs a list of configs sequentially (never in parallel — one GPU)
and writes a leaderboard sorted by dev CER, with each row linking to its run
directory.

## E. Baseline protocol

Before any adapted model is evaluated, `baseline.py` evaluates the **unadapted**
model on dev at **three seeds** and reports mean and standard deviation.

**Gate: standard deviation of micro-CER under 10% of its mean.** If it fails,
stop and investigate decoding before training further. A published fine-tune of
this model family recorded baseline CER of 19.74 on one run and 62.22 on
another over the same evaluation set while the adapted model sat at 3.23 on
both — the instability was repetition-loop behaviour in the base model, not the
data. A relative-reduction claim measured against a baseline that moves like
that is unfalsifiable, and fixing it is a prerequisite rather than an
optimisation.

Check the runaway rate first when this gate fails.

## Build order

Stop at each gate.

1. `prepare_data.py` steps 1–5 on **one book**.
   *Gate: show me 10 body-text crops with their aligned text, **plus every
   header, footer and page-number region found on those pages** — those must
   have mapped to empty rather than picked up body text. Do not process the
   corpus until I confirm.*
2. Filtering, Vietnamese detection, era tagging, split generation.
   *Gate: `viet-ocr-eval verify train.jsonl test.jsonl` passes; filter
   rejection rates reported by era.*
3. Run directory contract, config layering, checkpointing, resume.
   *Gate: kill a run mid-training and resume; loss curve continues smoothly.*
4. `baseline.py` at three seeds.
   *Gate: the stability gate passes.*
5. `train.py` end to end with dev evaluation through `viet-ocr-eval`.
6. `sweep.py` and the leaderboard.

## Acceptance criteria

- No edit-distance or error-rate implementation exists in this codebase; assert
  it with a source grep test
- Every run directory matches the contract exactly and is complete enough that
  `promote.py` needs no other input
- Re-running the same config with the same seed produces the same
  `config_hash` and a dev CER within noise
- Resume from `last/` is bit-identical in optimizer and RNG state
- The resolved list of matched LoRA target modules is logged at startup
- Test and gold splits are provably unfiltered

## Things that will tempt you

- writing a quick CER helper for the training loop — this is the prohibition
  that matters most
- running your own layout detection when `json_raw` already has the boxes
- reaching for a global alignment because the library already has one — it will
  quietly mislabel every header, footer and page number on every page
- defining reading order separately in the preparation path and the evaluation
  path
- tightening the alignment filter to make the data look clean
- training on full pages because the alignment step is annoying
- keeping optimizer state in every checkpoint
- inlining decode settings in the eval path so they drift from `decode.json`
- starting the sweep before the baseline stability gate passes

Start with step 1, on one book. Show me the alignment output before anything
else.
