# viet-ocr-eval — lr2e4_s3000_dev150

protocol 1.1 · normalization {'collapse_whitespace': True, 'canonical_tone': True, 'lowercase': False} · runaway capped: True · n = 150 pages

| metric | % | denominator |
|---|---|---|
| CER (micro) | 1.62 [1.22–2.23] | 195115 chars |
| CER (macro ± sd) | 2.30 ± 6.97 | per page |
| CER (median page) | 1.11 | per page |
| WER (syllable) | 6.31 [5.47–7.35] | 41813 syllables |
| **DER** | 2.39 [1.94–2.87] | 43656 diacritic graphemes |
| TER (tone only) | 2.95 | 29092 tone-bearing graphemes |
| WSER (whitespace) | 1.59 | 41663 spaces |

## Error breakdown (counts)

| category | count | share |
|---|---|---|
| base letter (substitution) | 633 | 20.0% |
| tone mark | 857 | 27.1% |
| letter diacritic (circumflex/breve/horn/stroke) | 185 | 5.9% |
| insertion | 598 | 18.9% |
| deletion | 223 | 7.1% |
| whitespace | 662 | 21.0% |

## Run health

- runaway pages: 0 (0.00%)
- empty outputs: 0 (0.00%)
- pages with markup in the hypothesis: 0 (0 markup characters)

## Stratified by `difficulty`

| value | n | CER | DER | WSER |
|---|---|---|---|---|
| high | 56 | 1.55 | 2.94 | 1.61 |
| low | 38 | 1.02 | 1.33 | 1.40 |
| mid | 52 | 2.19 | 2.69 | 1.71 |
| unknown | 4 | 4.35 | 12.50 | 4.76 |

## Stratified by `era`

| value | n | CER | DER | WSER |
|---|---|---|---|---|
| 1946–1975 | 67 | 1.12 | 1.24 | 1.76 |
| unknown | 24 | 0.76 | 1.15 | 1.27 |
| ≤1945 | 19 | 0.87 | 2.04 | 0.52 |
| ≥1976 | 40 | 3.80 | 5.98 | 2.15 |

## Stratified by `language`

| value | n | CER | DER | WSER |
|---|---|---|---|---|
| unscored | 6 | 4.64 | 11.43 | 6.82 |
| vi | 144 | 1.62 | 2.38 | 1.58 |
