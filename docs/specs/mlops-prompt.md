# Prompt — build the MLOps layer  (revised 24/09)

> Paste everything below the line into Claude Code at the repo root.
> Edit the bracketed values first. Run after the backend's `model_versions`
> table and eval-manifest export exist.
> If a session built from the earlier version is already running, paste this
> whole file and add: "This replaces the earlier spec. List what conflicts with
> code already written before changing anything."

---

You are building the MLOps layer for a self-hosted Vietnamese book OCR project.
Master's capstone, hard deadline **[30 September 2026]**, about six days away,
on one machine with one 24 GB GPU.

This layer has two jobs and nothing else:

1. **make every number in the thesis traceable** to the exact artefacts that
   produced it
2. **stop an untrustworthy model or an untrustworthy evaluation** from reaching
   the thesis or the serving path

It is not a platform. If a component does not serve one of those two goals, it
is out of scope.

## Where the project actually is

Read this first; it changes what you build.

- **Training is finished.** Six runs exist under `[runs/]`, each following the
  run-directory contract (`resolved_config.yaml`, `run.json`,
  `data_manifest.json`, `train_metrics.jsonl`, `checkpoints/`, `best/`,
  `eval/dev_step-*.json`). You are **backfilling** them into tracking, not
  logging live training.
- One run, `exp_lr2e4_long`, was interrupted by a power loss (00:59 to 07:21 on
  23/09) and resumed from step 4000. That downtime is not GPU time.
- **The final model has already been chosen on dev**, and the choice is
  recorded in a committed `[decision.md]`: the final model, plus one seed
  replicate that will be reported alongside it. Nothing in this layer re-selects
  a model.
- Dev CER was measured by the training harness on **region crops cut from the
  corpus's Azure boxes**. The deployed system cuts regions with
  **PP-DocLayoutV3**. Those are different inputs, and the evaluation design
  below has to account for it.
- The backend exists and provides: the `model_versions` table, a worker that
  refuses jobs whose `model_version` does not match the model name vLLM reports
  on `/v1/models`, `to_plaintext()`, `GET /exports/eval-manifest`, and
  `bench.py`.
- **`viet-ocr-eval` is at protocol 1.1**, at `[./skills/viet-ocr-eval]`.
  CLI: `evaluate.py selftest | verify | score | compare`. `compare` reports
  CER, DER, TER, WER and WSER with paired CIs, **and** a
  `reduction_shares` block splitting the reduction by error category. Every
  report includes a markup audit in `health.markup_chars`.

## Hard constraints

1. **Never compute a metric yourself.** Every error rate, confidence interval
   and share comes from `viet-ocr-eval` via its CLI as a subprocess, parsed from
   its JSON. No edit distance, no quick CER helper, anywhere.

2. **Postgres `model_versions` is the registry.** MLflow tracks runs; it is not
   a registry. Do not enable MLflow Model Registry.

3. **Nothing becomes servable automatically.** Registration writes
   `is_active = false`. Activation is a separate command run by a human.

4. **Artefacts are immutable and content-addressed.** sha256 at creation,
   never overwritten.

5. **The test set is touched once per declared model, and only for declared
   models.** See section C. This is the constraint that protects the thesis
   result, and it is enforced in code, not by convention.

6. **Human-corrected pages from the usability study are never an evaluation
   reference.** Reviewers start from the adapted model's output, so their
   corrections lean toward it; scoring models against them favours the adapted
   model. Refuse any eval manifest tagged `purpose=usability`.

7. Everything runs locally in docker-compose.

## A. Tracking — MLflow plus a backfill importer

MLflow with a sqlite backend and a local artifact store, added to the existing
docker-compose.

**`backfill_runs.py runs/`** imports each existing run directory as one MLflow
run:

- params: the whole `resolved_config.yaml` flattened, seed, git sha, split
  hashes from `data_manifest.json`
- step metrics from `train_metrics.jsonl`: loss, and learning rate, samples/s
  and grad norm **when present**
- **dev metrics per step** from `eval/dev_step-*.json`: CER, DER, TER, WSER,
  runaway rate, empty rate. This dev-CER curve is the validation curve the
  thesis shows; there is no separate validation loss, and the thesis says so.
- tags: `best_step`, `best_dev_cer`, adapter sha256, and an `incidents` tag for
  anything like the `exp_lr2e4_long` interruption
- GPU hours computed from `run.json` start and end **minus recorded downtime**

