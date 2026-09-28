# Source audit before test access — 25/09/2026

Read-only audit of the master's capstone (PaddleOCR-VL-1.6 + LoRA on VieBookRead) against the specs in
`docs/specs/`. Output: GO / NO-GO for test access, ranked findings, fix plan. Nothing was fixed.

| | |
|---|---|
| Repos audited | training + skills (root repo, HEAD cdb4bf9, skill tree dirty), backend 2035c27, frontend d44a9d0, mlops cd10b01 (all clean) |
| Specs used | `training-prompt.md`, `frontend-prompt.md`, `frontend-prompt-delta.md`, `mlops-prompt.md`, `mlops-addendum-25-09.md`, `decision.md` (committed blob `fc2e096c`, mlops bf495a1) |
| **Specs not provided** | **`main.pdf`, `backend-prompt.md`, `backend-prompt-delta.md`.** B items are checked against the checklist wording, the mlops specs and `backend/docs/migration-plan.md`; the C table is reconstructed from specs that quote the proposal. |
| Auditors | lead (G, X, consolidation); subagents D+T+skill, B, F, M; one falsifier on the Blocker-relevant PASS items |
| Evidence | `audit/evidence/{g,x,dt,b,f,m,falsifier}/` |

**Safety compliance.**
- No model touched test or gold. No test or gold report or hypothesis file was opened; the prior-access
  timeline was built from file names, mtimes, git history and the access log. One incidental exposure: a
  grep printed one test WSER line from `training/work/analysis/summary.md` (DT §6); nothing was derived from it.
  `decision.md`, which the audit had to read, itself states the test results.
- No writes to anything real. The real `mlops` state files hash the same before and after
  (`m/real_repo_snapshot_final.txt`). The frontend `dist/` and `src/.umi*` are untouched. All stacks ran
  under the scratch compose project `audit-x`, using its own volumes and image tags.
- GPU. With your approval, one isolated temporary base recognizer (:18090) and layout server (:18091) ran
  for about 13 minutes on 5 **dev** pages. They were stopped by PID afterwards, and GPU memory went back to
  13.7 GB (`x/x3_nvidia_*.txt`). The live servers on :8090/:8091/:8092 were never contacted.
  `evaluate_test.py` was not run, with or without `--rehearsal`.

---

## 1. Verdict: **NO-GO**

**The premise of this gate, a single held-out test access, no longer holds.**
- **Base and final have each already been scored on test twice.** The fixed-crop view on test and gold ran
  17–19/09 and the end-to-end view on test ran 24/09. There are also four unrecorded looks at test pages: the
  backend gate-6 scoring of 300 test pages, a scored 6-page D4 dry run, 12 crops pushed through the base
  server, and latency benches run on test pages.
- **Every endpoint rule in `decision.md` was fixed after those results were known.** `decision.md` discloses
  this. The primary endpoint is robust to it: every CI clears −20%. Target 2's "largest" reading is not: gold
  fails it.
- **Another `evaluate_test.py` run would be the third access per model.** It cannot turn the result into a
  confirmatory one.
- **It would also be refused today**, for three reasons: the skill tree is dirty, the rehearsal is stale
  (older code tree, older `decision.md` blob), and each version already has accesses, so a `--rerun-reason`
  is required.

**6 of the 11 items that GO requires at PASS fail: G1, T5, M1, M2, M3 and M5.** Four of those six (G1, M2, M3,
M5) were broken by the falsifier. G3, D1, D2, D4 and T3 held.

**Recommendation.**
- Do **not** make another test access to "get the number". The numbers exist and cannot become pre-registered.
- Spend the time making the existing test results honestly reportable (fix plan, §7).
- The one thing a new access would add is the end-to-end view on **gold**. It can be obtained without any
  inference, by re-scoring the stored D4 outputs of the 250 gold pages with `viet-ocr-eval`. That should be
  logged as a use of test outputs (A-8).

**Blockers, in fix order**

1. **A-1 — The test set was accessed before pre-registration.** Two accesses per model plus unrecorded looks;
   every endpoint rule post hoc. This cannot be undone; the fix is complete disclosure and post-hoc framing
   (S). Until then, any thesis sentence saying the test set was "used once", "locked" or "pre-registered" is
   false.
2. **A-2 — Base hypotheses contain markup (T5 rule).** 14 characters on 3 of 150 dev pages; `decision.md`
   records 143 on test. The markup abort was waived for base after its count was known. Decide one of:
   - (a) keep the waiver and print the bound next to every base number (S);
   - (b) add one plain-text converter applied to both models and re-score the stored outputs on CPU (M).
3. **A-3 — `decision.md` has no fallback deadline (M1 rule).** Substantively empty: plan H *is* the fallback
   content and nothing can trigger a switch. Because `decision.md` is frozen, the only resolution is a
   recorded owner waiver (S).

**Majors to fix before any further access** (only if you decide to make one): A-44 (M5 rehearsal gate), A-45 (M4
Engine code not hashed), A-46 (M2 `--decision` override), and A-32/A-9 (failed pages, usability refusal).
Without another access, these matter only for the registry and the tooling, not for any number that already
exists.

---

## 2. Findings (most severe first)

Source IDs: G/X = lead, DT = data+training+skill auditor, B = backend auditor, F = frontend auditor,
M = MLOps auditor, FZ = falsifier. Effort: S under 1 h, M under half a day, L longer.

### Blockers

**A-1 · Blocker · T3, M5, prior access · test set accessed before pre-registration; access log incomplete** (G, DT-2, M-1, M-2)
- **Spec:** `mlops-prompt.md:70-72` (constraint 5), `:181-187`, `:281-282`; `mlops-addendum-25-09.md:133-148`
  ("Finalise `decision.md` completely before the first access").
- **Evidence:**
  - `g/prior_test_access_timeline.txt` and `dt/prior_test_access_ledger_metadata.txt`:
    - finals ledger events: base test generation 17/09 21:03Z, final 18/09 11:08Z, gold and compares by
      19/09 20:02Z, stratified tables 20/09;
    - D4 end-to-end test runs 24/09, `compare_d4.json` at 25/09 01:43 +07;
    - `decision.md` first committed 25/09 07:21 +07 (7a8cd16), and target 2 fixed at 08:31 (9d1ffb4).
  - `m/prior_test_touches.txt`: touches missing from `test_access.log` and from `REPRODUCE.md`'s "twice per
    model":
    - `backend/reports/eval/report_gate6_machine_bench2.*` (300 test pages scored, 24/09 ~05:27Z);
    - the `d4-dry/` run (6 pages scored and compared);
    - 12 test crops through the base server (`recognizer_server/README.md:11-12`);
    - latency benches reading `TEST_MANIFEST` (`backend/bench.py:52,220`).
  - `decision.md:8-44` discloses accesses 1–4 and that the registration is post hoc.
