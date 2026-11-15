# Task Plan (team of 4)

All paths are inside `hub/`. A stage starts when the previous one is **done**, not on a date.
Read Stage 0 plus **your role only**.

With 4 members there is no separate Front-end/QA role. The briefing gives it to the Lead,
and we split the screens so each person builds the pages that sit next to their own work.

## Who owns what
| Role | Owns |
|---|---|
| **Lead** | emerging tech (R3, R4), test plan and report (R17), rater tracker, user guide, final report, decisions |
| **API dev** | `app/main.py`, `app/db.py`, `app/routes/`, `app/registrar_client.py`, `app/holidays_client.py`, `db/schema.sql`, `docs/api_contract.md`, staff and admin pages (R5-R7, part of R8) |
| **Data** | `app/importers/`, `app/clearance.py`, `app/exports.py`, `scripts/run_imports.py`, `docs/mapping_spec.md` (R1, R2, R9, R10) |
| **Security** | `app/security/`: login, roles, masking, manifest check, slips, audit log; student page with QR slip (R11-R16, part of R8) |

**Client style (Lead decides):** plain HTML + JavaScript pages in `client/` that call the Hub API.
One page per role: `student.html`, `staff.html`, `admin.html`. The API dev serves `client/` from the Hub.
Build against the example responses in `docs/api_contract.md` until the real endpoints exist.

## Stage 0: Setup
*Done when:* everyone runs the mock Registrar and `uvicorn app.main:app` locally, and `python -m pytest` passes.
- **All:** clone, `cd hub`, install, copy `.env.example` to `.env`, paste the keys from the Lead, run the mock.
- **Lead:** send the keys privately, settle the 6 open decisions at the end of `docs/api_contract.md`.

## Stage 1: Foundations (parallel)
*Done when:* the Registrar sync loads 40 students and login returns a token.
- **API dev:** `/api/v1` prefix, contract error format, DB from `schema.sql`, `/health`, route files.
- **Security:** password hashing, login + token, role checks, `mask_student_id()` (push early).
- **Data:** mapping spec, Library XML and Accounting CSV adapters (return good rows + rejects).
- **Lead:** choose the 2 emerging-tech components (QR slip + hash-chained audit log), test case table (20+), rater tracker.

## Stage 2: First integration
*Done when:* one real student shows a real CLEARED or HOLD on the student page.
- **Data:** importers verify the manifest first, then save rows and rejects; `clearance.py` computes status.
- **API dev:** `GET /students`, `GET /clearance/{id}`, `GET /auth/me`; start the staff page.
- **Security:** audit log with hash chain, wired to login; start the student page (login + status).
- **Lead:** run the first integration check, log bugs, start the test report.

## Stage 3: Feature complete
*Done when:* all 16 endpoints work and the tampered file is rejected.
- **API dev:** remaining endpoints, holidays client + deadline service, API spec, staff and admin pages.
- **Data:** automation script (schedule, logs, archive, HOLD summary), CSV/JSON/XML exports.
- **Security:** signed slips + QR + verify, input validation, SQL and secrets review, student page with slip.
- **Lead:** user guide, line up raters, full fresh-clone test.

## Stage 4: Hardening and code freeze
*Done when:* all tests pass and only bug fixes are merged.
- **Security:** attack tests (SQL injection, replay, tampered file, wrong role, lockout).
- **Lead:** run all test cases, finish the test report, call the freeze, tag the release.
- **Data:** re-check import counts. **API dev:** fix bugs.

## Stage 5: Evaluation (starts at Stage 3, overlaps 4)
*Done when:* 30 signed sheets and 30 photos match the tracker.
- **All:** each member brings about 8 raters (4 x 8 = 32). Photo consent first; if declined, find another rater.
- **Lead:** keeps the tracker and the ratings summary.

## Stage 6: Final documents and demo
*Done when:* PDF compiled, signed sheets collected, demo rehearsed twice.
- **Lead:** compile the PDF and write Appendix I (who built what, including the screen split).
- **Everyone:** write your part of chapter 3 and know your code for Q&A.
