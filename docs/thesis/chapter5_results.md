# Chapter 5 — Results and Discussion (draft, 02/10/2026)

> **Draft status.** All numbers are copied from the files named in each section. Every error rate comes from the
> `viet-ocr-eval` command-line tool; none is computed by hand. §5.4.4 (usability) is a placeholder until the user
> study has run. Sentences marked **[CHECK]** need the author's decision before submission.

## 5.1 Evaluation setup and what the numbers can claim

**Models.** *Base* is the unadapted PaddleOCR-VL-1.6. *Adapted* is the same model with the LoRA adapter of run
`exp_lr2e4`, step 3000. The adapter is applied at runtime and is never merged (§5.4.3 explains why). The adapter was
selected on the development split only.

**Two views of quality.**
- The **fixed-crop view** feeds both models the ground-truth region crops of VieBookRead through the training harness.
- The **end-to-end view** runs the deployed platform on the page images: PP-DocLayoutV3 finds the layout, the
  recognition server reads each region, and the `page-v1` text policy assembles the page.

The second view is what a user receives. The first isolates recognition from layout.

**Data.**
- The locked test split has 3,978 pages from 23 books, with 5,116,736 reference characters. Its references are
  VieBookRead's distantly supervised page texts ("pseudo labels").
- A gold subset of 250 test pages, spread over all 23 books, was hand-verified against the page images.
- Two books outside VieBookRead were checked separately (§5.2.3).

**Metrics.** CER and WER are computed on syllables. DER counts tone and letter-diacritic substitutions over
diacritic-bearing graphemes; TER counts tone substitutions only. WSER counts whitespace errors over reference spaces.
Micro averages are primary.

**Intervals.** Every comparison is paired by page, with 1,000 bootstrap resamples and seed 13. Two intervals are
reported:
- one resamples **pages** (the protocol default);
- one resamples **whole books** (`compare --cluster book`, added in protocol 1.3).

Pages of one book share typeface, paper and scan, so they are not independent. The book interval is the honest one for
a claim about books the model has not seen. It is 2–3× wider.

**Disclosure (must appear in the thesis).**
- The test split was scored twice per model (fixed-crop 17–19/09, end-to-end 24/09) before the primary endpoint was
  written down in `decision.md` (25/09).
- The test results are therefore **post hoc**: the analysis was not pre-registered, even though model selection used
  only the development split.
- The degradation strata (§5.3.3) and the book-level intervals were defined on 01/10, after the overall results were
  known. They are **exploratory**.

Sources: `docs/SO_LIEU_2026-10-01.md`, `training/work/analysis/protocol_1.1/SUMMARY.md`,
`training/work/analysis/numbers_1001/SUMMARY.md`, `backend/reports/eval/d4/`, `mlops/docs/REPRODUCE.md`.

## 5.2 RQ1 — Does adaptation lower CER?

### 5.2.1 Locked test split and gold subset

**Table 5.1** Base vs adapted. Rates in %. The relative change has a 95% CI from page resampling, then one from book
resampling.

| view | set | metric | base | adapted | change [page CI] | [book CI] |
|---|---|---|---|---|---|---|
| end-to-end | test (3,978 p.) | **CER** | 3.32 | 1.68 | **−49.4%** [−53.1, −45.5] | [−59.8, −38.2] |
| | | WER | 11.58 | 5.15 | −55.6% [−57.5, −53.3] | [−62.7, −47.8] |
| | | DER | 6.84 | 1.03 | −84.9% [−85.6, −84.3] | [−87.4, −80.5] |
| | | TER | 7.21 | 1.20 | −83.4% [−84.2, −82.6] | [−86.4, −77.8] |
| | | WSER | 2.37 | 2.12 | −10.5% [−21.4, +1.0] | [−29.9, +9.3] |
| end-to-end | gold (250 p.) | **CER** | 3.11 | 1.37 | **−55.8%** [−59.9, −51.6] | [−62.7, −48.7] |
| | | WER | 12.13 | 5.08 | −58.2% [−60.8, −55.1] | [−63.6, −52.7] |
| | | DER | 7.00 | 1.15 | −83.5% [−86.1, −80.6] | [−87.4, −78.9] |
| | | WSER | 2.30 | 1.84 | −19.8% [−26.3, −12.7] | [−29.2, −9.9] |
| fixed-crop | test | **CER** | 3.38 | 1.78 | **−47.3%** [−52.4, −42.0] | [−62.8, −31.8] |
| | | WER | 11.62 | 5.02 | −56.8% [−58.7, −54.5] | [−63.1, −49.6] |
| | | DER | 6.95 | 1.03 | −85.1% [−85.8, −84.5] | [−87.7, −80.8] |
| fixed-crop | gold | **CER** | 4.51 | 2.13 | **−52.7%** [−68.6, −38.0] | [−72.7, −34.6] |