- **What is still sound:** selection was dev-only. T3 passes: no test/gold id in 1,370 run/log/leaderboard
  files, and the model was fixed before access 1 (DT §4).
- **Why it matters:** "one-time evaluation on a locked test set" is not a true description anymore. Target 2
  was defined after its test and gold results were known, and gold fails that rule.
- **Fix:**
  - Append hand-written `backfilled` lines for the gate-6 and dry-run scorings, with evidence hashes and a
    reason, and commit them. Note the unscored touches in `REPRODUCE.md`.
  - Correct "twice per declared model" in `REPRODUCE.md`.
  - Thesis: report test results as post hoc; present target 2 as exploratory, with test and gold side by side.
  - Do not edit `decision.md`.
- **Effort:** S.

**A-2 · Blocker (T5 rule; bounded) · T5 · base model emits markup that reaches the scorer on the fixed-crop path** (DT-1, M-13)
- **Spec:**
  - `mlops-prompt.md:207-209` ("abort if any report has `health.markup_chars > 0`") and `:273` ("never cut the
    markup abort");
  - audit rule T5.
  - `decision.md:46-56,162-167` exempts base after the fact.
- **Evidence:**
  - `dt/t5/report_base_dev150.md`: "pages with markup in the hypothesis: 3 (14 markup characters)"; the pages
    are `026/page_10` (8), `035/page_174` (2) and `117/page_65` (4).
  - The compare prints "Markup in hypotheses: base 14 chars, adapted 0 chars".
  - Cause: `training/ocrtrain/infer.py:196-205` → `deveval.write_page_manifest` passes raw decoded text. The
    end-to-end path strips markup in `to_plaintext()` (`plaintext_stats.markup_chars_removed`), so the two
    views treat markup differently.
- **Why it matters:** markup counts as recognition error for base only, which inflates the reduction. The size
  is bounded: 14 characters against 4,217 edits removed on dev150, and ≤149 characters on test per
  `decision.md`.
- **Fix:** either
  - (a) record the waiver and print base's markup count beside every base number (S); or
  - (b) apply one deterministic plain-text converter to both models' stored outputs and re-score on CPU, with
    no new inference (M).
- **Effort:** S / M.

**A-3 · Blocker (M1 rule; substantively Minor) · M1 · `decision.md` has no fallback deadline** (M-16)
- **Spec:** `mlops-addendum-25-09.md:200-212` (fallback "decided now … [27/09 12:00]"); audit rule M1.
- **Evidence:** `decision.md:169-171`: "plan: H is the plan of record, not a fallback". There is no deadline.
- **Why it matters:** the literal M1 rule. In substance, the fallback's content (Paddle fixed-crop, native
  Paddle end-to-end for both models) is exactly what runs, so no gate failure can trigger a switch.
- **Fix:** an owner waiver recorded outside `decision.md`, in `REPRODUCE.md` and the thesis. `decision.md` is
  frozen.
- **Effort:** S.


### Major

**A-4 · Major · G2 · skill 1.2 is uncommitted and stamps protocol 1.1** (DT-5, M-8)
- **Evidence:**
  - `git status` shows 4 modified files and an untracked `viet-ocr-eval-1.2/`. The working tree equals the
    pristine 1.2 copy.
  - `scripts/evaluate.py:82` stamps "1.1". `mlops/mlops/evalcli.py:50-54` reads it as 1.1, and
    `repro.py:241-244` would label a 1.2 tree 1.1.
  - Scoring code is unchanged: `metrics.py` is byte-identical and `canonical()` is unchanged. The dev150
    re-score reproduces `protocol_1.1/dev150/compare.json` exactly.
  - Selftest passes (`dt/selftest_1.2.txt`).
- **Spec:** `mlops-prompt.md:229` ("the viet-ocr-eval version").
- **Why it matters:** reports cannot say which verifier produced them, and `evaluate_test.py` refuses on the
  dirty tree.
- **Fix:** bump the stamp to 1.2, commit the skill, and record the tree sha256 in `REPRODUCE.md`.
- **Effort:** S.

**A-5 · Major · G1, G2, X1 · an analysis script computes CER and CIs outside the CLI; the training guard test fails** (DT-3, FZ)
- **Evidence:**
  - `training/work/analysis/runaway.py:20-21` does `import metrics as M` and calls `M.score_page` (`:266,377`)
    and `M.paired_delta` (`:295-301`) on test outputs.
  - It also computes CER itself (FZ, `falsifier/G1_training_guard_fails.txt`):
    - `(tot_ed-ed_ra)/(tot_ref-ref_ra)` at `:271,274`;
    - per stratum `:323`, per book `:334`, macro `:272`, and the de-duplicated-page CER `:382`;
    - with `cap_runaway=False`, a non-default scoring.
  - `work/analysis/summary.md:142` cites its sensitivity result ("−57.0% [−61.3, −50.9]") as the number to
    quote beside the headline.
  - `work/analysis/protocol_1_1.py:222-223` imports `normalize.canonical`.
  - `dt/pytest_training.txt`: 12 passed, **1 failed** (`test_no_metric_code`).
  - The guards can be evaded (`falsifier/G1_guard_evasion.txt`):
    - the training regex does not ban `difflib` or `nltk`;
    - the mlops AST check misses `from nltk import edit_distance`, `torchmetrics.functional…char_error_rate`
      and `__import__`;
    - all three guards miss `importlib.import_module` and `def cer_of(`;
    - the mlops guard skips `work/`;
    - the frontend has no guard.
- **Spec:** `training-prompt.md:44-48` (constraint 3) and `:242-243`.
- **Why it matters:** a number the analysis tells you to quote next to the headline was computed outside the CLI
  with non-default scoring.
- **Fix:** re-derive those numbers with CLI `score`/`compare` on subset manifests, following the
  `evaluate_final.py:354-371` pattern, or mark `runaway.md` as not a thesis source. Make the test pass.
- **Effort:** M.

**A-6 · Major · T1 · no run records a git sha, and the final model's training code is not in git** (DT-6)
- **Evidence:**
  - All 14 `run.json` have `git_sha: null`. `training/` entered git at 8172abf (23/09).
  - The final run's `source_sha256` is `2ea991a0…`, which no commit's tree reproduces (`9f712b7a…`); see
    `dt/t1_source_hash_vs_git.txt`.
  - The only source changed since is `ocrtrain/config.py`.
  - Everything else in T1 passes: `rundir.validate()` is clean and `sha256sum -c best/SHA256SUMS` is OK in
    every run.
