-- DNSC e-Clearance Hub — Database Schema
-- SQLite version

PRAGMA foreign_keys = ON;

-- Students table — master list from Registrar
CREATE TABLE IF NOT EXISTS students (
    student_id TEXT PRIMARY KEY,
    program_code TEXT NOT NULL,
    year_level INTEGER NOT NULL,
    status TEXT NOT NULL, -- ENROLLED, ON_LEAVE, SUSPENDED, GRADUATED
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Clearance status — per student, per academic term
CREATE TABLE IF NOT EXISTS clearance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    academic_term TEXT NOT NULL, -- e.g., "2026-2027-1"
    status TEXT NOT NULL DEFAULT 'PENDING', -- PENDING, CLEARED, HOLD
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
    UNIQUE(student_id, academic_term)
);

-- Clearance reasons — why a student is ON HOLD
CREATE TABLE IF NOT EXISTS clearance_reasons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clearance_id INTEGER NOT NULL,
    reason_code TEXT NOT NULL, -- UNPAID_FINES, UNRETURNED_BOOKS, etc.
    reason_detail TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (clearance_id) REFERENCES clearance(id) ON DELETE CASCADE
);

-- Offices — Library, Finance, Student Affairs, etc.
CREATE TABLE IF NOT EXISTS offices (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    head_email TEXT,
    requires_clearance BOOLEAN DEFAULT 1
);

-- Office clearance status per student
CREATE TABLE IF NOT EXISTS office_clearance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    office_code TEXT NOT NULL,
    academic_term TEXT NOT NULL,
    is_cleared BOOLEAN DEFAULT 0,
    notes TEXT,
    cleared_at TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
    FOREIGN KEY (office_code) REFERENCES offices(code) ON DELETE CASCADE,
    UNIQUE(student_id, office_code, academic_term)
);

-- Audit log — track who changed what and when
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT,
    old_value TEXT,
    new_value TEXT,
    ip_address TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Seed: default offices
INSERT OR IGNORE INTO offices (code, name) VALUES
('LIB', 'Library'),
('FIN', 'Finance Office'),
('SA', 'Student Affairs'),
('REG', 'Registrar');
