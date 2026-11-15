# DNSC e-Clearance Hub

One system that merges the Registrar, Library, Accounting and Student Affairs data into a single **CLEARED / HOLD** status per student.
IT312 Final Project, Track A. FastAPI + SQLite. All data is synthetic.

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
3. `python generate_keys.py`  (creates your own `.env`; never commit it)
4. `git status`  (`.env` must NOT be listed)

## Run
- **Mock Registrar** (port 8001): `python run_mock_registrar.py`
- **Hub** (port 8000): `uvicorn app.main:app --reload --port 8000`, then open http://127.0.0.1:8000/docs
- **Tests:** `pytest`

## What is where (inside `hub/`)
| Path | What | Owner |
|---|---|---|
| `app/` | The Hub code | see TASKS.md |
| `app/routes/` | API endpoints | API dev |
| `app/security/` | Login, roles, masking, signatures, audit log | Security |
| `app/importers/` | Library XML + Accounting CSV adapters | Data |
| `scripts/` | Automation script | Data |
| `client/` | Student / staff / admin screens | Front-end/QA |
| `tests/` | pytest tests | Front-end/QA (all add tests) |
| `db/schema.sql` | Database tables | API dev |
| `docs/` | API contract, design, mapping spec | API dev / Lead / Data |
| `generate_keys.py`, `run_mock_registrar.py` | Setup helpers | |
| `registrar_mock_api.py`, `registrar_students.json`, `verify_manifest.py`, `drop_folder/`, `tamper_tests/` | Instructor starter kit (leave as is) | |

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
