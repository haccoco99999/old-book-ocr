# Prompt — build the frontend  (revised 23/09)

> Paste everything below the line into Claude Code at the repo root.
> Edit the bracketed values first. Run after the backend exists, or at least
> after its OpenAPI schema does.
> **If a session built from the earlier version is already running, paste
> `frontend-prompt-delta.md` into it instead of this file.**

---

You are building the frontend for a self-hosted OCR platform for scanned
Vietnamese books. Hard deadline **[30 September 2026]**, about one week away.
A reviewer will spend hours a day in this interface proofreading old book
pages, so reading comfort and correct Vietnamese text handling matter more than
breadth of features.

The frontend also produces the raw data for the thesis usability study
(research question 3): time per page and edits per page, from real
proofreading sessions. Instrumentation is a deliverable, not an afterthought.

## Stack — pin these, do not upgrade mid-project

- **UmiJS / `@umijs/max` 4**
- **React 19**
- **antd 6** with **`@ant-design/icons` >= 6** — these two must move together;
  `@ant-design/icons@6` is not compatible with `antd@5`
- **`@ant-design/pro-components` v3** (single package; the separate
  `pro-table` / `pro-form` / `pro-layout` packages are gone)
- Do **not** install `@ant-design/v5-patch-for-react-19`. antd 6 supports React
  19 natively and the patch will break things.
- Import from `@umijs/max`, not `umi`:
  `import { useModel, request, useAccess, getLocale, useIntl } from '@umijs/max'`

Pin exact versions, commit the lockfile, and do not upgrade during the project.

## Screens

Four screens and one external link.

1. **Upload / Ingestion** — drag-drop PDF or images, validation, progress,
   per-document status
2. **Queue** — job list with status, retry, failure reason, live-ish refresh.
   Show each job's **queue wait** and **service time** as the backend returns
   them. Display them; do not compute your own.
3. **Review / Proofreading** — the critical screen, see below
4. **Export** — choose format (txt / Markdown / JSON), scope, download

**Monitoring** is a menu item that opens the Grafana URL
(`[http://localhost:3000]`) in a new tab. The thesis proposal promises a
monitoring dashboard; Grafana is that dashboard. Do not build a Dashboard screen.

Screens 1, 2 and 4 are ProComponents work — `ProTable` with request-driven
pagination, `ProForm` for filters, `ProLayout` for the shell. Keep them plain.
Spend the saved time on screen 3.

## Screen 3 — Review / Proofreading

Split view: page image on the left, recognized text on the right.

- synchronized scrolling, toggleable
- image pane: zoom, pan, fit-width, fit-page, rotate; keyboard shortcuts
- text pane: editable, monospace optional, generous line height, adjustable
  font size
- previous/next navigation that does not lose unsaved edits
- save writes a **new revision**; the machine output is never overwritten and
  stays viewable
- a revision history panel with a diff against the machine output, showing the
  model version and text policy of the machine revision
- keyboard-first: a reviewer should get through a page without the mouse

### What the reviewer is shown, and why it matters

The text pane shows the backend's **plain-text** output. Some regions — running
headers, page numbers, tables, formulas — are deliberately excluded from it,
because the reference text they are scored against does not contain them.

A reviewer who does not know this will type the page number back in on every
page. Each of those keystrokes becomes an "edit", which corrupts the edits-per-
page measure and makes human-corrected pages useless as reference text.

So:

- show a quiet notice listing what was excluded on this page, from the
  revision's `plaintext_stats` (for example "Đã loại: 1 tiêu đề trang, 1 số
  trang")
- show a short **transcription guideline** panel, loaded from a config Markdown
  file `[./config/review-guideline.vi.md]`. Default content:
  - chép đúng như trang in — giữ chính tả cũ (`nhứt`, `nầy`) và gạch nối giữa
    âm tiết (`Việt-Nam`); không sửa sang chính tả hiện đại
  - không gõ lại phần đã bị loại (tiêu đề trang, số trang, bảng)
  - chỉ sửa lỗi nhận dạng
- the guideline is visible on first open of every session and one keystroke
  away afterwards

### Vietnamese text handling — three non-negotiables

A generic editor implementation will quietly corrupt data here.

**1. IME composition.** Vietnamese is typed with Telex or VNI, which fire
`compositionstart` / `compositionupdate` / `compositionend`. Track composition
state; do not transform, normalise or autosave during a composition. Test: a
simulated composition sequence producing `tiếng` yields `tiếng`.

**2. NFC on input and paste.** macOS and other sources produce decomposed (NFD)
text. Normalise to NFC on paste and before every save, **after**
`compositionend`, never during. Mixed forms in the database silently corrupt
every error-rate number computed later.

**3. Font coverage for stacked diacritics.** `ế ộ ữ ẫ ể` stack a letter
diacritic and a tone mark. Many web fonts lack these glyphs and fall back per
character, shifting the baseline. Pick a font with verified Vietnamese coverage,
declare an explicit fallback stack, and add a check page rendering all 134
Vietnamese precomposed vowels.

## Usability instrumentation

Research question 3 is answered from these events. SUS is collected separately
on paper after each session — **do not build a questionnaire.**

