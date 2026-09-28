# Addendum to "Prompt — build the MLOps layer" (25/09, reviewed)

> Paste this after the 24/09 prompt and add: "This amends the 24/09 spec.
> Where they conflict, this file wins. List what conflicts with code already
> written before changing anything."

---

## 0. Clarifications of existing constraints

**Constraint 1 (no metrics) — scope.** Forbidden: any error rate, edit
distance, CI, share or delta computed outside `viet-ocr-eval`. Allowed: weight
diffs, hashes, timings, GPU hours, VRAM, page counts, and exact string equality
("pages whose output changed").

The source grep test fails on:
- imports of `editdistance`, `Levenshtein`, `rapidfuzz`, `jiwer`,
  `torchmetrics.text`, `nltk.metrics.distance`, `difflib`
- function definitions whose name contains `levenshtein`, `edit_distance` or
  `editdistance`, or matches `^(compute|calc|calculate|get)_(cer|wer|der|ter)`

**Do not grep for the bare substrings `cer|wer|der|ter`.** They match `order`,
`render`, `filter`, `header`, `loader`, `parameter` and `after`, so the test
would fail on ordinary code and end up disabled. Reading keys such as
`cer_micro` out of a report is allowed.

**Constraint 5 (test touched once) — definition of one access.** One access is
one `evaluate_test.py` invocation for one version, covering **both views and
both sets (test + gold)**. The two views are not two accesses.

## G. vLLM serving contract (new section)

vLLM is already the serving engine. This section makes it reproducible and
makes base and adapted decode identically.

