"""Import service (Data engineer, R1/R9/R14): verify the manifest, run the adapter, save to SQLite.

import_file() is the one function the automation script (Stage 3) and POST /imports/run call.
It never reads a record before the manifest passes, and it never leaves a half-saved import:
everything for one file is saved in ONE transaction.
"""
import hashlib
import json
import uuid
from pathlib import Path

from ..clearance import recompute
from .accounting_csv import parse_accounting_csv
from .common import AdapterError, make_reject, now_iso
from .library_xml import parse_library_xml
from .manifest import ManifestError, verify_manifest

SOURCES = ("LIBRARY", "ACCOUNTING")


class ImportBlocked(Exception):
    """The import cannot run at all (for example, the Registrar list is not loaded yet)."""


def _registrar_ids(conn):
    ids = {row[0] for row in conn.execute("SELECT student_id FROM students")}
    if not ids:
        raise ImportBlocked("students table is empty: load the Registrar list before importing")
    return ids


def _log_rejected_file(conn, source, filename, sha256, code, now, manifest=None):
    """Record a whole-file rejection. The nonce is a throwaway value: a rejected file must never
    'use up' the real nonce, or an attacker could block the genuine file."""
    with conn:
        cur = conn.execute(
            "INSERT INTO import_files (source, filename, sha256, nonce, manifest_created, record_count, "
            "accepted_rows, rejected_rows, status, reject_reason, imported_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 0, 0, 'REJECTED', ?, ?)",
            (source, filename, sha256, "rejected:" + uuid.uuid4().hex,
             manifest.created_at if manifest else now, manifest.record_count if manifest else 0,
             code, now))
    return {"import_id": cur.lastrowid, "source": source, "filename": filename, "status": "REJECTED",
            "reject_reason": code, "accepted_rows": 0, "rejected_rows": 0, "replaced_manual": []}


def import_file(conn, path, source, key, now=None):
    """Import one drop-folder file. Returns a summary dict (status ACCEPTED or REJECTED).

    conn    open sqlite3 connection (the caller turns on PRAGMA foreign_keys and closes it)
    path    the data file; its manifest must sit next to it as <path>.manifest.json
    source  "LIBRARY" or "ACCOUNTING"
    key     the HMAC key the manifest was signed with
    """
    source = source.upper()
    if source not in SOURCES:
        raise ValueError(f"source must be one of {SOURCES}")
    now = now or now_iso()
    path = Path(path)
    registrar_ids = _registrar_ids(conn)

    data = path.read_bytes()                     # read ONCE: the same bytes are hashed and parsed
    sha256 = hashlib.sha256(data).hexdigest()
    manifest_path = path.with_name(path.name + ".manifest.json")
    if not manifest_path.exists():
        return _log_rejected_file(conn, source, path.name, sha256, "BAD_MANIFEST", now)

    # 1. Manifest first (R14): signature, then hash.
    try:
        manifest = verify_manifest(data, manifest_path.read_bytes(), key, source)
    except ManifestError as exc:
        return _log_rejected_file(conn, source, path.name, sha256, exc.code, now)

    # 2. Replay: a nonce that was already accepted is never accepted again.
    if conn.execute("SELECT 1 FROM import_files WHERE nonce = ?", (manifest.nonce,)).fetchone():
        return _log_rejected_file(conn, source, path.name, sha256, "REPLAY", now, manifest)

    # 3. Adapter: map the rows (Stage 1 code).
    try:
        if source == "LIBRARY":
            result = parse_library_xml(data, registrar_ids)
        else:
            result = parse_accounting_csv(data, registrar_ids, manifest.export_date)
    except AdapterError:
        return _log_rejected_file(conn, source, path.name, sha256, "UNREADABLE_FILE", now, manifest)
    if result.total_rows != manifest.record_count:
        return _log_rejected_file(conn, source, path.name, sha256, "RECORD_COUNT_MISMATCH", now, manifest)

    # 4. Save everything for this file in one transaction.
    with conn:
        import_id = conn.execute(
            "INSERT INTO import_files (source, filename, sha256, nonce, manifest_created, record_count, "
            "accepted_rows, rejected_rows, status, reject_reason, imported_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 0, 0, 'ACCEPTED', NULL, ?)",
            (source, path.name, sha256, manifest.nonce, manifest.created_at,
             manifest.record_count, now)).lastrowid

        rejects = list(result.rejects)
        changed = set()                          # students whose underlying data changed
        saved = 0
        for record in result.accepted:
            sid = record["student_id"]
            if source == "LIBRARY":
                ok = _save_library(conn, record, import_id, changed)
            else:
                ok = _save_accounting(conn, record, import_id, changed)
            if ok:
                saved += 1
            else:                                # card number already belongs to another student
                rejects.append(make_reject(record["card_no"], ["DATA_CONFLICT"], sid, dict(record)))

        for r in rejects:
            raw = {"student_id": r["student_id"], "reasons": r["reasons"], "row": r["raw_data"]}
            conn.execute(
                "INSERT INTO import_rejects (import_id, row_ref, reason_code, raw_data, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (import_id, r["row_ref"], r["reason_code"], json.dumps(raw, ensure_ascii=False), now))

        conn.execute("UPDATE import_files SET accepted_rows = ?, rejected_rows = ? WHERE import_id = ?",
                     (saved, len(rejects), import_id))

        office = "LIBRARY" if source == "LIBRARY" else "ACCOUNTING"
        replaced = recompute(conn, changed={office: changed}, now=now)

    return {"import_id": import_id, "source": source, "filename": path.name, "status": "ACCEPTED",
            "reject_reason": None, "accepted_rows": saved, "rejected_rows": len(rejects),
            "replaced_manual": replaced}


def _save_library(conn, r, import_id, changed):
    """One Library row per student: a newer row replaces the old one (decision 5)."""
    sid = r["student_id"]
    clash = conn.execute("SELECT 1 FROM library_records WHERE card_no = ? AND student_id <> ?",
                         (r["card_no"], sid)).fetchone()
    if clash:
        return False
    old = conn.execute("SELECT unreturned_books, unpaid_fines FROM library_records WHERE student_id = ?",
                       (sid,)).fetchone()
    if old is None or tuple(old) != (r["unreturned_books"], r["unpaid_fines"]):
        changed.add(sid)
    conn.execute("DELETE FROM library_records WHERE student_id = ?", (sid,))
    conn.execute(
        "INSERT INTO library_records (card_no, student_id, unreturned_books, unpaid_fines, last_borrowed, "
        "import_id) VALUES (?, ?, ?, ?, ?, ?)",
        (r["card_no"], sid, r["unreturned_books"], r["unpaid_fines"], r["last_borrowed"], import_id))
    return True


def _save_accounting(conn, r, import_id, changed):
    """One Accounting row per student and term: a newer row replaces the old one."""
    sid = r["student_id"]
    old = conn.execute("SELECT assessed, paid, balance FROM accounting_records "
                       "WHERE student_id = ? AND term = ?", (sid, r["term"])).fetchone()
    if old is None or tuple(old) != (r["assessed"], r["paid"], r["balance"]):
        changed.add(sid)
    conn.execute(
        "INSERT OR REPLACE INTO accounting_records (student_id, term, assessed, paid, balance, "
        "last_payment_date, import_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (sid, r["term"], r["assessed"], r["paid"], r["balance"], r["last_payment_date"], import_id))
    return True