- **Spec:** `training-prompt.md:138-140`; `mlops-prompt.md:280`.
- **Fix:** reconstruct the 17/09 `ocrtrain/config.py`, confirm that `source_hash()` gives `2ea991a0…`, tag
  that tree, and map it in `REPRODUCE.md`.
- **Effort:** M.

**A-7 · Major · T7 · "baseline is stable" is unsupported** (DT-4)
- **Evidence:** `baseline.py` compares seeds 13/14/15 under greedy decoding: sd 0.0, 14,044/14,044 identical
  regions (`dt/t7_baseline_gate.txt`). A seed gate cannot fail when decoding is greedy.
- **Mitigation:** the engine runs only at batch 1 (`work/logs/batching_probe.json`). Three full-dev reruns
  were byte-identical.
- **Spec:** `training-prompt.md:205-219` vs skill 1.2 `references/protocol.md` §4 (see §4 of this report).
- **Replacement:** the §4 batch-order repeatability check. Run base twice on dev150 with a different region
  order or a different number of generation processes, then report pages changed and runaway rate. About
  50 min of GPU.
- **Fix:** run the §4 check, or state in the thesis that stability is shown only as determinism at batch 1.
- **Effort:** S (needs GPU).

**A-8 · Major · M5, M8 · the end-to-end view was never scored on gold** (M-3)
- **Evidence:** `test_access.log` lines 3–4 have `"sets": ["test"]`. `repro.py:96-98` has no end-to-end gold
  row. `decision.md:132` declares a `{view: both, set: test and gold}` secondary endpoint.
- **Spec:** `mlops-prompt.md:204`.
- **Fix:** re-score the stored D4 outputs of the 250 gold pages against gold with `score`/`compare`. No
  inference is needed. Log it as a use of stored test outputs.
- **Effort:** S–M.

**A-9 · Major · B7 · nothing refuses a `purpose=usability` manifest** (M-4, X3)
- **Evidence:**
  - `x/x3_fake_smoke_part2.txt`: `GET /exports/eval-manifest?source=human` returns rows with `ref`,
    `purpose: "usability"` and the file name `…-human-usability.jsonl`.
  - `join_reference.py` refuses it only because refs are already present.
  - `viet-ocr-eval score` scores it with exit 0.
  - mlops code has no `purpose`/`usability` check (`evalcli.py:24-28`).
- **Spec:** `mlops-prompt.md:74-77,283`.
- **Fix:** `evalcli.score` (and any eval entry point) refuses a manifest whose name or any row carries
  `purpose=usability`, plus a test.
- **Effort:** S.

**A-10 · Major · activation · no `activate.py`; `is_active` is never read** (M-5)
- **Spec:** `mlops-prompt.md:64-65,173-174`.
- **Evidence:** every row is `is_active=false` while the adapted model serves live. `decision.md` gives no
  justification.
- **Fix:** a minimal `activate.py`, or document the deviation.
- **Effort:** S–M.

**A-32 · Major · B8 · pages of failed jobs are not exported as empty hypotheses; the whole export is refused** (B-2)
- **Evidence:** `b/b8_failed_page_export.txt`. A FakeRecognizer job failed at page 4 of 8. `source=machine`
  then returns `409 "5 page(s) have no machine output yet"` (`eval_manifest.py:78-80`), including when a
  complete document is added to the request.
- **Mitigation:** `mlops/testeval.py:313-324` exports only succeeded documents and fills `hyp=""` for every
  other page. **Gap:** `tools/d4_eval.py:158` aborts instead of scoring failed pages as empty.
- **Spec:** `mlops-addendum-25-09.md:168-171`; audit rule B8.
- **Fix:** an `include_failed=empty` option that emits `hyp:""` plus `failed:true`.
- **Effort:** S.

**A-44 · Major · M5 · the rehearsal gate accepts a rehearsal of different code; three gates can be bypassed** (FZ, M-6)
- **Evidence:** `falsifier/M5_probes.txt` and `M5_probes_test.py`; 3 probes, all show the gap.
  - `code_tree` hashes only `mlops/` and `evaluate_test.py` (`testeval.py:100`).
  - Rehearsals may run on modified training and backend trees (`check_clean(strict=not rehearsal)`, `:360`),
    and the started line records no training or backend commit (`:379`). Using the repo's own test fixture,
    a rehearsal at t_OLD/b_OLD unlocks an access at t_NEW/b_NEW.
  - `--rerun-reason " "` is accepted.
  - A report without `health.markup_chars` (protocol 1.0) reads as 0 (`.get(…, 0)`, `:179`), so the markup
    abort cannot fire. The protocol version is not enforced.
  - The clean check uses `--untracked-files=no`. The `VIET_OCR_EVAL` and `MASTER_DIR` env overrides are
    neither refused nor logged.
  - The gold hash is not compared against `decision.md`.
- **What held:**
  - The started line is committed before any test file is read.
  - An aborted run still counts as an access.
  - Outputs go to the gitignored `work/`.
  - A failed page is scored as empty and a missing page aborts.
  - The served name is checked before and after the end-to-end view and on every region.
  - Today's code tree no longer matches the rehearsal, so an access would be refused.
- **Spec:** `mlops-addendum-25-09.md:157-167` ("identical code path", "Clean tree").
- **Fix:**
  - Hash the training harness, recognizer, worker, skill and `decision.md` into `code_tree`.
  - Require clean trees, untracked files included, in rehearsal mode too.
  - Record all commits.
  - Reject whitespace-only reasons.
  - Require the `markup_chars` key and the protocol version.
  - Refuse the env overrides.
  - Check the gold sha.
- **Effort:** M.

**A-45 · Major · M4 · serving preflight does not hash the code that produces the text** (FZ)
- **Evidence:** `falsifier/M4_preflight_ignores_engine_code.txt` and `M4_unhashed_code.txt`.
  - `serve.sh` re-hashes the 23 recorded files. None of them is the executed Engine code: `training/ocrtrain/*.py`,
    `recognition_server.py`, `third_party/ERNIE`, paddleformers, libgomp.
  - The hashed `base_model/*.py` are HF files that the Paddle path never imports.
  - With `ocrtrain/infer.py` mutated, the preflight reports 0 mismatches.
  - The recorded commits are not compared at serve time.
  - `testeval.restore()` (`:432`) and `manage.py start-recognizer` launch without any preflight, and an
    already-running recognizer with the right name is kept as it is.
  - **Nothing diverges today:** training, backend and ERNIE match the promotion-time state.
- **Spec:** `mlops-addendum-25-09.md:62-70` (G.4, "hash every file … the remote-code `.py` files"). Under
  plan H, the Engine code is the equivalent.
