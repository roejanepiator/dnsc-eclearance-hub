-- DNSC e-Clearance Hub: SQLite schema (v1 draft)
-- Conventions:
--   * Money is stored as INTEGER centavos (1500.00 -> 150000). Never use REAL for money.
--   * Dates are ISO-8601 text (YYYY-MM-DD); timestamps are ISO-8601 with offset.
--   * All access from Python MUST use parameterized queries (R13).
-- Apply with:  sqlite3 hub.db < schema.sql   (and run PRAGMA foreign_keys=ON per connection)

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------
-- Reference data
-- ---------------------------------------------------------------
-- Offices that sign a clearance. Registrar is the master record, not a signing office.
CREATE TABLE offices (
    code  TEXT PRIMARY KEY CHECK (code IN ('LIBRARY','ACCOUNTING','STUDENT_AFFAIRS')),
    name  TEXT NOT NULL
);

-- Library uses codes like BSED-MATH; the Registrar uses EDMATH. Map them here.
CREATE TABLE program_crosswalk (
    source          TEXT NOT NULL CHECK (source IN ('LIBRARY','ACCOUNTING')),
    source_code     TEXT NOT NULL,
    registrar_code  TEXT NOT NULL,
    PRIMARY KEY (source, source_code)
);

-- ---------------------------------------------------------------
-- Master record (synced from Registrar API, R5)
-- ---------------------------------------------------------------
CREATE TABLE students (
    student_id     TEXT PRIMARY KEY CHECK (student_id GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9][0-9]'),
    last_name      TEXT NOT NULL,
    first_name     TEXT NOT NULL,
    middle_initial TEXT,
    program_code   TEXT NOT NULL,
    program_name   TEXT,
    year_level     INTEGER CHECK (year_level BETWEEN 1 AND 6),
    email          TEXT,
    status         TEXT NOT NULL CHECK (status IN ('ENROLLED','LOA')),
    synced_at      TEXT NOT NULL
);

-- ---------------------------------------------------------------
-- Users and login (R11, R12)
-- ---------------------------------------------------------------
CREATE TABLE users (
    user_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,                 -- bcrypt/argon2 output, never plaintext
    role            TEXT NOT NULL CHECK (role IN ('student','staff','admin')),
    office_code     TEXT REFERENCES offices(code), -- required for staff, NULL otherwise
    student_id      TEXT REFERENCES students(student_id), -- required for student accounts
    is_active       INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until    TEXT,
    created_at      TEXT NOT NULL,
    CHECK (role <> 'staff'   OR office_code IS NOT NULL),
    CHECK (role <> 'student' OR student_id  IS NOT NULL)
);

-- ---------------------------------------------------------------
-- Import tracking (R1, R2, R9, R14)
-- ---------------------------------------------------------------
CREATE TABLE import_files (
    import_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    source           TEXT NOT NULL CHECK (source IN ('LIBRARY','ACCOUNTING')),
    filename         TEXT NOT NULL,
    sha256           TEXT NOT NULL,
    nonce            TEXT NOT NULL UNIQUE,         -- UNIQUE blocks replay of an old signed file
    manifest_created TEXT NOT NULL,
    record_count     INTEGER NOT NULL,
    accepted_rows    INTEGER NOT NULL DEFAULT 0,
    rejected_rows    INTEGER NOT NULL DEFAULT 0,
    status           TEXT NOT NULL CHECK (status IN ('ACCEPTED','REJECTED')),
    reject_reason    TEXT,                         -- e.g. SIGNATURE_INVALID, HASH_MISMATCH, REPLAY
    imported_at      TEXT NOT NULL
);

