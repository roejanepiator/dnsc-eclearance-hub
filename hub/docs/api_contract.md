# DNSC e-Clearance Hub: API Contract (v1 draft)

Status: DRAFT for Week 15 (basis for Appendix E). Owner: API developer. Approver: project lead.
Change rule: any change to this file needs a PR reviewed by the API dev **and** the front-end dev.

## 1. Conventions

- **Base path:** `/api/v1`. All bodies are JSON (`application/json; charset=utf-8`), except report exports.
- **Auth:** `Authorization: Bearer <token>` on every endpoint except those marked **Public**.
- **Money:** JSON strings with 2 decimals (`"1500.00"`). Stored as centavos in the DB.
- **Dates:** `YYYY-MM-DD`. Timestamps: ISO-8601 with offset (`2026-11-20T22:00:00+08:00`).
- **IDs in responses:** student IDs are returned **masked** (`2023-***28`) everywhere except the student's own view and the staff `GET /students/{id}` lookup (R16). Masking helper lives in one shared function.
- **Paging:** `?page=1&size=20` (size 1-50). Response includes `page`, `size`, `total`, `has_next`.
- **Rate limiting:** `POST /auth/login` is limited (5 failed attempts, then lockout; see `users.failed_attempts`).

### Error format (all errors)

```json
{ "error": { "code": "VALIDATION_ERROR", "message": "size must be 1-50", "details": {"field": "size"} } }
```

| Status | When | `code` |
|---|---|---|
| 400 | Bad input / failed validation | `VALIDATION_ERROR` |
| 401 | Missing, invalid or expired token; bad login | `UNAUTHENTICATED` |
| 403 | Valid token, role not allowed or not your record | `FORBIDDEN` |
| 404 | Unknown student, slip, import | `NOT_FOUND` |
| 409 | Conflict (e.g. replayed import file, duplicate user) | `CONFLICT` |
| 422 | Import file rejected (bad signature/hash) | `IMPORT_REJECTED` |
| 429 | Too many login attempts | `RATE_LIMITED` |
| 502 | Upstream (Registrar/Nager.Date) failed after retries | `UPSTREAM_ERROR` |
| 500 | Unexpected. Never leak stack traces or SQL | `INTERNAL_ERROR` |

## 2. Roles

| Role | Who | Can do |
|---|---|---|
| `student` | Linked to one `student_id` | See **own** clearance, request **own** slip, see deadline |
| `staff` | Tied to one office (`LIBRARY`, `ACCOUNTING`, `STUDENT_AFFAIRS`, or `REGISTRAR`) | See students, sign off/hold **own office only**; Student Affairs also manages affairs records; Registrar staff can export reports |
| `admin` | Group-only role (R12) | Everything staff can, plus run imports, manage users, read audit log |

## 3. Endpoint summary (16)

| # | Method | Path | Roles | Week 16 must work |
|---|---|---|---|---|
| 1 | GET | `/health` | Public | yes |
| 2 | POST | `/auth/login` | Public | yes |
| 3 | GET | `/auth/me` | any | |
| 4 | GET | `/students` | staff, admin | yes |
| 5 | GET | `/students/{student_id}` | staff, admin | |
| 6 | GET | `/clearance/{student_id}` | student (own), staff, admin | yes |
| 7 | PUT | `/clearance/{student_id}/offices/{office}` | staff (own office), admin | |
| 8 | GET | `/clearance/summary` | staff, admin | |
| 9 | POST | `/clearance/{student_id}/slip` | student (own), staff, admin | |
| 10 | GET | `/slips/{slip_id}/verify` | Public | |
| 11 | GET | `/deadline` | any | |
| 12 | POST | `/affairs/records` | staff (Student Affairs), admin | |
| 13 | POST | `/imports/run` | admin | |
| 14 | GET | `/imports` | admin | |
| 15 | GET | `/reports/clearance` | staff (Registrar), admin | |
| 16 | GET | `/audit-log` | admin | |

User creation is done by an admin script or `POST /users` if time allows (not counted).

## 4. Endpoint details

### 1. GET `/health` (Public)
`200` -> `{"status":"ok","time":"2026-11-20T10:00:00+08:00"}`