**Answer to RQ1.**
- **Yes.** Adaptation lowers CER by about half: −47% to −56% across both views and both reference sets.
- **The 20% target is met in every cell, even with book resampling.** The least favourable upper bound is −31.8%
  (fixed-crop test, book CI).
- The gain holds against hand-verified references (gold). So it is not an artefact of learning the conventions of the
  pseudo labels.

### 5.2.2 Whitespace

WSER does not improve significantly on the test split: both intervals include zero in both views. It does improve on
gold (end-to-end −19.8%). The adapted model reads letters and marks better, but word boundaries are not reliably better.

### 5.2.3 Books outside VieBookRead (generalisation check)

Two books absent from VieBookRead were run through the platform and scored against pages typed from scratch by the
author (one typist; a neutral typo check was applied).

| book | condition | pages typed | base CER | adapted CER | change [95% CI] |
|---|---|---|---|---|---|
| *Việt Nam Pháp thuộc sử* (1961) | clean print | 5 (6,995 chars) | 1.49 | 0.56 | −62.5% [−73.4, −53.9] |
| *Einstein* (1972) | yellowed paper, faded ink | 3 (3,944 chars) | 2.18* | 0.86* | −60.5% [−79.5, −10.5] |

\* Quote-free sensitivity score: the typist used straight quotes where the print has « ».

- On the degraded book, the adapted CER doubles relative to the clean book, but it stays about 60% below base.
- These checks are small (3–5 pages each). They support the *direction* of RQ1 on unseen books, not a precise size.

## 5.3 RQ2 — How are the errors distributed?

### 5.3.1 Where the reduction comes from

**Table 5.2** Share of the removed character edits (base − adapted, paired pages) by error category. Runaway pages are
capped and counted as their own category, so the shares sum to 100%.

| | e2e test | e2e gold | fixed test | fixed gold |
|---|---|---|---|---|
| edits removed | 83,921 | 5,487 | 81,733 | 7,518 |
| **tone + letter diacritic** | **79.6%** | **75.7%** | **83.2%** | **55.3%** |
| — tone marks | 56.1% | 51.4% | 58.7% | 38.0% |
| — letter diacritics | 23.5% | 24.3% | 24.5% | 17.3% |
| base letters | 8.6% | 10.6% | 9.1% | 8.1% |
| insertions | 6.3% | 6.3% | 1.6% | 24.8% |
| deletions | 1.1% | 2.0% | 2.2% | 1.9% |
| whitespace | 2.9% | 5.5% | 2.8% | 9.9% |
| runaway pages | 1.6% | 0.0% | 1.1% | 0.0% |
| diacritic share, 95% CI (book) | [70.9, 90.3] | [72.0, 80.4] | [75.4, 91.7] | [35.9, 78.2] |
| P(diacritics are the largest category) | 100% | 100% | 100% | 92.9% |

**Answer to target 2.**
- On the test split, three quarters or more of the improvement is in tone marks and letter diacritics. Diacritics are
  the largest category in every resample.
- The same holds on gold in the end-to-end view.
- The exception is fixed-crop gold (55%, largest in 93% of resamples). It is driven by a single page (`003/page_25`) where
  the base model looped to the token cap. Removing pages whose output exceeds twice the reference (a post hoc rule)
  gives 70.9% [63.4, 77.5].
- Because the target was defined after the results were known, this answer is **exploratory**.

### 5.3.2 What errors remain

After adaptation, the remaining errors are mostly **deletions, whitespace and insertions**; tone and letter-diacritic
errors almost disappear. In the end-to-end test split, middle degradation stratum, the adapted model leaves:
- 2,943 tone errors and 988 letter-diacritic errors;
- against 14,702 deletions and 11,436 whitespace errors.