1. **Separate environment.** vLLM runs in its own container or venv, not the
   Paddle one, as the official vLLM recipe for this model recommends. Pin a
   version **≥ 0.11.1** (the recipe's minimum) and the image digest; store both
   on every `model_versions` row and in the repro package.
2. **Fixed launch flags**, written by `serve.sh` and stored on the row:
   `--served-model-name <version> --trust-remote-code --dtype <D>
   --max-model-len <N> --max-num-batched-tokens 16384
   --no-enable-prefix-caching --mm-processor-cache-gb 0
   --gpu-memory-utilization <X> --generation-config vllm`
   - `--dtype`: the **same dtype the Paddle dev evaluation used**. `bfloat16`
     only if the GPU supports it (compute capability ≥ 8.0, Ampere or newer);
     otherwise `float16` on both sides. A dtype mismatch between the two paths
     adds to the parity noise floor.
   - `--generation-config vllm` stops a `generation_config.json` in a model
     directory from supplying sampling defaults. Without it, a parameter not set
     explicitly in the request can come from that file, and base and adapted
     can decode differently.
   - `--gpu-memory-utilization`: vLLM takes about 90% of the GPU by default.
     Set it explicitly and low enough to leave room for PP-DocLayoutV3 and the
     backend on the same 24 GB. Bench reports record it.
3. **Explicit sampling on every request**: temperature 0, top_p 1, and
   `max_tokens` equal to the harness's `max_new_tokens`, with the same prompt
   text and chat template as the harness. Use a repetition penalty only if the
   Paddle harness used one, and only after checking both implementations
   define it the same way. The backend logs the effective sampling params per
   job.
4. **Model directory = artefact.** Hash every file: weights, `config.json`,
   `preprocessor_config.json`, tokenizer files, chat template, and the
   remote-code `.py` files, which `--trust-remote-code` executes.
   **Copy non-weight files from the base snapshot into the merged directory;
   do not regenerate them.** Byte-identity then holds by construction. If the
   converter must write `config.json`, allow differences only in an allowlist
   of keys (for example `torch_dtype`) and print the diff. `serve.sh`
   re-verifies every hash against the row before launch and refuses on
   mismatch.
5. **Name check.** After launch, `/v1/models` must return exactly `<version>`.
   `evaluate_test.py` checks it before and after each view, to detect a
   mid-run restart.
6. **Image-token check** (tier 2, see build order). For the smoke crops, log
   image tokens per crop in Paddle and in vLLM (vLLM reports prompt tokens in
   `usage`). Different counts mean the processors resize differently, which
   explains a parity failure without any weight bug.

Runtime LoRA in vLLM (`--enable-lora`) is out of scope: the adapter is in
Paddle format and support for this architecture is unverified.

## B. Amendments to promotion

Insert before the CER parity gate:

- **3a. Weight-level merge check**, on **Paddle-format tensors, before
  conversion**, so base and merged share one layout.
  - Every tensor is either unchanged or an expected change. Expected changes
    are the LoRA target weights plus any extra trainable parameters listed in
    the adapter (`modules_to_save`, biases, norms). If the merge cast dtypes,
    compare against the base cast to the merged dtype.
  - For each LoRA target, check `W_merged − W_base ≈ scale · (B·A)`. Paddle
    `Linear` stores weights as `[in, out]`, the transpose of torch, so build the
    product in the matching orientation. `scale = lora_alpha / r`, or
    `lora_alpha / sqrt(r)` if rsLoRA is on in the config. The tolerance is
    **relative**, for example `max |residual| ≤ 2⁻⁷ · max |W_base|` in bf16,
    because the rounding error of a bf16 add scales with the weight.
  - Changed-tensor count must equal the expected-change count. On failure,
    list the module names. Also list adapter modules that map to no base tensor.

  This catches the ERNIE #1405 class of failure: adapter weights that exist but
  were not applied, or were applied wrongly. It **cannot** see modules that were
  never trained. In the published Javanese fine-tune, 6 of 586 LoRA modules in
  the visual head were missing because the paddleformers regex never targeted
  them during training; that is a training-time problem, caught only by the
  resolved target-module count logged at training start. Cite it that way in the
  thesis.
- **4a. Converter check on base** (tier 2). Run the same Paddle→torch converter
  on the unadapted base and compare tensor by tensor with the official
  torch-format release. If the Paddle base and the official release are the
  same safetensors files, this reduces to confirming the converter does only
  layout changes.

Change the parity gate:

- **Calibrate first.** Before any adapted gate, run base in Paddle against base
  in vLLM on the same fixed crops of **at least 100 dev pages**. Base inference
  is cheap, and 20 pages is too few to estimate a floor. Score both with
  `viet-ocr-eval` and `compare` them. Report the relative CER difference and
  the number of pages whose output changed. This is the framework noise floor;
  store it on the `base-v1` row.
  - If the floor is ≥ 1%, a correct conversion cannot meet a 1% threshold. Set
    the b↔c threshold to `max(1%, 2 × floor)` and **write it into
    `decision.md` before running the adapted gate.**
  - This step is also what makes the base model's dev numbers (Paddle)
    comparable with its fixed-crop test numbers (vLLM).
- Report pages changed for a↔b and b↔c, not only the CER difference.
- Run a, b and c one after another. Never run vLLM and Paddle inference on the
  GPU at the same time.

## C. Amendments to the test evaluation

- **Pre-registration.** Before the first test access, `decision.md` contains a
  `primary_endpoint` block:
  - comparison: base-v1 vs the final model; the seed replicate is reported
    descriptively
  - view, set, and CER aggregation (micro or macro)
  - threshold: ≥ 20% relative CER reduction, from the proposal
  - **decision rule**: whether "met" means the point estimate or the whole 95%
    CI clearing −20%. `viet-ocr-eval compare` prints both, so choosing after
    seeing them is a forking path.
  - secondary metrics, including the diacritic share for target 2
  - gold subset definition: source, size, who verified it, transcription
    guideline

  `evaluate_test.py` refuses if the block is missing. **Finalise `decision.md`
  completely before the first access**: the calibration result, threshold and
  fallback all go in first, because the file is frozen from then on.
- **Log at start, not end.** Write a `status=started` line before the first
  test file is read, and a `status=completed|aborted` line with report hashes
  at the end. An aborted run is still an access; a rerun needs
  `--rerun-reason`.
- **Each log line records** the git blob sha of `decision.md`, split hash,
  served model name, weights hash and operator. After each access, **commit
  `test_access.log`**; the git history is the tamper evidence. A hash chain
  between lines is tier 2.
- **Clean tree.** Refuse if **tracked** files are modified or `decision.md`
  differs from the version recorded at the first access. Evaluation outputs
  must be written to a gitignored directory or outside the repo; otherwise the
  first version's reports make the tree dirty and the second version is
  refused.
- **Rehearsal on dev.** `evaluate_test.py --rehearsal` runs the identical code
  path on a **fixed 50-page dev subset**, writes `rehearsal.log` and never
  `test_access.log`. Both views must pass it (markup check, page completeness,
  name checks) for a version before its test access is allowed. Full dev is not
  needed; the point is plumbing, and end-to-end on full dev would cost hours
  you do not have.
- **Page completeness.** Every page of the split appears in every report. A
  page whose job failed or timed out is scored as empty output, never dropped.
  Report the count per version, and abort if the scored page set differs from
  the split page set.
- **Idempotency.** End-to-end idempotency keys include the evaluation run id
  and version, so a rerun never returns an earlier job's output. Each version
  starts with an empty queue.
- **Layout is part of the system.** Record the paddleocr version and the
  PP-DocLayoutV3 weights hash in every end-to-end report and in the repro
  package.
- **Describing the gap.** The fixed-crop vs end-to-end difference comes from
  **layout detection, reading order, and region inclusion** (the harness's page
  assembly vs `to_plaintext()` policy `body-v1`). Do not call it layout alone.
- `REPRODUCE.md` states that VieBookRead references are LLM-corrected pseudo
  ground truth and that gold is human-verified.

## A. Amendments to tracking

- **MLflow key names cannot contain `=`.** Use `cer_micro.era.1900s`. Add a
  unit test that logs one param, one metric and one tag of each key shape used.
- **Original timestamps.** Run start and end come from `run.json`; metric
  timestamps come from the log lines when present, not from import time.
- **Resume overlap: check, do not assume.** The power loss hit during the dev
  evaluation at step 4000, and the resume fast-forwarded the data loader to step
  4000, so there may be no duplicated steps. Detect duplicate step numbers in
  `train_metrics.jsonl` and duplicate files in `eval/`. Only if duplicates exist,
  keep the post-resume segment and tag the discarded range
  (`discarded_steps=…`). Never average them, and never drop them silently.
- **Downtime source.** A committed `incidents.yaml` with run, start, end, cause
  and `resumed_from_step`. GPU hours are the sum of active segments. Log the
  38-minute data fast-forward as its own segment, not as training.

## H. Fallback — decided now, written in `decision.md`

If the weight-level check or the parity gate fails and is not fixed by
**[27/09 12:00]**:

- The fixed-crop view for all declared versions runs through the Paddle path
  used for dev: runtime adapter for adapted, Paddle for base.
- The end-to-end view runs through the backend with its **native-Paddle
  recognizer** (backend constraint 2 requires it to be swappable) for **both**
  base and adapted. The engine is then the same on both sides, and the product
  still has an adapted end-to-end result and a throughput number. `bench.py`
  reports the engine used, and the thesis says why vLLM was not.
- Thresholds are never changed after seeing a failure.

## Build order and time budget (replaces the 24/09 list)

0. **vLLM smoke + calibration**, half a day. The pinned vLLM serves base 1.6
   with the section G flags. The base Paddle↔vLLM noise floor is measured on
   ≥100 dev pages and written into `decision.md`, together with the primary
   endpoint and the fallback.
1. `register_base.py`, `promote.py` with 3a, and `serve.sh`.
   *Gate: a corrupted merge and an unapplied module are caught by 3a; the real
   merge passes; the row is inserted with `is_active = false`.*
2. `evaluate_test.py`.
   *Gate: the 24/09 gates, plus the rehearsal passes for base and final, and an
   aborted run counts as an access.*
3. MLflow backfill and `log_eval.py`.
4. `make verify-splits`, `make repro-package`.
5. Grafana.

**Tier 1 — never cut:** pre-registration; G.2–G.5; the weight-level check;
calibration and the parity gate; the rehearsal; the test access log with
start/end lines and a commit; the markup abort; page completeness; idempotency
keys; the fallback.

**Tier 2 — cut first if time runs out:** 4a, G.6 image-token check, the hash
chain, original metric timestamps, MLflow backfill detail beyond the dev-CER
curves, repro-package automation (assemble by hand from the same list), Grafana.
