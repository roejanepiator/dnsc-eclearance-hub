# DNSC e-Clearance Hub

One system that merges the Registrar, Library, Accounting and Student Affairs data into a single **CLEARED / HOLD** status per student.
IT312 Final Project, Track A. FastAPI + SQLite. Team of 4. All data is synthetic.

All code is in `hub/`. Run every command below from inside `hub/`.
(`hub/README.md` is the instructor's original starter kit README.)

## How it works
1. Pull the official student list from the **Registrar API** (JSON).
2. Import **Library** (XML) and **Accounting** (CSV) files, only after checking their signature.
3. Decide CLEARED or HOLD per office and overall.
4. Students and staff use a client app that talks to the **Hub REST API**.

## Setup (once per person)
1. `git clone <repo url>` then `cd hub`
2. `pip install -r requirements.txt`
3. Copy the template: `copy .env.example .env` (Windows) or `cp .env.example .env` (Mac/Linux)
4. Open `.env` and replace the 3 `ask-the-lead` values with the ones the Lead sent you **privately**
5. `git status`  (`.env` must NOT be listed)

Everyone uses the **same 3 keys**. Never paste them in Git, in a pinned message, or in a screenshot.
`generate_keys.py` is for the Lead only. Do not run it (especially not `--force`): it would give you
different keys from the team. If a key leaks, tell the Lead.

## Run
- **Mock Registrar** (port 8001): `python registrar_mock_api.py`  (reads the key from `.env`)
- **Hub** (port 8000): `uvicorn app.main:app --reload --port 8000`, then open http://127.0.0.1:8000/docs
- **Tests:** `python -m pytest`

A browser visit to the mock shows `401`: that is normal, the key must be sent as an `X-API-Key` header.

## What is where (inside `hub/`)
| Path | What | Owner |
|---|---|---|
| `app/main.py`, `app/db.py`, `app/routes/` | Hub app, database, endpoints | API dev |
| `app/registrar_client.py`, `app/holidays_client.py` | Calls to the Registrar and holidays APIs | API dev |
| `app/security/` | Login, roles, masking, signatures, slips, audit log | Security |
| `app/importers/`, `app/clearance.py`, `app/exports.py` | Importers, CLEARED/HOLD rules, report exports | Data |
| `scripts/` | Automation script | Data |
| `client/` | Student, staff and admin pages | Security (student) / API dev (staff, admin) |
| `tests/` | pytest tests (everyone adds tests for their own code) | Lead (test plan) |
| `db/schema.sql` | Database tables | API dev |
| `docs/` | API contract (API dev), mapping spec (Data) | |
| `generate_keys.py` | Makes the shared keys (Lead only) | Lead |
| `registrar_mock_api.py`, `registrar_students.json`, `verify_manifest.py`, `drop_folder/`, `tamper_tests/` | Instructor starter kit (leave as is, except the key line in the mock) | |

## Keys in `.env`
| Key | Used for |
|---|---|
| `REGISTRAR_API_KEY` | Hub <-> mock Registrar |
| `HMAC_SIGNING_KEY` | Our own signatures (import manifests, slips) |
| `APP_SECRET_KEY` | Login tokens |
| `STARTER_HMAC_KEY` | Checking the starter kit files only (public demo value) |

## Team rules
- Never commit `.env` or any real secret. One in the Git history = -10 points.
- Own branch, pull request into `main`, one reviewer. Commit your own code.
- Change `db/schema.sql` or `docs/api_contract.md` only through a pull request, and tell the API dev.
- Synthetic data only. Rater sheets and photos stay out of Git.

Who does what, in order: see [TASKS.md](TASKS.md).