- **Fix:** add Engine, recognizer and ERNIE/paddleformers tree hashes (or commits plus a clean check) to the
  row and the preflight, and route every launch through the preflight. This absorbs A-17.
- **Effort:** M.

**A-46 · Major · M2 · `promote.py --decision <file>` bypasses the declared check, and the record misstates its source** (FZ, M-11)
- **Evidence:** `falsifier/M2_decision_override.txt`.
  - With a fake file, the dev-only seed-14 replicate passes the "declared" step.
  - The record then stores the real `decision.md` blob (`promotion.py:218`), while parity uses the fake
    file's threshold (`:168`).
  - `weightcheck` has no relative-tolerance residual gate; delta statistics are information only. The Engine
    requires exact equality, which is stricter.
  - `rslora` is not cross-checked between `lora_config` and the run config (both are false today).
  - Serve and evaluate_test re-read the real `decision.md`, so only the registry can be polluted.
- **Spec:** `mlops-prompt.md:131-132`; `mlops-addendum-25-09.md:86-99`.
- **Fix:** remove the flag (absorbs A-15), cross-check `rslora`, and document that equality replaces the
  tolerance.
- **Effort:** S.

**A-33 · Major · X1 · the backend test suite drops the schema of whatever database it is given, and the README points it at the live ports** (B-3)
- **Evidence:** `b/x1_test_target_guard.txt`.
  - `tests/conftest.py:31` runs `DROP SCHEMA public CASCADE` on `TEST_DATABASE_URL`, and
    `test_worker.py:44` runs `flushdb()`.
  - README lines 250-251 suggest `127.0.0.1:5432/ocr_test` and `127.0.0.1:6379/15`. Those are the **live**
    Postgres (which holds the D4 revisions) and the live Valkey.
  - Without the variables, 56 of 97 tests are silently skipped, including the B2, B3, B5, B7 and B8 tests
    (`b/pytest_backend_without_db_env.txt`).
- **Why it matters:** one typo destroys the live data.
- **Fix:** refuse unless the database name ends in `_test`, the Valkey db is not 0, and the host/port is not
  the live one. Point the README at a separate test container.
- **Effort:** S.

A-9 also has a design conflict (B §4.1): the backend's RQ3 path computes edits per page by running
`viet-ocr-eval score` on the `source=human` manifest. A refusal inside the skill would break RQ3. So put the
refusal in the evaluation entry points (mlops `evalcli`, `evaluate_test`), and consider renaming the human
export (for example `/exports/usability-edits`).

### Minor

| ID | item | finding | evidence | fix / effort |
|---|---|---|---|---|
| A-11 (M-6) | M5 | The passing rehearsal is stale: code tree `53bfea…` vs HEAD `8454bb…` (7 commits), `decision.md` blob `0b686f04` vs `fc2e096c`. The code_tree hashes only mlops, and the gold path has never been exercised. | `m/rehearsal_code_tree.txt` | Hash harness, recognizer, worker and skill into code_tree; exercise gold in the rehearsal; rehearse again before any access. S–M |
| A-12 (M-7) | M5 | The documented two-version rehearsal refuses its second version (tracked `rehearsal.log` dirties the tree). | `m/sim_rehearsal_two_versions.txt` | Auto-commit `rehearsal.log`. S |
| A-13 (M-9) | M3 | The parity gate passes at <1% CER difference, while `decision.md` expects 0 pages changed. "1,323/1,323 regions identical" was in-process, not through HTTP. | `parity.py:109`; `training/work/analysis/bench.py:145` | Gate on `regions_changed == 0`; correct the wording. S |
| A-14 (M-10) | M2 | The served-adapter check (`promotion.py:150-161`) has no failing-case test. | `tests/test_promote_refusals.py:87` | Fake `/health` with `file_tensors_not_in_model > 0`. S |
| A-15 (M-11) | M2 | `--decision <path>` lets the declared check read any file, while the record stores the repo's blob. | `promote.py:24,26-27`; `promotion.py:218` | Remove the flag. S |
| A-16 (M-12, M-14) | M1, M5 | Registry rows predate the gates and lack the parity result and MLflow id. The backfilled log lines lack split hash, served name, weights hash and operator. | `m/registry_records.txt` | Document; add a supplementary note. S |
| A-17 (M-15) | M4 | `testeval.restore()` and the temporary promotion server start recognizers without `serve.preflight` re-hashing. | `testeval.py:420-433`; `promotion.py:278` | Route through preflight. S |
| A-18 (DT-9) | T6 | One duplicated-crop page (`091/page_27`) carries much of the dev insertion and whitespace reduction (base_ins 579 vs 372). | `dt/t6_dev_composition.txt` | CLI sensitivity compare without duplicated-crop pages. S |
| A-19 (DT-11) | T2 | The visual head is not adapted: the SigLIP pooling head is never instantiated and has no effect on output. Not documented. | `dt/t2_*.txt` | State it in the thesis. S |
| A-20 (DT-12) | D3 | 0 pages flagged "probably not Vietnamese"; 8 test / 2 gold CJK pages are tagged `non_latin`. `decision.md` does not say how they are handled. | `dt/d3_nonlatin_pages.txt` | State the handling. S |
| A-21 (DT-13, FZ) | D4 | Gold passes. After the first import, Claude generated a rare-word re-check list and 30 pages were re-verified from it. There is no second annotator. 91% of gold regions are accepted pseudo-GT, which was LLM-assisted upstream, so `decision.md`'s "typed by a person" overstates it. 11 pages were verified < 10 s apart. | `dt/d4_gold_provenance.txt` | Disclose. S |
| A-22 (DT-10) | D4 | `decision.md` "earliest verification per page" does not match the code, which keeps the latest per annotator. | `gold_review.py:207-216` | Thesis wording. S |
| A-23 (DT-14, DT-15) | D5 | exp_lines records a stale gold hash; split id lists are not in git. | `dt/d5_split_hashes.txt` | Commit id-only lists. S |
| A-24 (DT-7, DT-8) | T1 | Retention keeps unevaluated steps; `train_metrics.jsonl` lacks DER. | `dt/t1_run_contract.txt` | Document. S |
| A-25 (DT-16, FZ) | G3 | The evaluation path reuses the stored order. FZ: it equals `order_regions` on every dev, test and gold page. The docstring overclaims. The sha pin detects training-copy drift only in the monorepo layout, and no training test pins the file. | `dt/reading_order.txt` | Fix the docstring. S |
| A-26 (G4) | G4 | The backend stores human text "exactly as submitted" (`review.py:9-10,108-111`), with no NFC. The eval manifest copies the human `ref` as stored. Scores are unaffected (the skill NFCs, `normalize.py:166`). An NFD resubmission of identical text would create a spurious revision (`review.py:103`). | `g/g4_nfc_grep.txt` | NFC at the POST boundary. S |
| A-27 (G6) | G6 | The Paddle training and serving env has no committed lock: `requirements-train.txt` has 33 of 38 packages unpinned. A freeze exists only in the repro tarball (`venv-train.txt`, `venv-layout.txt`) and as a hash in `run.json`. The current freeze hash `d4a1b488…` equals all 14 runs. | `g/g6_pins.txt`, `g/g6_venv_train_freeze.txt` | Commit the freezes. S |
| A-28 (G6, M-18, F §6) | G6 | The live stack runs on public defaults: `API_TOKEN=dev-token`, Postgres `ocr/ocr`, Grafana `admin`. Loopback only. | `f/G6-live-api-default-token.txt`; `docker-compose.yml:13,23,65` | Set real values in `.env`. S |
| A-29 | C | The RQ3 instrument is the standalone study kit (`training/work/study`, SUS inside the HTML), not the frontend instrumentation the frontend spec names. `study.py:159 paired_ci` bootstraps CIs outside viet-ocr-eval (edit counts do come from the CLI, `:198-199`). | `training/work/study/README.md`, `study.py` | Record the design change; note the participant-level CI. S |
| A-30 (F-1…F-7) | F | The dev server overwrites `dist/`; `session_id` is per page load, not per tab; `save` is emitted on unchanged text; toolchain changed (Vitest, TS 7, utoopack); a backend outage shows "no active model"; MSW ships in the prod bundle; `npm ls` gives ELSPROBLEMS. | `f/*` | See F report. S each |
| A-31 (M-17, M-19, M-20) | M | MLflow is local sqlite, not in compose; bench JSON has no engine field; the addendum's grep regex is a prefix match. | `m/mlflow_checks.txt` | Document. S |