**Missing is recorded as missing.** If a field was never logged, write a tag
such as `grad_norm=not_recorded`. If learning rate is absent from the logs,
you may reconstruct it from the schedule in `resolved_config.yaml`, but log it
under a separate key `lr_reconstructed` so nobody mistakes it for a
measurement. Never interpolate or invent a training metric.

**`log_training_memory.py <run_id> <nvidia-smi csv>`** attaches peak training
VRAM, measured separately by a short re-run of the final config, to that run as
`peak_vram_train_mib` with a tag naming how it was measured.

**`log_eval.py <report.json | compare.json>`** — the bridge, roughly forty
lines. Logs normalization and `protocol_version` as params; the headline
metrics, run health including `markup_chars`, and stratified metrics as
`cer_micro.era.1900s`-style keys (MLflow rejects `=` in key names); for a compare file, every relative delta with
its CI and the full `reduction_shares` block (`share.diacritic`, its CI,
`p_diacritic_largest`). Attach the JSON and Markdown as artifacts.

## B. Registration and the parity gate

### Register the base model

`register_base.py --name base-v1` creates a `model_versions` row for the
unadapted model: no adapter, no merge, base ref and commit sha, preprocess and
decode config. The comparison needs a baseline row to point at, and it must be
registered with exactly the same preprocessing and decoding as the adapted model.

### Promote the adapted model

`promote.py <run_dir> --name <version>` runs these steps in order and **aborts
on the first failure, leaving no row and no partial artefact**:

1. **Declared check.** Refuse unless `<run_dir>` is listed in the committed
   `decision.md`.
2. Record the adapter sha256 from `best/SHA256SUMS`; confirm it matches.
3. Merge with `erniekit export ... lora=True`.
4. Convert merged Paddle weights to torch safetensors for vLLM.
5. **Parity gate, three-way, on identical region crops.** Take a fixed smoke
   set of 20 dev pages and their region crops — the same crops, prompt and
   decode settings for all three:
   - (a) base + adapter applied at runtime in Paddle
   - (b) merged weights in Paddle
   - (c) merged torch weights served by vLLM

   Score each with `viet-ocr-eval score`, then run `compare` for a↔b and b↔c.
   **Abort unless both relative CER differences are under 1%.** a↔b tests the
   merge; b↔c tests the conversion. Keeping the crops fixed is what makes a
   failure attributable: if this step fed whole pages through layout, a layout
   difference would look like a merge bug.
6. **Repeatability.** Run (c) a second time with a different vLLM batch size.
   Report the relative CER difference and the number of pages whose output
   changed. Greedy decoding makes seeds irrelevant, so batch composition is
   the only remaining source of run-to-run variance, and one flipped token can
   send this model into a repetition loop. Warn above 1%; do not abort.
7. `viet-ocr-eval selftest`; abort on failure.
8. `viet-ocr-eval verify <train.jsonl> <test.jsonl>`; abort on leakage.
9. Insert the `model_versions` row, `is_active = false`, with base ref and sha,
   adapter sha256, merged weights URI, preprocess and decode config, the parity
   and repeatability results, and the MLflow run id.

The parity gate is the most important thing in this layer. LoRA merging in this
model family has a documented history of dropping modules — `PaddlePaddle/ERNIE`
issue #1405 reports the ERNIEKit merge failing on PaddleOCR-VL, and a published
fine-tune of the same family found its merged checkpoint gave meaningless error
rates while the runtime adapter was fine. Without the gate, a conversion bug
looks like a bad model.

### Serving a version

`serve.sh <version>` launches vLLM with that row's weights and
**`--served-model-name <version>`**. The backend worker refuses jobs whose
model does not match the served name, so this flag is what connects the
registry to the evaluation. Only one model is served at a time.

`activate.py <version>` flips `is_active`, writes an audit row, and prints the
eval summary for the incoming and outgoing versions.

## C. The test evaluation — once, declared, two views

`evaluate_test.py --versions base-v1,<final>,<replicate>` runs the locked test
set and the gold subset.

**Access control.** Keep an append-only `test_access.log` recording version,
timestamp, git sha and operator. Refuse any version not in `decision.md`.
Refuse a second test run of the same version unless `--rerun-reason "<text>"`
is given, and write that reason to the log. The log goes in the reproducibility
package. On a small test set, choosing among candidates by test score turns the
result into a selection effect; this log is how the thesis shows that did not
happen.

**Two views of every model**, both required:

| view | input | what it measures |
|---|---|---|
| **fixed-crop** | the same Azure-box region crops the dev evaluation used | recognition alone; directly comparable with the dev numbers |
| **end-to-end** | pages through the backend: upload → queue → PP-DocLayoutV3 → recognition → `to_plaintext()` → `eval-manifest` | what a user of the system gets |

