"""CLEARED / HOLD rules (Data engineer, feature 3). Single source of truth: docs/api_contract.md
sections 5 and 6. All functions take an open sqlite3 connection and never commit; the caller does.

Tables used (db/schema.sql): students, library_records, accounting_records, affairs_records,
import_files, import_rejects, clearance_status.
"""
import json

from .importers.common import now_iso

OFFICES = ("LIBRARY", "ACCOUNTING", "STUDENT_AFFAIRS")


# --------------------------------------------------------------------------- helpers
def current_term(conn):
    """The term whose balance counts: the latest clearance period, else the term of the newest import."""
    row = conn.execute("SELECT term FROM clearance_periods ORDER BY period_id DESC LIMIT 1").fetchone()
    if row:
        return row[0]
    row = conn.execute(
        "SELECT term FROM accounting_records ORDER BY import_id DESC, term DESC LIMIT 1").fetchone()
    return row[0] if row else None


def load_conflicts(conn):
    """Students whose rows disagreed (DATA_CONFLICT) in the newest ACCEPTED import of each source."""
    conflicts = {"LIBRARY": set(), "ACCOUNTING": set()}
    for source in conflicts:
        latest = conn.execute(
            "SELECT MAX(import_id) FROM import_files WHERE source = ? AND status = 'ACCEPTED'",
            (source,)).fetchone()[0]
        if latest is None:
            continue
        rows = conn.execute(
            "SELECT raw_data FROM import_rejects WHERE import_id = ? AND reason_code = 'DATA_CONFLICT'",
            (latest,)).fetchall()
        for (raw,) in rows:
            try:
                conflicts[source].add(json.loads(raw)["student_id"])
            except (ValueError, KeyError, TypeError):
                pass
    return conflicts


def compute_student_offices(conn, student_id, student_status, term, conflicts):
    """Apply the contract rules. Returns {office: (status, reason)}. Reads only, writes nothing."""
    if student_status == "LOA":                                   # decision 1
        return {o: ("HOLD", "ON_LOA") for o in OFFICES}

    result = {}

    # LIBRARY: no record = never borrowed = CLEARED (decision 2)
    if student_id in conflicts["LIBRARY"]:                        # decision 5
        result["LIBRARY"] = ("HOLD", "NEEDS_REVIEW")
    else:
        row = conn.execute(
            "SELECT unreturned_books, unpaid_fines FROM library_records WHERE student_id = ?",
            (student_id,)).fetchone()
        if row and row[0] > 0:
            result["LIBRARY"] = ("HOLD", "UNRETURNED_BOOKS")
        elif row and row[1] > 0:
            result["LIBRARY"] = ("HOLD", "UNPAID_FINES")
        else:
            result["LIBRARY"] = ("CLEARED", None)

    # ACCOUNTING: no record for the current term = HOLD (decision 3)
    if student_id in conflicts["ACCOUNTING"]:
        result["ACCOUNTING"] = ("HOLD", "NEEDS_REVIEW")
    else:
        row = None
        if term is not None:
            row = conn.execute(
                "SELECT balance FROM accounting_records WHERE student_id = ? AND term = ?",
                (student_id, term)).fetchone()
        if row is None:
            result["ACCOUNTING"] = ("HOLD", "NO_ACCOUNTING_RECORD")
        elif row[0] > 0:
            result["ACCOUNTING"] = ("HOLD", "BALANCE_DUE")
        else:
            result["ACCOUNTING"] = ("CLEARED", None)

    # STUDENT_AFFAIRS: any outstanding item = HOLD
    row = conn.execute(
        "SELECT 1 FROM affairs_records WHERE student_id = ? AND outstanding = 1 LIMIT 1",
        (student_id,)).fetchone()
    result["STUDENT_AFFAIRS"] = ("HOLD", "AFFAIRS_OUTSTANDING") if row else ("CLEARED", None)
    return result


# --------------------------------------------------------------------------- writing
def recompute(conn, student_ids=None, changed=None, now=None):
    """Recompute AUTO clearance_status rows (all students, or only student_ids).

    changed: {office: set(student_ids)} whose underlying data just changed. A MANUAL decision wins
             over AUTO (decision 7) UNLESS the student is listed in `changed` for that office.
    Returns the list of MANUAL decisions that were replaced, so the caller can write them to the
    audit log: [{student_id, office, manual_status, manual_reason, new_status, new_reason}].
    """
    changed = changed or {}
    now = now or now_iso()
    term = current_term(conn)
    conflicts = load_conflicts(conn)
    replaced = []

    students = conn.execute("SELECT student_id, status FROM students").fetchall()
    wanted = set(student_ids) if student_ids is not None else None
    for student_id, status in students:
        if wanted is not None and student_id not in wanted:
            continue
        computed = compute_student_offices(conn, student_id, status, term, conflicts)
        existing = {r[0]: r for r in conn.execute(
            "SELECT office_code, status, reason, source FROM clearance_status WHERE student_id = ?",
            (student_id,))}
        for office, (new_status, new_reason) in computed.items():
            old = existing.get(office)
            if old and old[3] == "MANUAL":
                if student_id not in changed.get(office, ()):
                    continue                                   # manual decision stays
                replaced.append({"student_id": student_id, "office": office,
                                 "manual_status": old[1], "manual_reason": old[2],
                                 "new_status": new_status, "new_reason": new_reason})
            elif old and old[1] == new_status and old[2] == new_reason:
                continue                                       # unchanged: keep its updated_at
            conn.execute(
                "INSERT OR REPLACE INTO clearance_status "
                "(student_id, office_code, status, reason, source, updated_by, updated_at) "
                "VALUES (?, ?, ?, ?, 'AUTO', NULL, ?)",
                (student_id, office, new_status, new_reason, now))
    return replaced


# --------------------------------------------------------------------------- reading
def get_clearance(conn, student_id, student_status=None):
    """One student's clearance in the shape of docs/api_contract.md endpoint 4, or None if unknown.

    Uses the saved clearance_status rows (so MANUAL decisions show); an office with no saved row
    is computed on the spot, so the answer is never empty.
    """
    if student_status is None:
        row = conn.execute("SELECT status FROM students WHERE student_id = ?", (student_id,)).fetchone()
        if row is None:
            return None
        student_status = row[0]
    saved = {r[0]: r for r in conn.execute(
        "SELECT office_code, status, reason, updated_at FROM clearance_status WHERE student_id = ?",
        (student_id,))}
    computed = compute_student_offices(conn, student_id, student_status,
                                       current_term(conn), load_conflicts(conn))
    offices = []
    for office in OFFICES:
        if office in saved:
            _, status, reason, updated_at = saved[office]
        else:
            (status, reason), updated_at = computed[office], None
        offices.append({"office": office, "status": status, "reason": reason, "updated_at": updated_at})
    overall = "CLEARED" if all(o["status"] == "CLEARED" for o in offices) else "HOLD"
    return {"student_id": student_id, "overall": overall, "offices": offices}


def evaluate_clearance(student):
    """Kept for routes/clearance.py (API dev), which calls evaluate_clearance(registrar_student).

    Same return shape as before ({student_id, status, reasons}) but the answer now comes from the
    real records in the database. The API dev can switch the route to get_clearance() later.
    """
    from .db import get_db  # imported here so this module can be tested with any connection

    with get_db() as conn:
        data = get_clearance(conn, student["student_id"], student.get("status") or "ENROLLED")
    return {
        "student_id": data["student_id"],
        "status": data["overall"],
        "reasons": [o["reason"] for o in data["offices"] if o["reason"]],
    }