| A-47 (FZ, M-9) | M3 | "Never share the GPU" is false. During fixed-crop the layout server :8091 stays up; the only harness guard is `min_free_vram_gb: 24`. During end-to-end, recognizers start on both worker ports, :8090 and :8092. Outputs are unaffected (batch-1 greedy). The parity gate passes with a changed region (real CLI run), which covers A-13. | `falsifier/M3_*.txt` | Stop layout during fixed-crop or document it; gate on `regions_changed == 0`. S |
| A-48 (FZ) | B4 | The md export (`exports.py:52 blocks_to_markdown`) is a second text path: it drops headers, keeps footnotes, keeps `**`/`<br>`, and skips NFC. It is documented as presentation-only. The `page-v1` keep set is not pinned: dropping captions and footnotes from it still passes 11/11 tests, and eval-manifest re-derives `hyp` with the current code under the stored name (see A-36). | `falsifier/B4_*.txt` | Pin both policies' label sets in tests; hash `plaintext.py` into `plaintext_stats`. S |
| A-34 (B-4) | skill | `score` treats a missing `ref` as empty: an unjoined machine manifest exits 0 with CER macro 0.00 and 1,431 insertions. | `b/b8_manifest_score_unchanged.txt`; `evaluate.py:_text` | Fail on rows without `ref`. S |
| A-35 (B-5) | B4 | Markup stripping in `to_plaintext()` is a 4th source of the fixed-crop vs end-to-end gap. It strips `#`, `**…**`, `__…__` and HTML, but keeps LaTeX. The code is symmetric, but the effect is not: only base emits markup. It damages some genuine text (`________`→`__`, footnote `**`), though it would change 0/1,520 dev and 59/19,780 train references. | `b/b4_*.txt` | Report `markup_chars_removed` per model with D4; add it to the gap description. S |
| A-36 (B-6) | B4 | The manifest re-derives `hyp` from `blocks` (`eval_manifest.py:93`), with no code hash in `plaintext_stats`. | — | Assert `hyp == rev0.text` when the policy matches. S |
| A-37 (B-7) | B12 | A job on an already-processed document "succeeds" and returns the earlier output, even under a different `text_policy` (`pipeline.py:159-161`). | `b/b12_rerun_same_document.txt` | Refuse (409) a policy mismatch. S |
| A-38 (B-9) | B5 | Rev 0 can be deleted and re-inserted; the trigger only covers UPDATE (migration 0005). | `b/b5_rev0_immutable.txt` | Add a BEFORE DELETE trigger or REVOKE DELETE. S |
| A-39 (B-10) | B3 | The served-model check compares the name only, not the weight or adapter hashes that `/health` exposes. mlops `serve_on` does compare them. | `pipeline.py:132-135` | Compare hashes once per job. S |
| A-40 (B-11) | B10 | Effective decode parameters are not logged per job, and the server does not echo them. Sampling itself is explicit (`http_clients.py:54`) and mismatches get 422 (`recognition_server.py:171-176`). | `b/b10_sampling_params.txt` | Log and echo. S |
| A-41 (B-12) | G1 | `backend/tests/test_no_metric_code.py` misses `nltk.metrics` and prefix names such as `compute_cer_micro(`. No such code exists. | `b/g1_no_metric_pattern_check.txt` | Widen the patterns. S |
| A-42 (B-13) | B9 | `events_exported=true` is taken on trust; refused exports still write `export` audit rows. | `b/b9_hard_delete.txt` | S |
| A-43 (B-14) | B6 | Bench reports were produced from dirty trees (19, 1 and 4 dirty files). p95 warm service is 12.756 s (2 servers) and 19.53 s (3 servers), against a < 12 s target. | `b/b6_bench_reports_structure.txt` | Rerun the bench from a clean tree, or disclose. S |

---

## 3. Coverage matrix

Status legend: PASS / FAIL / NOT IMPLEMENTED / NOT VERIFIED. "(code)" means code reading only, where execution was
possible but not done. FZ = falsifier outcome.