The deletions are dominated by layout: tables, formulas and figures are excluded by design, and reading order matters.
Improving them is a layout problem, not a recognition problem.

### 5.3.3 Degradation strata (exploratory)

**Index.** The index uses the page image only:
- *grey paper* = 1 − share of near-white pixels;
- *faint ink* = 5th percentile grey level.

The two are combined as a percentile-rank score. Tertile cut points come from 2,000 training pages, so the test pages
are not used to tune them.

**Table 5.3** End-to-end view, test split.

| degradation | pages | books | base CER | adapted CER | change [book CI] | diacritic share |
|---|---|---|---|---|---|---|
| low | 1,201 | 13 | 2.90 | 1.30 | −55.2% [−66.4, −47.2] | 80.7% |
| mid | 1,483 | 22 | 4.08 | 2.50 | −38.6% [−53.0, −24.8] | 87.0% |
| high | 1,294 | 16 | 2.98 | 1.26 | −57.9% [−67.1, −38.3] | 72.9% |

**Reading.**
- The gain is present in **every stratum**, and tone marks are the largest removed category in each.
- The image index does **not** track OCR difficulty: the "mid" stratum is the hardest for both models, not "high". It
  mainly separates raw grey scans from whitened scans.
- In the fixed-crop view, the mid stratum's book interval reaches −16.7%, the only interval in this chapter that does not
  clear −20%.
- So this chapter does **not** claim that adaptation helps *more* on degraded pages. The evidence on genuinely degraded
  print is the *Einstein* book (§5.2.3), which is small.

Two other strata are recorded with the data:
- Era: the gain is −56% to −62% for every dated period, and −17.7% for pages of unknown date.
- Azure-confidence difficulty: the gain is −60% to −63%, except −18.8% on pages Azure read confidently, where the pseudo
  labels are closest to conventional OCR.

### 5.3.4 Run health

| | e2e test base / adapted | fixed test base / adapted |
|---|---|---|
| runaway pages (output > 3× reference) | 2 / 0 | 30 / 28 |
| empty outputs | 2 / 2 | 0 / 0 |
| markup characters in output | 149 (32 pages) / 0 | 143 (33 pages) / 0 |

- Most fixed-crop runaways come from duplicated region crops in VieBookRead's `final/` polygons, not from decoding
  loops. Genuine loops affect about 0.015% of regions.
- The base model's markup counts as recognition error for base only, which inflates the reduction by at most
  149 characters out of 83,921 removed edits.

## 5.4 RQ3 — Does the system meet its latency, reliability and usability criteria?

### 5.4.1 Latency and throughput

**Setup.**
- Machine: one RTX 5090 (32 GB) under WSL2.
- Workload: 300 seeded pages from 23 books, all submitted at once.
- Latency is **warm service time** per page (layout + recognition + persistence), with nearest-rank percentiles.

**Table 5.4** Same 300 pages for every run.

| run | model | servers × pages in flight | p50 / p95 / p99 (s) | pages/h |
|---|---|---|---|---|
| 01/10 | base | 2 × 1 | 4.69 / **7.07** / 8.39 | **758** |
| 01/10 | base | 3 × 2 | 8.03 / 12.32 / 14.50 | 873 |
| 24/09 | adapted | 2 × 1 | 7.52 / 12.76 / 17.10 | 458 |
| 01/10 | adapted | 2 × 1 | 7.44 / 11.37 / 12.21 | 484 |
| 24/09 | adapted | 3 × 2 | 12.60 / 19.53 / 21.95 | 556 |

**Answer.**
- With the adapter, the system meets **either** ≥ 500 pages/h (3 × 2) **or** a p95 at the 12 s line (2 × 1), but
  **not both at once**.
- On the same pipeline, the base model meets both.
- Both models generate the same amount of text: 521 vs 523 tokens per page. The entire gap is decode speed: recognition
  is 1.61× slower with the runtime adapter.

**What was tried to close the gap, without changing the model's outputs:**
1. *Older-page-first scheduling of regions.* No gain (p95 21.4 → 20.8 s on dev pages). Service time includes the wait
   as the younger page, and the per-region decode is the limit.
