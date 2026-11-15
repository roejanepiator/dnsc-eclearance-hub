# Task Plan

All paths are inside `hub/`. A stage starts when the previous one is **done**, not on a date. Read Stage 0 plus **your role only**.
With 4 members, the Lead also does Front-end/QA.

## Who owns what
| Role | Owns |
|---|---|
| **Lead** | `docs/design.md`, emerging tech (R3, R4), decisions, final report |
| **API dev** | `app/main.py`, `app/db.py`, `app/routes/`, `app/registrar_client.py`, `app/holidays_client.py`, `db/schema.sql`, `docs/api_contract.md` (R5-R7) |
| **Data** | `app/importers/`, `app/clearance.py`, `app/exports.py`, `scripts/run_imports.py`, `docs/mapping_spec.md` (R1, R2, R9, R10) |
| **Security** | `app/security/`: login, roles, masking, manifest check, slips, audit log (R11-R16) |
| **Front-end/QA** | `client/`, `tests/`, rater tracker, user guide (R8, R17) |

## Stage 0: Setup
*Done when:* everyone runs the mock Registrar and `uvicorn app.main:app` locally.
- **All:** clone, `cd hub`, install, `generate_keys.py`, run the mock.
- **Lead:** settle the 6 open decisions at the end of `docs/api_contract.md`.

## Stage 1: Foundations (parallel)
*Done when:* the Registrar sync loads 40 students and login returns a token.
- **API dev:** `/api/v1` prefix, contract error format, DB from `schema.sql`, `/health`, route files.
- **Security:** password hashing, login + token, role checks, `mask_student_id()` (push early).
- **Data:** mapping spec, Library XML and Accounting CSV adapters (return good rows + rejects).
- **Front-end/QA:** screens built on the contract examples, 20+ test case table, rater tracker.
- **Lead:** design document, choose 2 emerging-tech components (QR slip + hash-chained audit log).

## Stage 2: First integration
*Done when:* one real student shows a real CLEARED or HOLD in the client.
- **Data:** importers verify the manifest first, then save rows and rejects; `clearance.py` computes status.
- **API dev:** `GET /students`, `GET /clearance/{id}`, `GET /auth/me`.
- **Security:** audit log with hash chain, wired to login.
- **Front-end:** switch from mock data to the real API.

## Stage 3: Feature complete
*Done when:* all 16 endpoints work and the tampered file is rejected.
- **API dev:** remaining endpoints, holidays client + deadline service, API spec.
- **Data:** automation script (schedule, logs, archive, HOLD summary), CSV/JSON/XML exports.
- **Security:** signed slips + QR + verify, input validation, SQL and secrets review.
- **Front-end:** all views, user guide, run test cases.
- **Lead:** finish design doc, line up raters, full fresh-clone test.

## Stage 4: Hardening and code freeze
*Done when:* all tests pass and only bug fixes are merged.
- **Security:** attack tests (SQL injection, replay, tampered file, wrong role, lockout).
- **Front-end/QA:** full test report. **Data:** re-check import counts. **API dev:** fix bugs.
- **Lead:** call the freeze, tag the release.

## Stage 5: Evaluation (starts at Stage 3, overlaps 4)
*Done when:* 30 signed sheets and 30 photos match the tracker.
- **All:** each member brings about 6 raters. Photo consent first; if declined, find another rater.
- **Front-end/QA:** keeps the tracker. **Lead:** ratings summary.

## Stage 6: Final documents and demo
*Done when:* PDF compiled, signed sheets collected, demo rehearsed twice.
- **Lead:** compile the PDF. **Everyone:** write your part of chapter 3 and know your code for Q&A.