| item | status | finding | evidence |
|---|---|---|---|
| **G1** | **FAIL** (FZ broke) | A-5: `runaway.py` computes CER ratios and CIs in-process. A-41: all three guards can be evaded; the frontend has no guard. `eda/notebooks/eda_lib.py` (untracked) uses difflib for alignment only. | `g/g1_grep.txt`, `g/g1_broader.txt`, `m/g1_grep.txt`, `f/G1-frontend-grep.txt` |
| G2 | FAIL | A-4, A-5 | `dt/skill_diff_status.txt`, `dt/selftest_1.2.txt` (selftest OK), `dt/callsites.txt` |
| **G3** | PASS (FZ held) | A-25 | `g/g3_diff.txt` (identical sha256 `bfd4775a…`), `b/g3_reading_order_callsites.txt`, `dt/reading_order.txt` |
| G4 | FAIL (partial) | A-26. Editor, `to_plaintext()` and scorer are NFC; the backend write and the human ref export are not. | `g/g4_nfc_grep.txt`, `b/g4_nfd_correction.txt`, `f/` G4 row |
| G5 | PASS (code + records) | `decode.json` → `infer.Engine` in both harness and recognition server. The worker sends `decode_cfg`; the server returns 422 on mismatch; bench records `decode_cfg`. vLLM N/A (plan H). | `g/g5_decode_grep.txt`, `dt/decode_settings.txt` |
| G6 | FAIL (Minor) | A-27, A-28. uv/npm locks are committed for backend, frontend and mlops. | `g/g6_*.txt`, `m/g6_secrets_lock.txt`, `f/G6-frontend.txt` |
| **D1** | PASS (FZ held: also data-lines, data-mixed, 14 `erniekit_train.jsonl`, and page-image hashes across splits) | – | `dt/d1_verify.txt`, `dt/d1_verify_lines_mixed.txt`, `m/verify_splits_scratch.txt` |
| **D2** | PASS (FZ held: independent counts from raw `final/` equal the manifests, dev 1520/14044, test 3978/37422, gold 250/2229) | – | `prepare_data.py:462-478,493-498,505-507`; `dt/d2_unfiltered_check.txt` |
| D3 | PASS (0 flagged) | A-20 | `dt/d3_nonlatin_pages.txt` |
| **D4** | PASS (FZ held) | A-21, A-22 | `dt/d4_gold_provenance.txt`, `dt/d4_transcript_scan.txt` |
| D5 | PASS | A-23 | `dt/d5_split_hashes.txt`, `m/corpus_spotcheck.txt` |
| T1 | FAIL | A-6 (layout and SHA256SUMS pass), A-24 | `dt/t1_run_contract.txt`, `dt/t1_source_hash_vs_git.txt` |
| T2 | PASS | A-19. 290 modules (126 for `exp_lm_only`), same `names_sha256`; the visual head is not included. | `dt/t2_*.txt` |
| **T3** | PASS (FZ held) | Selection dev-only; see A-1 for test exposure. | `dt/t3_testid_scan.txt` |
| T4 | PASS | No duplicated steps or eval files; incident recorded. | `dt/t4_duplicates.txt`, `mlops/incidents.yaml` |
| **T5** | **FAIL** | A-2 (Blocker by rule) | `dt/t5/*` |
| T6 | PASS | A-18 | `dt/t6_dev_composition.txt` |
| T7 | FAIL | A-7 (claim unsupported) | `dt/t7_baseline_gate.txt` |
| B1 | PASS | – | `b/b1_api_no_ml.txt`, `test_import_boundary.py` 2/2 |
| B2 | PASS | 20 concurrent POSTs → 1×201, 19×200, 1 job, 1 outbox row | `b/b2_idempotency_http_concurrency.txt` |
| B3 | PASS | A-39. Runtime: `ModelMismatch`, not retryable. | `x/x3_b3_served_model_mismatch.txt`; test passes |
| **B4** | FAIL (Minor, FZ broke) | A-48, A-35, A-36 | `b/b4_to_plaintext_probe.txt`; `test_plaintext.py` 11/11 |
| B5 | PASS | A-38 | `b/b5_rev0_immutable.txt` |
| B6 | PASS (code + report keys) | A-43 | `bench.py:56-81,162-200,346-362`; `b/b6_bench_reports_structure.txt` |
| **B7** | **FAIL** | A-9 | `b/b7_usability_paths.txt`, `x/x3_fake_smoke_part2.txt` |
| **B8** | **FAIL** | A-32, A-34 | `b/b8_failed_page_export.txt`, `b/b8_manifest_score_unchanged.txt` |
| B9 | PASS | A-42 | `b/b9_hard_delete.txt` |
| B10 | FAIL (Minor) | A-40 | `b/b10_sampling_params.txt` |
| B11 | PASS | – | `telemetry.py:19-22`, `ops/prometheus/rules.yml:9-10` |
| B12 | PASS (code) | A-37 | `mlops/testeval.py:297`, `tools/d4_eval.py:129` |
| F1–F7 | PASS | A-30 | `f/*` (Vitest 150/150, Playwright 3/3 also with the backend unreachable, lint and tsc clean) |
| **M1** | **FAIL** (by rule) | A-3. All other elements present (`m/` §3 table); registration post hoc (A-1). | `decision.md:98-171` |
| **M2** | **FAIL** (FZ broke) | A-46, A-14. 3a (merge) N/A: no merge. | `m/pytest_mlops.txt` (weightcheck ×6, refusals ×4) |
| **M3** | FAIL (Minor, FZ broke) | A-47. Calibration N/A (justified); recorded parity 0 changed. | `m/registry_records.txt` |
| **M4** | **FAIL** (FZ broke) | A-45. The recorded files re-hash with 0 mismatches, but the Engine code is not hashed. | `m/serve_hash_reverify.txt` |
| **M5** | **FAIL** (FZ broke); live rehearsal NOT VERIFIED | A-44, A-11, A-12 | `m/m5_code_trace.txt`, `m/pytest_mlops.txt`, `m/sim_rehearsal_two_versions.txt` |
| M6 | PASS | The fallback is the only path. | `testeval.py:189-211,254-340`; `rehearsal.log` |
| M7 | PASS | No `=` in keys; `not_recorded` tags; LR was measured, so nothing reconstructed. | `m/mlflow_checks.txt` |
| M8 | PASS (code + existing tarball) | A-4 (a rebuild now would mislabel the skill) | `m/repro_tarball_listing.txt` |
| X1 | FAIL | Training 12/13 (`test_no_metric_code` fails, A-5); backend 97/97 (A-33); frontend 150/150 + 3/3; mlops 42 passed, 1 skipped, 3 deselected (they parse test reports); skill selftest OK | `dt/pytest_training.txt`, `b/pytest_backend.txt`, `f/X1-*.txt`, `m/pytest_mlops.txt` |
| X2 | PASS | Clean clone, project `audit-x`: api and worker healthy, schema 0012 (Docker layer cache used) | `x/x2_*.txt` |
| X3 | PASS | 5 dev pages: FakeRecognizer, then the real base model (isolated servers). Upload → queue → edit → export → eval-manifest → join → `score` (base on these pages: 0 runaway, 0 markup). | `x/x3_*.txt`, `x/report_x3_*.json` |
| X4 | NOT VERIFIED | Owner decision: a live rehearsal stops the live recognizers, writes to the live DB and appends to the tracked `rehearsal.log`. The existing pass is stale (A-11). | `m/rehearsal_code_tree.txt` |

