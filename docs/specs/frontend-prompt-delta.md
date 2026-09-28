# Frontend — amendment for a session already in progress (23/09)

> Paste into the Claude Code session that is already building the frontend.
> Use `frontend-prompt.md` instead if you are starting fresh.
> Apply the backend amendment first; these changes depend on its new endpoints.
> Regenerate the OpenAPI client before starting.

---

The thesis requirements have been checked against the proposal, and the
frontend needs the changes below. Apply them to what exists; do not restart.
Before writing code, list which of these touch code already written and propose
the order. Wait for my confirmation.

## 1. Monitoring link

Add a **Monitoring** menu item that opens Grafana (`[http://localhost:3000]`) in
a new tab. The proposal promises a monitoring dashboard; Grafana is it. Still no
Dashboard screen.

## 2. Queue screen

Show each job's **queue wait** and **service time** from the API. Display only;
do not compute them.

## 3. Review screen — what the reviewer is told

The text pane shows plain text from which headers, page numbers, tables and
formulas were deliberately excluded. A reviewer who does not know this retypes
the page number on every page, which corrupts edits-per-page and makes corrected
pages useless as reference text.

- show a quiet notice listing excluded regions from the revision's
  `plaintext_stats` (e.g. "Đã loại: 1 tiêu đề trang, 1 số trang")
- show a transcription guideline panel from
  `[./config/review-guideline.vi.md]`, visible on first open each session and
  one keystroke away after. Default: chép đúng như trang in, giữ chính tả cũ và
  gạch nối (`Việt-Nam`); không gõ lại phần bị loại; chỉ sửa lỗi nhận dạng
- the revision panel shows the machine revision's model version and text policy

## 4. Usability instrumentation

- **participant code** prompt at session start, pattern `^P\d{2}$`
  (configurable). No name field anywhere.
- events to `POST /review-events`: `open`, `first_edit` (once per page visit),
  `save`, `leave`, `idle_start` / `idle_end` (60 s without keyboard, mouse,
  scroll or IME input; configurable)
- each event: `page_id`, `revision_id` if any, `participant_code`, per-tab
  `session_id`, event, `Date.now()` plus `performance.now()`
- queue in memory; flush every 10 s and on save; `navigator.sendBeacon` on
  `pagehide` / hidden; failed flushes retry silently, never block editing
- build the queue as a standalone module with its own tests **before** wiring it
  into the editor
- no SUS questionnaire (paper)

## 5. No metrics in the browser

The revision diff is for display only. No edit count, percentage or "accuracy"
badge, and no active-time calculation in the client. Those come from the
backend export and `viet-ocr-eval`.

## Tests to add

- instrumentation queue: order kept; idle timer with fake timers; `sendBeacon`
  on `pagehide`; failed flush retained; invalid participant code rejected
- editor: `first_edit` once per visit; excluded-regions notice renders from
  `plaintext_stats`
- MSW handler for `/review-events` records payloads
- extend the Playwright E2E: participant code → … → review with edit and save →
  export, asserting `open`, `first_edit`, `save`, `leave` arrived in order