-- Every rejected row (R2: "logging every reject")
CREATE TABLE import_rejects (
    reject_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    import_id   INTEGER NOT NULL REFERENCES import_files(import_id) ON DELETE CASCADE,
    row_ref     TEXT NOT NULL,                     -- card number, CSV line number, etc.
    reason_code TEXT NOT NULL,                     -- NOT_IN_REGISTRAR, BAD_DATE, BAD_AMOUNT, DUPLICATE, ...
    raw_data    TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

-- ---------------------------------------------------------------
-- Office records (unified schema after mapping)
-- ---------------------------------------------------------------
CREATE TABLE library_records (
    card_no           TEXT PRIMARY KEY,
    student_id        TEXT NOT NULL REFERENCES students(student_id),
    unreturned_books  INTEGER NOT NULL DEFAULT 0 CHECK (unreturned_books >= 0),
    unpaid_fines      INTEGER NOT NULL DEFAULT 0 CHECK (unpaid_fines >= 0),   -- centavos
    last_borrowed     TEXT,
    import_id         INTEGER NOT NULL REFERENCES import_files(import_id)
);

CREATE TABLE accounting_records (
    student_id        TEXT NOT NULL REFERENCES students(student_id),
    term              TEXT NOT NULL,
    assessed          INTEGER NOT NULL CHECK (assessed >= 0),                 -- centavos
    paid              INTEGER NOT NULL CHECK (paid >= 0),
    balance           INTEGER NOT NULL CHECK (balance >= 0),
    last_payment_date TEXT,
    import_id         INTEGER NOT NULL REFERENCES import_files(import_id),
    PRIMARY KEY (student_id, term)
);

-- Student Affairs staff enter these through the Hub (web form)
CREATE TABLE affairs_records (
    record_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id   TEXT NOT NULL REFERENCES students(student_id),
    record_type  TEXT NOT NULL CHECK (record_type IN ('ORG_MEMBERSHIP','EQUIPMENT')),
    description  TEXT NOT NULL,
    outstanding  INTEGER NOT NULL DEFAULT 1 CHECK (outstanding IN (0,1)),
    entered_by   INTEGER NOT NULL REFERENCES users(user_id),
    entered_at   TEXT NOT NULL,
    resolved_at  TEXT
);

-- ---------------------------------------------------------------
-- Clearance status (R3 / feature 3)
-- ---------------------------------------------------------------
CREATE TABLE clearance_status (
    student_id   TEXT NOT NULL REFERENCES students(student_id),
    office_code  TEXT NOT NULL REFERENCES offices(code),
    status       TEXT NOT NULL CHECK (status IN ('CLEARED','HOLD')),
    reason       TEXT,                              -- e.g. UNPAID_FINES, BALANCE_DUE, NO_RECORD, ON_LOA
    source       TEXT NOT NULL CHECK (source IN ('AUTO','MANUAL')),
    updated_by   INTEGER REFERENCES users(user_id), -- NULL when AUTO
    updated_at   TEXT NOT NULL,
    PRIMARY KEY (student_id, office_code)
);

-- Overall = CLEARED only when every office is CLEARED
CREATE VIEW clearance_overall AS
SELECT s.student_id,
       CASE WHEN (SELECT COUNT(*) FROM clearance_status c
                  WHERE c.student_id = s.student_id AND c.status = 'CLEARED') =
                 (SELECT COUNT(*) FROM offices)
            THEN 'CLEARED' ELSE 'HOLD' END AS overall_status
FROM students s;

-- ---------------------------------------------------------------
-- Deadline service (R6)
-- ---------------------------------------------------------------
CREATE TABLE holidays (
    holiday_date TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    fetched_at   TEXT NOT NULL
);

CREATE TABLE clearance_periods (
    period_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    term             TEXT NOT NULL UNIQUE,
    start_date       TEXT NOT NULL,
    nominal_deadline TEXT NOT NULL,                 -- before adjusting for holidays/weekends
    final_deadline   TEXT NOT NULL,                 -- after skipping PH holidays
    computed_at      TEXT NOT NULL
);

-- ---------------------------------------------------------------
-- Signed clearance slips (R15)
-- ---------------------------------------------------------------
CREATE TABLE clearance_slips (
    slip_id        TEXT PRIMARY KEY,                -- random UUID, goes in the QR code
    student_id     TEXT NOT NULL REFERENCES students(student_id),
    overall_status TEXT NOT NULL CHECK (overall_status IN ('CLEARED','HOLD')),
    payload_json   TEXT NOT NULL,                   -- exact canonical JSON that was signed
    signature      TEXT NOT NULL,                   -- HMAC-SHA256 hex
    issued_at      TEXT NOT NULL,
    expires_at     TEXT NOT NULL,
    revoked        INTEGER NOT NULL DEFAULT 0 CHECK (revoked IN (0,1))
);

-- ---------------------------------------------------------------
-- Automation runs (R1, R2: HOLD summary)
-- ---------------------------------------------------------------
CREATE TABLE job_runs (
    run_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    job_name     TEXT NOT NULL,                     -- 'nightly_import', 'registrar_sync', ...
    started_at   TEXT NOT NULL,
    finished_at  TEXT,
    status       TEXT NOT NULL CHECK (status IN ('RUNNING','SUCCESS','PARTIAL','FAILED')),
    summary_json TEXT                               -- counts: files accepted/rejected, HOLDs by office
);

-- ---------------------------------------------------------------
-- Audit log (R16). Tamper-evident: each entry hashes the previous one.
-- ---------------------------------------------------------------
CREATE TABLE audit_log (
    audit_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    ts           TEXT NOT NULL,
    actor_user   INTEGER REFERENCES users(user_id), -- NULL for system/script actions
    actor_role   TEXT,
    action       TEXT NOT NULL,                     -- LOGIN_OK, LOGIN_FAIL, SIGN_OFF, SET_HOLD, VIEW_STUDENT, EXPORT, IMPORT_REJECTED, ...
    target_type  TEXT,
    target_id    TEXT,                              -- store masked IDs only
    ip_address   TEXT,
    details      TEXT,
    prev_hash    TEXT NOT NULL,                     -- entry_hash of the previous row ('GENESIS' for first)
    entry_hash   TEXT NOT NULL                      -- SHA-256 over this row's fields + prev_hash
);

-- ---------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------
CREATE INDEX idx_library_student    ON library_records(student_id);
CREATE INDEX idx_affairs_student    ON affairs_records(student_id, outstanding);
CREATE INDEX idx_clearance_office   ON clearance_status(office_code, status);
CREATE INDEX idx_rejects_import     ON import_rejects(import_id);
CREATE INDEX idx_slips_student      ON clearance_slips(student_id);
CREATE INDEX idx_audit_ts           ON audit_log(ts);

-- ---------------------------------------------------------------
-- Seed data
-- ---------------------------------------------------------------
INSERT INTO offices (code, name) VALUES
    ('LIBRARY','Library'),
    ('ACCOUNTING','Accounting'),
    ('STUDENT_AFFAIRS','Student Affairs');

-- Verify these against the Registrar program names; BSHM intentionally left unmapped (reject).
INSERT INTO program_crosswalk (source, source_code, registrar_code) VALUES
    ('LIBRARY','BSA','AGRI'),
    ('LIBRARY','BSED-MATH','EDMATH'),
    ('LIBRARY','BSCRIM','CRIM'),
    ('LIBRARY','BSIT','IT'),
    ('LIBRARY','BSIS','IS');