---

## 4. Spec contradictions

1. **Serving engine.** `mlops-prompt.md` (merge, conversion, vLLM, 3-way gate) and addendum §G ("vLLM is
   already the serving engine") vs backend decision D1 (no merge) and `decision.md` plan H (Paddle runtime
   adapter everywhere). `decision.md` resolves it with a justification. As a result, M2's 3a and M3's
   calibration are N/A (§3).
2. **Pre-registration timing.** Addendum C requires `decision.md` before the first access, and
   `mlops-prompt.md:37-39` assumes the choice "is recorded in a committed decision.md". The file dates from
   25/09, after four accesses (A-1).
3. **Markup abort.** `mlops-prompt.md:207-209,273` (any markup aborts; never cut) vs `decision.md:162-167`
   (base exempt, set after its count was known). A-2.
4. **Fallback.** Addendum H sets a 27/09 12:00 deadline; `decision.md` makes the fallback the plan of record,
   with no deadline. A-3.
5. **Baseline gate.** `training-prompt.md` §E (3-seed gate, sd < 10% of mean) vs skill 1.2
   `references/protocol.md` §4 (seeds do not test this under greedy decoding; batch-order check). A-7.
6. **Seed replicate.** `mlops-prompt.md:178,210` (run on test, compare base vs replicate) vs addendum
   ("reported descriptively") vs `decision.md` (dev only, `test: false`).
7. **Page furniture in the reference.** `frontend-prompt.md:73-75` and delta §3 say headers and page numbers
   are excluded "because the reference text … does not contain them". VieBookRead references do contain them:
   dev150 has page numbers on 130/150 pages and running heads on 42 (DT §3 T6), and the backend migration plan
   says so too (`migration-plan.md:175`). So evaluation uses `page-v1` (D5) while the product default and the
   reviewer guideline use `body-v1`. Human-corrected pages will not look like references.
8. **Crop source.** `training-prompt.md` constraint 2 and §A (Azure line boxes, projected labels) and
   `mlops-prompt.md:41-42,193` ("Azure-box region crops") vs the implementation. Paragraph crops and labels come
   from `final` region polygons within 10 px of Azure paragraphs (`prepare_data.py:199-205`). Semi-global
   alignment is used only for the line build.
9. **Skill version.** `mlops-prompt.md:49` says protocol 1.1; the working tree holds uncommitted 1.2, which
   still stamps 1.1 (A-4).
10. **Protocol §1 vs `.gitignore`.** The protocol says `test.jsonl` and `gold.jsonl` are committed;
    `/training/data/` is gitignored (A-23).
11. **RQ3 instrument.** `frontend-prompt.md:115-151` (RQ3 from the review-screen events; SUS on paper; no
    questionnaire) vs `training/work/study` (standalone HTML kit, SUS inside, base-vs-adapted blind design).
    A-29.
12. **Facts that drifted in the specs.**
    - "One 24 GB GPU" (the machine has a 32 GB RTX 5090).
    - "Six runs" (8 training runs).
    - "MLflow in docker-compose" (local sqlite).
    - "Training finished by 21/09" (dev-only runs on 22–23/09).
    - "134 precomposed vowels" (132 plus đ/Đ).

13. **Usability refusal vs RQ3.** `mlops-prompt.md:74-77,283` says refuse and never score any
    `purpose=usability` manifest. The backend's RQ3 design (`usability.py:4-5`, `eval_manifest.py:12-15`)
    scores exactly that manifest with `viet-ocr-eval score` to count edits.
14. **Which policy the gap refers to.** Addendum C ("Describing the gap") names `to_plaintext()` policy
    `body-v1`. Every evaluation (D4, mlops end-to-end, bench) uses `page-v1`, while the product default and the
    review UI use `body-v1`.
15. **Failed pages.** The backend README and `eval_manifest.py` treat a page without output as an error and
    refuse. Addendum C and audit rule B8 say to score it as empty. mlops reconciles the two; `d4_eval.py` does
    not.
16. **B10's source.** B10's requirement lives in addendum §G, the vLLM contract, which plan H drops. It is
    applied here to the worker → recognition-server request.

---

## 5. Dev confound results (T5, T6)

`viet-ocr-eval` working tree 1.2 (stamped "protocol 1.1"). Base = baseline `manifest_seed13.jsonl` restricted to
the 150 dev pages; final = `exp_lr2e4/eval/step-003000/manifest.jsonl`. Evidence is in `dt/t5/`
(`compare_base_vs_lr2e4_s3000_dev150.md`, `reduction_shares_extract.txt`).

| metric | base % | adapted % | rel. change | 95% CI |
|---|---|---|---|---|
| cer_micro | 3.78 | 1.62 | −57.2% | [−62.1, −52.2] |
| der | 9.12 | 2.39 | −73.8% | [−77.9, −70.0] |
| ter | 9.89 | 2.95 | −70.2% | [−75.1, −65.7] |
| wer_micro | 14.46 | 6.31 | −56.3% | [−59.6, −52.9] |
| wser | 2.38 | 1.59 | −33.2% | [−42.7, −20.3] |

**Reduction shares** (4,217 character edits removed, 150 paired pages):

| category | edits | share |
|---|---|---|
| **tone + letter diacritic** | 2,939 | **69.7%**, CI [59.35, 78.02], `p_diacritic_largest` 1.0 (1,000 valid resamples) |
| tone mark | 2,019 | 47.9% |
| letter diacritic | 920 | 21.8% |
| base letter | 431 | 10.2% |
| insertion | 466 | 11.1% |
| deletion | 52 | 1.2% |
| whitespace | 329 | 7.8% |
| runaway pages (capped) | 0 | 0.0% |

**Run health.**

| run | runaway | empty | markup |
|---|---|---|---|
| base, dev150 | 0 | 0 | **14 characters on 3 pages** (A-2) |
| adapted, dev150 | 0 | 0 | 0 |
| base, full dev (stored 1.0 report) | 8 pages (0.53%) | – | – |

**Framing check.** Insertion, whitespace and runaway together (18.9%) remove fewer edits than diacritics
(69.7%, CI 59.4–78.0). **No Major framing flag on dev.**

**T6.**
- Dev crops are exactly the `final` regions, so a hypothesis cannot contain a region the reference lacks.
  All 1,520 of 1,520 dev references equal their region texts joined in the stored order.
- The references **do** contain furniture: page numbers on 130/150 pages, running heads on 42, footnotes on 22.
- Neither model emits empty regions.
- On page-number regions, adapted matches exactly on 116 of 130 and base on 65 of 130. Adaptation learned the
  label format for furniture; it did not learn to drop it.