### 2. POST `/auth/login` (Public)
Request:
```json
{ "username": "rhea.morales", "password": "..." }
```
`200`:
```json
{ "access_token": "<jwt>", "token_type": "Bearer", "expires_in": 1800,
  "user": { "user_id": 7, "role": "student", "office": null } }
```
Errors: `400` missing fields, `401` wrong credentials (same message for unknown user and wrong password), `429` locked out. Every attempt writes `LOGIN_OK` / `LOGIN_FAIL` to the audit log.

### 3. GET `/auth/me`
`200` -> `{ "user_id": 7, "username": "...", "role": "staff", "office": "LIBRARY" }`

### 4. GET `/students` (staff, admin)
Query: `page`, `size`, `program` (Registrar code, e.g. `IT`), `status` (`ENROLLED|LOA`), `overall` (`CLEARED|HOLD`).
`200`:
```json
{ "page": 1, "size": 20, "total": 40, "has_next": true,
  "data": [ { "student_id": "2023-***28", "name": "MORALES, Rhea B.", "program_code": "AGRI",
              "year_level": 4, "status": "ENROLLED", "overall": "HOLD" } ] }
```

### 5. GET `/students/{student_id}` (staff, admin)
Path param must match `^\d{4}-\d{5}$`, else `400`. Writes `VIEW_STUDENT` to the audit log.
`200` -> full student profile (unmasked ID, name, program, year, email, status) + per-office summary. `404` if unknown.

### 6. GET `/clearance/{student_id}`
Students may only request their own ID (`403` otherwise).
`200`:
```json
{ "student_id": "2023-59928", "overall": "HOLD",
  "offices": [
    { "office": "LIBRARY",         "status": "HOLD",    "reason": "UNPAID_FINES", "updated_at": "2026-11-20T22:05:00+08:00" },
    { "office": "ACCOUNTING",      "status": "CLEARED", "reason": null,           "updated_at": "..." },
    { "office": "STUDENT_AFFAIRS", "status": "CLEARED", "reason": null,           "updated_at": "..." } ],
  "deadline": "2026-12-14" }
```

### 7. PUT `/clearance/{student_id}/offices/{office}`
Staff may only change **their own office** (`403` otherwise). Manual changes set `source = MANUAL`.
Request: `{ "status": "CLEARED", "reason": "Book returned 2026-11-21" }` (reason required when `HOLD`).
`200` -> the updated office entry. `400` invalid status, `404` unknown student/office. Writes `SIGN_OFF` / `SET_HOLD` to the audit log.

### 8. GET `/clearance/summary` (staff, admin)
`200`:
```json
{ "total_students": 40, "cleared": 12, "hold": 28,
  "by_office": { "LIBRARY": {"cleared": 30, "hold": 10},
                 "ACCOUNTING": {"cleared": 22, "hold": 18},
                 "STUDENT_AFFAIRS": {"cleared": 38, "hold": 2} },
  "as_of": "2026-11-20T22:10:00+08:00" }
```
This feeds the R2 "HOLD summary".

### 9. POST `/clearance/{student_id}/slip`
Only issues a slip when overall is `CLEARED`; otherwise `409 CONFLICT` with `reason`.
`201`:
```json
{ "slip_id": "b1c2e6f0-....", "student_id": "2023-***28", "overall": "CLEARED",
  "issued_at": "...", "expires_at": "...", "verify_url": "https://<host>/api/v1/slips/b1c2e6f0-.../verify",
  "qr_png_base64": "iVBORw0..." }
```
**Signature rule (R15):** `signature = HMAC-SHA256(HMAC_SIGNING_KEY, canonical_json(payload))`, where payload = `{slip_id, student_id, overall, issued_at, expires_at}`, keys sorted, separators `(",",":")` (same style as the starter-kit manifest).

### 10. GET `/slips/{slip_id}/verify` (Public)
Returns minimal, masked data only, so anyone scanning the QR sees nothing sensitive.
`200` -> `{ "valid": true, "student_id": "2023-***28", "overall": "CLEARED", "issued_at": "...", "expires_at": "..." }`
Invalid, tampered, expired or revoked slips: `200` with `{"valid": false, "reason": "SIGNATURE_MISMATCH|EXPIRED|REVOKED"}`. Unknown slip: `404`.

