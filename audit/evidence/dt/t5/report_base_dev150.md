# viet-ocr-eval — base_dev150

protocol 1.1 · normalization {'collapse_whitespace': True, 'canonical_tone': True, 'lowercase': False} · runaway capped: True · n = 150 pages

| metric | % | denominator |
|---|---|---|
| CER (micro) | 3.78 [3.15–4.77] | 195115 chars |
| CER (macro ± sd) | 4.97 ± 11.04 | per page |
| CER (median page) | 3.16 | per page |
| WER (syllable) | 14.46 [13.08–16.10] | 41813 syllables |
| **DER** | 9.12 [8.35–9.94] | 43656 diacritic graphemes |
| TER (tone only) | 9.89 | 29092 tone-bearing graphemes |
| WSER (whitespace) | 2.38 | 41663 spaces |

## Error breakdown (counts)

| category | count | share |
|---|---|---|
| base letter (substitution) | 1064 | 14.4% |
| tone mark | 2876 | 39.0% |
| letter diacritic (circumflex/breve/horn/stroke) | 1105 | 15.0% |
| insertion | 1064 | 14.4% |
| deletion | 275 | 3.7% |
| whitespace | 991 | 13.4% |

## Run health

- runaway pages: 0 (0.00%)
- empty outputs: 0 (0.00%)
- pages with markup in the hypothesis: 3 (14 markup characters)
- **markup present in hypotheses.** Heading markers, emphasis markers or tags are being scored as recognition errors. Convert model output to plain text before scoring, or this run is not comparable with one that emits plain text.

## Stratified by `difficulty`

| value | n | CER | DER | WSER |
|---|---|---|---|---|
| high | 56 | 3.88 | 10.58 | 2.25 |
| low | 38 | 2.51 | 6.64 | 1.39 |
| mid | 52 | 4.74 | 9.66 | 3.27 |
| unknown | 4 | 14.13 | 31.25 | 23.81 |

## Stratified by `era`

| value | n | CER | DER | WSER |
|---|---|---|---|---|
| 1946–1975 | 67 | 3.36 | 8.11 | 2.63 |
| unknown | 24 | 2.41 | 7.56 | 1.18 |
| ≤1945 | 19 | 2.98 | 10.36 | 0.75 |
| ≥1976 | 40 | 6.18 | 11.51 | 3.71 |

## Stratified by `language`

| value | n | CER | DER | WSER |
|---|---|---|---|---|
| unscored | 6 | 10.82 | 28.57 | 15.91 |
| vi | 144 | 3.77 | 9.10 | 2.36 |