- Part of the insertion row comes from the duplicated-crop page `091/page_27` (A-18).

---

## 6. What the thesis can claim (section C)

`main.pdf` was not provided. The targets below are those that `decision.md`, `frontend-prompt.md` and
`mlops-prompt.md` attribute to the proposal. §4.2 and §5.1 could not be checked: NOT VERIFIED.

| promised measurement (source quoting the proposal) | producible now? | from | status / caveat |
|---|---|---|---|
| **Target 1:** ≥ 20% relative CER reduction, adapted vs base (`decision.md:124-125`) | yes, already produced | `viet-ocr-eval compare` of `finals/test__base…` vs `test__…exp_lr2e4` (fixed-crop, test and gold); `backend/reports/eval/d4/compare_d4.json` (end-to-end, test) | Post hoc (A-1). End-to-end on gold is missing (A-8). Base markup is waived (A-2). |
| **Target 2:** the reduction is mostly diacritics (`decision.md:133-139`) | yes | `compare` `reduction_shares` (skill ≥ 1.1); `training/work/analysis/protocol_1.1` | Reading chosen post hoc. Met on test; **not met on gold** under the chosen rule. Dev: 69.7%, `p_largest` 1.0 (§5). |
| CER / WER(syllable) / DER / TER / WSER with paired bootstrap CIs (Month 3 statistical comparisons) | yes | `viet-ocr-eval compare` (1,000 paired page resamples, seed 13) | Skill label 1.1 vs 1.2 (A-4). `runaway.md` numbers bypass the CLI (A-5). |
| Stratified results (era, degradation) and filter rejection rates by era (`training-prompt.md:115-125`) | yes | finals stratified table (ledger event 11); `data_manifest.json` filter stats | – |
| Baseline stability (`training-prompt.md` §E) | no | seed gate only | Unsupported (A-7). Needs the batch-order check (~50 min GPU) or a wording change. |
| Fixed-crop vs end-to-end gap and its causes (`mlops-prompt.md:213-215`, addendum C) | partly | `backend/reports/eval/d4/layout_effect/` | Add markup stripping as a cause (A-35); `page-v1` vs `body-v1` wording (§4.14). |
| **RQ3:** time per page and edits per page from real proofreading (`frontend-prompt.md:17-19,115-151`) | code yes, data **no** | (a) frontend events → `/exports/usability.csv` plus `eval-manifest?source=human` → `score`; (b) `training/work/study/study.py analyze` | The study has not been run. There are two instruments (A-29), and path (a) conflicts with the usability refusal (§4.13). |
| SUS | code yes (study kit), data no | study kit HTML; the frontend spec says paper | – |
| Monitoring dashboard (`frontend-prompt.md:48-50`) | yes | Grafana dashboard (mlops step 5); the frontend Monitoring link opens it | – |
| Throughput and latency (pages/hour, p95 warm service time, cold start) | yes | `backend/bench.py` reports, `reports/bench_comparison.md` | p95 12.756 s (A) / 19.53 s (B), against a < 12 s target. Built from dirty trees (A-43). |
| Training cost (GPU hours excluding downtime, peak VRAM) | partly | MLflow backfill, `incidents.yaml` | Peak training VRAM is `not_recorded` (M-17). |
| Runaway and empty rate | yes | report `health` | Serving proxy `serving_runaway_rate` is kept separate (B11). |
| Proposal §4.2, §5.1 and RQ1–RQ2 wording | NOT VERIFIED | – | `main.pdf` not provided. |

---

## 7. Fix plan (before 27/09 12:00)

Roughly two working days, one fix at a time, each approved first. **No step makes a new test access.** Steps
marked *uses stored test outputs* re-score outputs that already exist; no model runs. They still belong in
`test_access.log` as backfilled uses.

| # | when | finding | action | effort |
|---|---|---|---|---|
| 1 | 25/09 | A-33 | Guard the backend test target (`_test` database, Valkey db ≠ 0, non-live port); fix the README. Protects live data first. | S |
| 2 | 25/09 | A-1 | Hand-append `backfilled` lines for gate-6 and the D4 dry run (evidence hashes, reason) and commit. Note the unscored touches. Correct `REPRODUCE.md` ("twice per model"). | S |
| 3 | 25/09 | A-3 | Record the fallback-deadline waiver in `REPRODUCE.md` (not in the frozen `decision.md`). | S |
| 4 | 25/09 | A-2 | Owner decides (a) waiver plus a bound printed beside every base number, or (b) one converter for both models plus a CPU re-score (*uses stored test outputs* for the test tables). | S / M |
| 5 | 25/09 | A-4 | Bump the skill stamp to 1.2, commit the skill, record the tree sha256. | S |
| 6 | 26/09 | A-9 | Refuse `purpose=usability` in mlops `evalcli`/`evaluate_test` (not in the skill, to keep RQ3 working); add a test. | S |
| 7 | 26/09 | A-5 | Re-derive the `runaway.md` numbers through the CLI (*uses stored test outputs*), or drop them as a thesis source. Make the training guard test pass. | M |
| 8 | 26/09 | A-6 | Reconstruct the 17/09 `ocrtrain/config.py`, confirm source hash `2ea991a0…`, tag it, map it in `REPRODUCE.md`. | M |
| 9 | 26/09 | A-8 | End-to-end gold: re-score the stored D4 outputs of the 250 gold pages (*uses stored test outputs*). | S–M |
| 10 | 26/09 | A-7 | Batch-order repeatability on dev150 (~50 min GPU, dev only, in a window when the live recognizers can be stopped), or reword the stability claim. | S |
| 11 | 27/09 a.m. | A-46, A-32, A-10 | Remove `--decision`; `include_failed=empty` export option; `activate.py` or a documented deviation. | S each |
| 11b | only before a further access | A-44, A-45, A-11, A-12 | Harden the rehearsal gate and the serving preflight, then re-run the rehearsal for both versions. | M |
| 12 | after 27/09 | Minors A-11…A-43 | Thesis wording items first (A-19, A-20, A-21, A-22, A-29, A-35, A-43), then code. | S each |

**Does it fit before 27/09 12:00?** Yes. Steps 1–9 fit on 25–26/09. If steps 7, 8 or 10 slip, the applicable
fallback is `decision.md`'s plan of record (plan H), which is already the running path. The slipped items go
into the thesis as disclosed limitations (code provenance by source hash only; stability shown only as
determinism at batch 1; `runaway.md` not used). **Nothing in this plan requires or justifies another test access.**
If, after these fixes, you still want a logged run under `evaluate_test.py`, first fix A-11 and A-12, re-run the
rehearsal for both versions on the current code tree, and pass a `--rerun-reason`. It would be the third access
per model.