2. *Merging the LoRA into the weights.* This was a separate, pre-registered experiment on 150 development pages.
   - The merged model decodes 1.42–1.45× faster than the runtime adapter, as fast as base, with identical CER
     (1.62% → 1.62%).
   - But 47 of 1,323 regions (3.55%) change their text, whether the merge is done in bf16 or in fp32.
   - The flips come from evaluating x·W + (x·A·B)·2 as two bf16 products instead of one. Any merge has them.
   - Since the served model must produce the evaluated model's outputs exactly, the merge was **not adopted**
     (decision D1 kept).
3. *CPU-side tuning* (garbage collector off during generation, pinning the decode threads). No gain (−1.4%).
   - While decoding with the adapter, GPU utilisation is about 33% (base: 79%). The decode is bound by kernel launches.
   - The same adapter measured 45–56 tokens/s in different sessions on the same machine. This session-to-session spread
     (≈24%) is larger than any tuning effect. **[CHECK]** Report the latency figures with this caveat.

### 5.4.2 Reliability

- **Failure rate.** Soak test of 320 one-page jobs on development pages, production configuration: **320 succeeded,
  0 failed, 0 retried**. With zero failures in 320 jobs, the one-sided 95% upper bound is 0.94%, so **the < 1% target
  is met**.
- The benchmark runs and the end-to-end evaluation add 219 jobs and 9,456 pages, also with no failure.
- **Fault injection.**
  - Killing the worker mid-job: the job resumes on its second attempt, and no page is lost or duplicated.
  - Stopping one of the two recognition servers originally failed 3 of 20 jobs. After a pool-failover change (skip an
    unreachable server for 10 s, resend the region, 5 attempts), the same test gave **20/20**.
  - **[CHECK]** The failover is on branch `pool-failover-2026-10-01`, not yet merged.

### 5.4.3 Resources

| configuration | GPU peak, device (GiB) | per recognition server (GiB, reserved) | host RAM peak (GiB) |
|---|---|---|---|
| 2 servers | 15.1–15.7 | 4.4–6.1 | 12.9–14.0 |
| 3 servers | 19.8–22.7 | 4.1–6.1 | 17.1–18.2 |

- Memory is set by the number of servers, not by the model. The device peaks include 1.8–2.4 GiB used by the Windows
  desktop at idle.
- The 2-server configuration fits the proposal's 24 GB card (22.4 GiB).
- The 3-server configuration does not fit with margin: its worst run peaked at 22.7 GiB including the desktop, about
  20.9 GiB without it. **[CHECK]**
- Training peaked at 22.18 GiB allocated.

### 5.4.4 Usability (placeholder)

The user study is designed and pre-registered (`training/work/study/PREREG.md`, frozen 01/10; one interface-only change
during the pilot, logged in §7 of that file).
- Design: 8 participants, each correcting 4 pages of base output and 4 pages of adapted output, blind and counterbalanced.
- Pass rule: all of
  - K1: SUS ≥ 68;
  - K2: adapted correction time per 1,000 characters lower than base, 95% CI;
  - K3: ≤ 300 s per 1,000 characters, about half of retyping;
  - K4: residual error not worse than +0.5 points.

**Results: pending.** **[CHECK]** If the study cannot run before submission, report RQ3 usability as not evaluated and
move the design to future work.

Known asymmetry to report with the results: on 3 of the 8 study pages, the base output keeps the line breaks of verse,
while the adapted output never breaks lines inside a region. This favours base visually, so it biases K2 against the
adapted model.

## 5.5 Threats to validity

1. **Post hoc test analysis** (§5.1). The models were fixed before the test was touched, but the endpoints were written
   after. The result is robust to this: every CER interval clears −20%.
2. **Pseudo labels.** The test references are distantly supervised. The gold subset agrees in direction and size
   (−55.8% vs −49.4% end-to-end).
3. **Clustering.** Page-level intervals understate uncertainty about new books. Book-level intervals are reported
   alongside.
4. **Single machine.** All performance figures come from one GPU under WSL2. They vary by about 24% between sessions.
5. **Exclusions.** Tables, formulas, figures and seals are excluded from the text (decision D5a, made after the table
   pages were measured). This affects 31 test pages.
6. **External books.** These checks use one typist and 3–5 pages per book.