### 11. GET `/deadline`
`200` -> `{ "term": "1S 2026-2027", "nominal_deadline": "2026-12-12", "final_deadline": "2026-12-14", "adjusted_for": [{"date":"2026-12-12","reason":"Saturday"}], "holidays_source": "date.nager.at", "computed_at": "..." }`
If Nager.Date is down: serve cached holidays from the `holidays` table. If none cached, `502 UPSTREAM_ERROR`.

### 12. POST `/affairs/records`
Request: `{ "student_id": "2023-59928", "record_type": "EQUIPMENT", "description": "Projector (borrowed 2026-10-02)", "outstanding": true }`
`201` -> created record. Triggers recompute of that student's `STUDENT_AFFAIRS` status. `404` if the student isn't in the Registrar list.

### 13. POST `/imports/run` (admin)
Triggers the same code the scheduled script uses (R1), then recomputes clearance.
`202` -> `{ "run_id": 12, "status": "RUNNING" }`; poll `GET /imports` for the result.
A file with an invalid signature, hash mismatch or reused nonce is **rejected whole** (nothing read), logged as `IMPORT_REJECTED`.

### 14. GET `/imports` (admin)
`200` -> paged list of `import_files` rows with `accepted_rows`, `rejected_rows`, `status`, `reject_reason`. Optional `include=rejects` returns row-level rejects (`row_ref`, `reason_code`) with raw data redacted.

### 15. GET `/reports/clearance` (Registrar staff, admin)
Query: `format=csv|json|xml` (required), optional `overall`, `program`.
Student IDs **masked**. Responses use `text/csv`, `application/json`, `application/xml`. Unsupported format: `400`. Writes `EXPORT` to the audit log.

### 16. GET `/audit-log` (admin)
Query: `page`, `size`, `action`, `from`, `to`. Each entry returns `audit_id, ts, actor_role, action, target_id (masked), prev_hash, entry_hash`. `GET /audit-log?verify=true` re-walks the hash chain and returns `{"chain_valid": true}`.

## 5. Clearance rules (single source of truth)

| Office | HOLD when | Else |
|---|---|---|
| LIBRARY | `unreturned_books > 0` **or** `unpaid_fines > 0` on the student's single Library row | CLEARED |
| ACCOUNTING | `balance > 0` for the current term | CLEARED |
| STUDENT_AFFAIRS | any `affairs_records` row with `outstanding = 1` | CLEARED |
| Overall | any office HOLD | CLEARED when all three are CLEARED |

Manual staff decisions (`source = MANUAL`) win over AUTO until the next import changes the underlying data, at which point the audit log records the override being replaced.

## 6. Decisions (settled by the team)

| # | Situation | Decision |
|---|---|---|
| 1 | LOA student | HOLD on all offices, `reason = ON_LOA`, no slip issued |
| 2 | Enrolled student with no Library record | CLEARED (never borrowed) |
| 3 | Enrolled student with no Accounting record | HOLD, `reason = NO_ACCOUNTING_RECORD` (payment cannot be confirmed) |
| 4 | Accounting payment date after the export date | Reject the row as `FUTURE_DATE` (logged); the student then has no Accounting record, so decision 3 applies |
| 5 | Duplicate rows for one student | No duplicates: one record per student per source, enforced by the database. Validate each row first; invalid rows are rejected. If exactly one valid row remains, keep it. If valid rows disagree, reject all as `DATA_CONFLICT` and set that office to HOLD with `reason = NEEDS_REVIEW`. A newer import replaces the old row (upsert) |
| 6 | Login token lifetime | 30 minutes, no refresh token |
| 7 | Manual staff decision vs. imported data | The manual decision stays until the next import changes the underlying data; the replacement is written to the audit log |

Changing any of these needs a pull request, and the API dev, Data engineer and Security engineer must be told.

### Reason codes (use exactly these)

| Where | Codes |
|---|---|
| Clearance HOLD reasons | `UNPAID_FINES`, `UNRETURNED_BOOKS`, `BALANCE_DUE`, `NO_ACCOUNTING_RECORD`, `ON_LOA`, `NEEDS_REVIEW`, `AFFAIRS_OUTSTANDING` |
| Import reject reasons | `NOT_IN_REGISTRAR`, `BAD_STUDENT_NO`, `BAD_NAME`, `BAD_DATE`, `BAD_AMOUNT`, `NEGATIVE_AMOUNT`, `UNKNOWN_PROGRAM`, `FUTURE_DATE`, `DUPLICATE`, `DATA_CONFLICT` |