**Participant code.** At the start of a review session, ask for an opaque code
such as `P03`. Validate it against a pattern (`^P\d{2}$`, configurable).
Never ask for or store a name. Keep it in session state for the tab's lifetime.

**Events**, sent to `POST /review-events`:

| event | when |
|---|---|
| `open` | a page is displayed in the review screen |
| `first_edit` | the first change to the text of that page in this visit |
| `save` | a revision is saved |
| `leave` | navigation away from the page, or tab hidden |
| `idle_start` / `idle_end` | no keyboard, mouse or scroll input for 60 s (configurable), and the next input after that |

Each event carries `page_id`, `revision_id` when there is one,
`participant_code`, a `session_id` generated per tab, the event name, and a
client timestamp (`Date.now()` for wall clock, with `performance.now()` kept
alongside so ordering survives a clock change).

Delivery:

- queue events in memory and flush every 10 s and on save
- on `pagehide` or `visibilitychange` to hidden, flush with
  `navigator.sendBeacon`
- a failed flush retries with the next one; it never blocks editing and never
  shows an error to the reviewer, but it is logged to the console
- IME composition counts as input and ends an idle period

**No metric is computed in the browser.** The revision-history diff is for
display. It must never be turned into a count, a percentage, or an "accuracy"
figure. Active time and edits per page are derived on the backend and by the
`viet-ocr-eval` skill from the raw events and revisions.

## API layer

Generate the client from the backend OpenAPI schema at
`[http://localhost:8000/openapi.json]` using the Umi `openapi` plugin. Do not
hand-write request types.

Mock with **MSW**, handlers derived from the same schema, so the frontend runs
and tests with the backend down. The MSW handler for `/review-events` records
what it receives so tests can assert on it.

## Testing

Use the test runner `@umijs/max` 4 ships with; fall back to Vitest if there is
no clear built-in. React Testing Library either way.

Required, in priority order:

1. **Unit tests for text utilities** — NFC normalisation, diacritic-safe
   operations, the composition-state reducer.
2. **Unit tests for the instrumentation queue** — events keep their order;
   `idle_start` fires after the threshold and `idle_end` on the next input,
   using fake timers; a flush on `pagehide` uses `sendBeacon`; a failed flush
   keeps the events for the next attempt; an invalid participant code is
   rejected.
3. **Component tests for the review editor** — composition produces correct
   output; pasted NFD is stored as NFC; editing never overwrites the machine
   revision; the unsaved-changes guard fires on navigation; `first_edit` fires
   once per page visit; the excluded-regions notice renders from
   `plaintext_stats`.
4. **Integration tests** against MSW — upload, queue polling and retry, export.
5. **One Playwright E2E**: enter participant code → upload → queue → review
   with an edit and save → export, asserting that `open`, `first_edit`, `save`
   and `leave` reached the mock backend in that order.

No snapshot tests for ProComponents screens. No coverage target.

## Design constraints

- Desktop-first. Do not spend time on mobile layouts.
- High contrast, calm palette, generous whitespace — the reviewer reads
  degraded 19th-century scans for hours.
- Light theme is the default and must be excellent. Dark theme only if it costs
  nothing — antd 6 uses CSS variables, so it usually does.
- Vietnamese UI copy, with i18n wired so English is a config change.

## Build order

Stop at each gate.

1. Scaffold, pinned versions, `ProLayout` shell with the Monitoring link,
   routing, OpenAPI client generation, MSW.
   *Gate: the app runs against mocks with the backend down; show me the
   generated client types.*
2. Upload and Queue screens.
   *Gate: both work end to end against MSW, and Queue shows queue wait and
   service time from the API.*
3. **Text utilities and the instrumentation queue, as standalone modules,
   before any editor markup.**
   *Gate: text-utility and instrumentation tests pass, including the `tiếng`
   composition case and the idle timer.*
4. Review screen UI: split view, sync scroll, zoom, revisions, shortcuts,
   excluded-regions notice, guideline panel, participant-code prompt, events
   wired in.
5. Export screen.
6. Playwright E2E and the font check page.

## Acceptance criteria

- no `@ant-design/v5-patch-for-react-19` in the dependency tree
- `antd` and `@ant-design/icons` both at major version 6
- every request type generated from OpenAPI
- text saved through the editor is NFC, asserted by test
- composing `tiếng` yields `tiếng`, asserted by test
- the machine revision is immutable, asserted by test
- the E2E proves review events reach the backend in order
- no participant name field exists anywhere in the UI
- no error rate, edit count or accuracy figure is computed or displayed
- the app builds and runs with the backend unreachable

## Things that will tempt you

- building a Dashboard screen because Pro templates ship one
- upgrading a dependency mid-project to fix a warning
- handling text on `onChange` without checking composition state
- normalising Unicode during composition instead of after it
- hand-writing API types "just for now"
- snapshot-testing ProTable screens
- turning the diff into an "accuracy %" badge
- computing active time in the browser
- a friendly "Name" field on the participant prompt
- hiding the guideline behind a help icon nobody opens
- treating the review screen as the last item because the others look like
  progress — it is the only screen that carries real risk

Start with step 1. Show me the pinned `package.json` and the generated client
types before writing screens.
