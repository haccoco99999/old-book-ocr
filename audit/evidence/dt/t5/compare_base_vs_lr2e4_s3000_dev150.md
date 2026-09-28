# Paired comparison — base_dev150 vs lr2e4_s3000_dev150

n = 150 paired pages · 1000 bootstrap resamples

| metric | base % | adapted % | rel. change | 95% CI on rel. change |
|---|---|---|---|---|
| cer_micro | 3.78 | 1.62 | -57.2% | [-62.1%, -52.2%] |
| der | 9.12 | 2.39 | -73.8% | [-77.9%, -70.0%] |
| ter | 9.89 | 2.95 | -70.2% | [-75.1%, -65.7%] |
| wer_micro | 14.46 | 6.31 | -56.3% | [-59.6%, -52.9%] |
| wser | 2.38 | 1.59 | -33.2% | [-42.7%, -20.3%] |

**Target met.** The whole 95% interval clears a 20% relative CER reduction.

## Where the reduction came from

Total character edits removed: 4217 (base − adapted, 150 paired pages)

| category | edits removed | share of reduction |
|---|---|---|
| **tone + letter diacritic** | 2939 | 69.7% |
| tone mark | 2019 | 47.9% |
| letter diacritic | 920 | 21.8% |
| base letter | 431 | 10.2% |
| insertion | 466 | 11.1% |
| deletion | 52 | 1.2% |
| whitespace | 329 | 7.8% |
| runaway pages (capped) | 0 | 0.0% |

Diacritic share 95% CI: [59.35%, 78.02%]. Diacritics removed more edits than every other category in 100.0% of resamples.

**Markup in hypotheses: base 14 chars, adapted 0 chars.** Part of the difference may be formatting, not recognition.