Run the fixed-crop view with each version served in turn, **reusing the
training harness's dev-evaluation code** (crop set, reading order, page
assembly), pointed at the served model, so it is scored exactly as dev was.
The parity gate is what makes that swap from runtime adapter to served merged
weights legitimate. Run the end-to-end
view by `serve.sh <version>`, submitting the test documents with that
`model_version`, then exporting with `source=machine`.

For each view, on both test and gold:

1. `score` each version
2. **abort if any report has `health.markup_chars > 0`.** Markup reaching the
   scorer means the plain-text path is broken, and base and adapted models
   differ in how much they emit, so it becomes a fake improvement
3. `compare` base against final, and base against the replicate
4. log everything via `log_eval.py`

The gap between the fixed-crop and end-to-end numbers is layout error, and it
affects both models. Report it; do not hide it. It is also why the test CER will
not match the dev CER, and the thesis should say that before a reviewer asks.

## D. Split versioning

- corpus manifest with per-file sha256 and a rollup hash
- split files hashed; every run and evaluation records the split hash it used
- a `make verify-splits` target running `viet-ocr-eval verify`. No pre-commit
  hook; not worth the time now.

## E. Reproducibility package

`make repro-package` → one dated tarball: git sha, `decision.md`,
`test_access.log`, resolved configs for all six runs, `requirements.lock` and
container digests, corpus manifest and split files with hashes, decode config,
the `viet-ocr-eval` version, every evaluation and compare report, bench reports,
parity and repeatability results, a short model card, and `REPRODUCE.md`.

`REPRODUCE.md` states plainly: the training runs listed; which one was chosen
and on what criterion; that test was run once per declared version; the two
evaluation views; and the known incidents.

## F. Grafana — one dashboard, no alerts

One provisioned dashboard JSON over the backend's `/metrics`: pages/hour, warm
service time p95, queue wait, per-stage time, job failure rate, GPU VRAM,
process RSS, `serving_runaway_rate`, empty-output rate.

Label the runaway panel clearly: **serving runaway is a reference-free proxy**
(output longer than 3× the document's median), not the thesis runaway rate,
which comes from `viet-ocr-eval` against the reference. The thesis latency
numbers come from `bench.py` reports, not from this dashboard. No alerting —
cut for time.

## What you are NOT building

CI/CD, retraining, hyperparameter search, a feature store, A/B or canary
serving, Kubernetes, cloud storage, pre-commit hooks, alerting, a custom UI.

## Build order — priority matches the calendar

Stop at each gate.

1. **`register_base.py`, `promote.py`, `serve.sh`** — needed first, because the
   test evaluation depends on them.
   *Gate: the parity gate aborts on a deliberately corrupted merge and passes on
   the real one; the final model is registered with `is_active = false`.*
2. **`evaluate_test.py`**, with access control and both views.
   *Gate: a second run of the same version is refused without a reason; a
   version missing from `decision.md` is refused; a report with markup
   aborts.*
3. **MLflow, `backfill_runs.py`, `log_eval.py`, `log_training_memory.py`.**
   *Gate: all six runs appear with dev-CER curves; `exp_lr2e4_long` carries its
   incident tag and GPU hours exclude the downtime; a compare report shows
   `share.diacritic` with its CI.*
4. `make verify-splits`, `make repro-package`.
5. Grafana dashboard.

If time runs out, cut from the bottom. Never cut the parity gate, the test
access log or the markup abort.

## Acceptance criteria

- no edit-distance or error-rate computation in this layer, asserted by a
  source grep test
- any `promote.py` failure leaves no registry row and no partial artefact
- every `model_versions` row traces to a git sha, a split hash and an MLflow run
- `test_access.log` shows exactly one run per declared version, or a stated
  reason for each extra one
- no evaluation manifest tagged `purpose=usability` is ever scored
- training metrics never recorded are tagged as not recorded, never filled in

## Things that will tempt you

- a quick CER helper for a sanity check
- running the test set on all six runs "just to see"
- promoting whichever run looks best on test
- feeding whole pages into the parity gate
- skipping the fixed-crop view because end-to-end is "the real one"
- reconstructing grad norm or validation loss that were never logged
- counting the power outage as GPU hours
- using usability corrections as extra gold
- building alerting because Grafana makes it easy

Start with step 1. Show me `register_base.py` and the parity-gate design before
writing `promote.py`.
