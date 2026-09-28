# Vietnamese orthography, as it affects scoring

Read this when a normalization decision needs justifying in the thesis, when a
number looks wrong, or before changing anything in `normalize.py`.

## The two kinds of mark

Vietnamese in the Latin script carries two categories of diacritic that behave
completely differently, and collapsing them is the most common way a "diacritic
error rate" ends up meaning nothing.

**Letter diacritics** are part of the letter's identity. `ă â ê ô ơ ư đ` are
distinct letters of the alphabet, not decorated versions of `a e o u d`. Under
NFD these appear as a base letter plus:

| mark | codepoint | letters |
|---|---|---|
| circumflex | U+0302 | â ê ô |
| breve | U+0306 | ă |
| horn | U+031B | ơ ư |
| stroke | *(see below)* | đ |

**Tone marks** encode one of six tones, five of them written:

| tone | mark | codepoint |
|---|---|---|
| huyền | grave | U+0300 |
| sắc | acute | U+0301 |
| ngã | tilde | U+0303 |
| hỏi | hook above | U+0309 |
| nặng | dot below | U+0323 |
| ngang | *(unmarked)* | — |

A single vowel can carry one of each, stacked: `ế` is `e` + circumflex + acute.
The categoriser handles this correctly — `tiếng` recognised as `tiêng` is scored
as one tone error, not as a base-letter error and not as two errors.

This split is what the thesis's error decomposition rests on. `ma / má / mà`
differ only by tone and mean *ghost / mother / but*; a model that loses tone
marks on degraded pages is failing differently from one that confuses `n` and
`u`, and the report has to be able to say which.

## đ does not decompose

`đ` (U+0111) and `Đ` (U+0110) have **no canonical decomposition**. NFD leaves
them atomic. Scored naively, `đi` recognised as `di` counts as a base-letter
substitution — but it is exactly the same failure mode as losing a circumflex:
the model saw the letter and missed the stroke.

`normalize.to_nfd()` therefore splits them into base + a private-use sentinel
(U+E000) that is classified as a letter diacritic. `from_nfd()` recomposes them.
The sentinel never escapes the scoring path.

## Tone placement is not an error

For nuclei `oa oe uy` (and `uơ`, `uê`), two placements are both correct:

| traditional | modern |
|---|---|
| hòa | hoà |
| hòe | hoè |
| thùy | thuỳ |
| thúy | thuý |

The choice is a typesetting convention. 19th-century books use one, modern
ebook reference text often uses the other, and VieBookRead's references come
from ebooks. Left alone, this inflates CER on a large fraction of syllables and
— worse — inflates it *specifically in TER*, the metric the thesis is trying to
report on.

`canonicalize_tone_position()` fixes this mechanically: within each maximal run
of vowel letters, move every tone mark onto the first vowel of the run. This is
deliberately **not** standard orthography. It does not need to be. It is a
normal form, applied identically to reference and hypothesis, so the convention
difference cancels out. Note in the thesis that it is a scoring transform, and
never apply it to exported text or to text shown to a proofreader.

If a syllable somehow carries two tone marks (only happens on malformed output),
they are spread left to right across the vowel run rather than silently dropped,
so the error stays visible.

## Whitespace separates syllables, not words

`Hà Nội` is one word and two syllables. `bệnh viện`, `hợp tác xã` likewise. This
has two consequences:

1. **"WER" here is a syllable error rate.** Report the number — it is what
   everyone else reports and comparability matters — but name what it measures
   in the text. Do not silently let a reader assume word-level.
2. **Whitespace errors deserve their own rate.** Joining `Hà Nội` into `HàNội`
   or splitting `tiếng` into `tiê ng` are recognition failures specific to
   Vietnamese typesetting, and they are invisible inside an aggregate CER.
   `WSER` counts them over the number of reference spaces.

The scorer counts a space deletion as one whitespace error, not as two
base-letter errors on the surrounding characters.

## Line breaks must be collapsed

Reference text comes from ebooks; hypotheses come from scanned page images. The
line breaks will never agree — different page size, different typesetting,
different era. Left uncollapsed, line-break mismatches dominate CER and hide the
recognition errors you are trying to measure.

`canonical()` collapses every whitespace run to a single space by default. Word
joining and splitting survive collapsing, so the linguistically meaningful
whitespace behaviour is preserved while the layout noise is removed.

If a run needs the layout preserved, `--no-collapse-whitespace` exists — but the
resulting number is not comparable to any run that used the default, and
`compare` will refuse to pair them.

## Legacy encodings

If any part of the corpus predates Unicode adoption, check for VNI or TCVN3
(ABC) encoded text. These are byte-level schemes that will not survive
`unicodedata.normalize` and will show up as dense garbage. Convert them to
Unicode at ingestion, before anything reaches the scorer.

Deprecated combining marks U+0340 (grave tone) and U+0341 (acute tone) are
handled automatically — NFC maps them to U+0300 and U+0301.

## Case

Case is kept by default and the primary number is case-sensitive. Report
case-insensitive as a secondary if it is informative — on historical print with
decorative capitals and small caps the gap can be worth a sentence. Do not
switch the primary.
