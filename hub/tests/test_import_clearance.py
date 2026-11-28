"""Stage 2 tests (Data engineer, R9/R14/R17): manifest check, saving to SQLite, CLEARED/HOLD rules.

Each test builds its own throw-away database in memory from db/schema.sql (the agreed schema),
loads the 40 Registrar students from registrar_students.json and imports the real starter files.
No .env, server or Registrar API is needed.
"""
import hashlib
import hmac
import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

import app.db
from app.clearance import evaluate_clearance, get_clearance, recompute
from app.importers.manifest import ManifestError, verify_manifest
from app.importers.service import ImportBlocked, import_file

HUB = Path(__file__).resolve().parent.parent
DROP = HUB / "drop_folder"
LIB = DROP / "library_export_2026-11-20.xml"
ACC = DROP / "accounting_balances_2026-11-20.csv"
TAMPERED = HUB / "tamper_tests" / "accounting_balances_2026-11-20.csv"
STARTER_KEY = "it312-starter-demo-key-change-me"   # public demo key from the starter kit
TEST_KEY = "unit-test-key-not-a-secret"


# ------------------------------------------------------------------ helpers
def make_db(load_students=True):
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")          # so wrong inserts fail loudly in tests
    conn.executescript((HUB / "db" / "schema.sql").read_text(encoding="utf-8"))
    if load_students:
        students = json.loads((HUB / "registrar_students.json").read_text(encoding="utf-8"))["students"]
        for s in students:
            conn.execute(
                "INSERT INTO students VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '2026-11-20T22:30:00+08:00')",
                (s["student_id"], s["last_name"], s["first_name"], s["middle_initial"], s["program_code"],
                 s["program_name"], s["year_level"], s["email"], s["status"]))
        conn.commit()
    return conn


def starter_db():
    conn = make_db()
    assert import_file(conn, LIB, "LIBRARY", STARTER_KEY)["status"] == "ACCEPTED"
    assert import_file(conn, ACC, "ACCOUNTING", STARTER_KEY)["status"] == "ACCEPTED"
    return conn


def sign(fields, key=TEST_KEY):
    body = json.dumps(fields, sort_keys=True, separators=(",", ":")).encode()
    return {**fields, "signature": hmac.new(key.encode(), body, hashlib.sha256).hexdigest()}


def manifest_for(data, source="library", count=1, nonce="n-1", key=TEST_KEY):
    return sign({"file": "x", "source": source, "sha256": hashlib.sha256(data).hexdigest(),
                 "record_count": count, "created_at": "2026-11-27T22:00:00+08:00", "nonce": nonce}, key)


def write_signed(folder, name, data, source, count, nonce, key=TEST_KEY):
    path = Path(folder) / name
    path.write_bytes(data)
    (Path(folder) / (name + ".manifest.json")).write_text(
        json.dumps(manifest_for(data, source.lower(), count, nonce, key)), encoding="utf-8")
    return path


def lib_xml(*rows):
    items = "".join(
        f'<borrower card="{c}"><name>MORALES, Rhea B.</name><studentNo>{s}</studentNo><program>BSA</program>'
        f"<lastBorrowed>10/27/2026</lastBorrowed><unreturnedBooks>{b}</unreturnedBooks>"
        f"<unpaidFines>{f}</unpaidFines></borrower>" for c, s, b, f in rows)
    return f'<borrowers exported="2026-11-27">{items}</borrowers>'.encode()


def offices(conn, student_id):
    data = get_clearance(conn, student_id)
    return {o["office"]: (o["status"], o["reason"]) for o in data["offices"]}, data["overall"]


# ------------------------------------------------------------------ manifest check (R14)
def test_manifest_valid():
    data = b"hello"
    m = verify_manifest(data, json.dumps(manifest_for(data)).encode(), TEST_KEY, "LIBRARY")
    assert m.source == "LIBRARY" and m.record_count == 1 and str(m.export_date) == "2026-11-27"


def test_manifest_wrong_key_is_signature_invalid():
    data = b"hello"
    with pytest.raises(ManifestError) as err:
        verify_manifest(data, json.dumps(manifest_for(data)).encode(), "another-key", "LIBRARY")
    assert err.value.code == "SIGNATURE_INVALID"


def test_manifest_edited_field_is_signature_invalid():
    data = b"hello"
    m = manifest_for(data)
    m["record_count"] = 999
    with pytest.raises(ManifestError) as err:
        verify_manifest(data, json.dumps(m).encode(), TEST_KEY, "LIBRARY")
    assert err.value.code == "SIGNATURE_INVALID"


def test_manifest_changed_file_is_hash_mismatch():
    manifest = json.dumps(manifest_for(b"hello")).encode()
    with pytest.raises(ManifestError) as err:
        verify_manifest(b"hello!", manifest, TEST_KEY, "LIBRARY")
    assert err.value.code == "HASH_MISMATCH"


def test_manifest_not_json_is_bad_manifest():
    with pytest.raises(ManifestError) as err:
        verify_manifest(b"x", b"not json", TEST_KEY, "LIBRARY")
    assert err.value.code == "BAD_MANIFEST"


def test_manifest_wrong_source_is_bad_manifest():
    data = b"hello"
    with pytest.raises(ManifestError) as err:
        verify_manifest(data, json.dumps(manifest_for(data, source="accounting")).encode(), TEST_KEY, "LIBRARY")
    assert err.value.code == "BAD_MANIFEST"


# ------------------------------------------------------------------ importing the starter files
def test_starter_files_are_saved():
    conn = make_db()
    lib = import_file(conn, LIB, "LIBRARY", STARTER_KEY)
    acc = import_file(conn, ACC, "ACCOUNTING", STARTER_KEY)
    assert (lib["accepted_rows"], lib["rejected_rows"]) == (25, 4)
    assert (acc["accepted_rows"], acc["rejected_rows"]) == (37, 5)
    count = lambda t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    assert (count("library_records"), count("accounting_records"), count("import_rejects")) == (25, 37, 9)
    assert conn.execute("SELECT status FROM import_files").fetchall() == [("ACCEPTED",), ("ACCEPTED",)]


def test_rejects_are_logged_with_reason_and_row():
    conn = starter_db()
    row = conn.execute("SELECT reason_code, raw_data FROM import_rejects WHERE row_ref = 'LIB-0027'").fetchone()
    assert row[0] == "BAD_STUDENT_NO"
    assert json.loads(row[1])["row"]["studentNo"] == "2026-1234"


def test_money_is_saved_as_centavos():
    conn = starter_db()
    row = conn.execute("SELECT assessed, balance FROM accounting_records WHERE student_id = '2025-93355'").fetchone()
    assert row == (1045050, 1045050)


def test_tampered_file_is_rejected_and_nothing_is_saved():
    conn = make_db()
    result = import_file(conn, TAMPERED, "ACCOUNTING", STARTER_KEY)
    assert (result["status"], result["reject_reason"]) == ("REJECTED", "HASH_MISMATCH")
    assert conn.execute("SELECT COUNT(*) FROM accounting_records").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM import_rejects").fetchone()[0] == 0
    row = conn.execute("SELECT status, reject_reason FROM import_files").fetchone()
    assert row == ("REJECTED", "HASH_MISMATCH")


def test_rejected_file_does_not_block_the_genuine_file():
    conn = make_db()
    assert import_file(conn, TAMPERED, "ACCOUNTING", STARTER_KEY)["status"] == "REJECTED"
    assert import_file(conn, ACC, "ACCOUNTING", STARTER_KEY)["status"] == "ACCEPTED"


def test_replayed_file_is_rejected():
    conn = starter_db()
    again = import_file(conn, ACC, "ACCOUNTING", STARTER_KEY)
    assert (again["status"], again["reject_reason"]) == ("REJECTED", "REPLAY")
    assert conn.execute("SELECT COUNT(*) FROM accounting_records").fetchone()[0] == 37


def test_wrong_key_rejects_the_whole_file():
    conn = make_db()
    result = import_file(conn, LIB, "LIBRARY", TEST_KEY)
    assert result["reject_reason"] == "SIGNATURE_INVALID"
    assert conn.execute("SELECT COUNT(*) FROM library_records").fetchone()[0] == 0


def test_missing_manifest_is_rejected():
    conn = make_db()
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "library.xml"
        path.write_bytes(lib_xml(("LIB-1", "2023-59928", 0, "0.00")))
        assert import_file(conn, path, "LIBRARY", TEST_KEY)["reject_reason"] == "BAD_MANIFEST"


def test_record_count_mismatch_is_rejected():
    conn = make_db()
    with tempfile.TemporaryDirectory() as folder:
        path = write_signed(folder, "l.xml", lib_xml(("LIB-1", "2023-59928", 0, "0.00")), "LIBRARY", 5, "n-a")
        assert import_file(conn, path, "LIBRARY", TEST_KEY)["reject_reason"] == "RECORD_COUNT_MISMATCH"


def test_unreadable_file_is_rejected_whole():
    conn = make_db()
    with tempfile.TemporaryDirectory() as folder:
        path = write_signed(folder, "l.xml", b"<borrowers><borrower>", "LIBRARY", 1, "n-b")
        assert import_file(conn, path, "LIBRARY", TEST_KEY)["reject_reason"] == "UNREADABLE_FILE"


def test_import_is_blocked_when_registrar_list_is_not_loaded():
    conn = make_db(load_students=False)
    with pytest.raises(ImportBlocked):
        import_file(conn, LIB, "LIBRARY", STARTER_KEY)


def test_conflicting_rows_become_needs_review():
    conn = make_db()
    with tempfile.TemporaryDirectory() as folder:
        data = lib_xml(("LIB-1", "2023-59928", 0, "0.00"), ("LIB-2", "2023-59928", 3, "0.00"))
        path = write_signed(folder, "l.xml", data, "LIBRARY", 2, "n-c")
        result = import_file(conn, path, "LIBRARY", TEST_KEY)
    assert (result["accepted_rows"], result["rejected_rows"]) == (0, 2)
    assert offices(conn, "2023-59928")[0]["LIBRARY"] == ("HOLD", "NEEDS_REVIEW")


def test_card_number_used_by_another_student_is_rejected_not_overwritten():
    conn = make_db()
    with tempfile.TemporaryDirectory() as folder:
        data = lib_xml(("LIB-1", "2023-59928", 0, "0.00"), ("LIB-1", "2026-29417", 1, "0.00"))
        result = import_file(conn, write_signed(folder, "l.xml", data, "LIBRARY", 2, "n-d"), "LIBRARY", TEST_KEY)
    assert (result["accepted_rows"], result["rejected_rows"]) == (1, 1)
    assert conn.execute("SELECT student_id FROM library_records WHERE card_no = 'LIB-1'").fetchone()[0] == "2023-59928"


# ------------------------------------------------------------------ CLEARED / HOLD rules
def test_loa_student_is_on_hold_everywhere():
    offs, overall = offices(starter_db(), "2025-81367")
    assert overall == "HOLD"
    assert set(offs.values()) == {("HOLD", "ON_LOA")}


def test_student_with_books_and_no_accounting_record():
    offs, _ = offices(starter_db(), "2026-19950")
    assert offs["LIBRARY"] == ("HOLD", "UNRETURNED_BOOKS")
    assert offs["ACCOUNTING"] == ("HOLD", "NO_ACCOUNTING_RECORD")     # FUTURE_DATE row was rejected
    assert offs["STUDENT_AFFAIRS"] == ("CLEARED", None)


def test_unpaid_fines_only():
    offs, _ = offices(starter_db(), "2025-38684")
    assert offs["LIBRARY"] == ("HOLD", "UNPAID_FINES")


def test_no_library_record_means_cleared_and_balance_means_hold():
    offs, overall = offices(starter_db(), "2025-93355")
    assert offs["LIBRARY"] == ("CLEARED", None)
    assert offs["ACCOUNTING"] == ("HOLD", "BALANCE_DUE")
    assert overall == "HOLD"


def test_fully_cleared_student():
    offs, overall = offices(starter_db(), "2026-29417")
    assert overall == "CLEARED"
    assert all(status == "CLEARED" for status, _ in offs.values())


def test_outstanding_affairs_record_puts_student_on_hold():
    conn = starter_db()
    conn.execute("INSERT INTO users (username, password_hash, role, office_code, created_at) "
                 "VALUES ('sa', 'x', 'staff', 'STUDENT_AFFAIRS', '2026-11-28T10:00:00+08:00')")
    conn.execute("INSERT INTO affairs_records (student_id, record_type, description, outstanding, entered_by, "
                 "entered_at) VALUES ('2026-29417', 'EQUIPMENT', 'Projector', 1, 1, '2026-11-28T10:00:00+08:00')")
    recompute(conn, ["2026-29417"], {"STUDENT_AFFAIRS": {"2026-29417"}})
    assert offices(conn, "2026-29417") == ({"LIBRARY": ("CLEARED", None), "ACCOUNTING": ("CLEARED", None),
                                            "STUDENT_AFFAIRS": ("HOLD", "AFFAIRS_OUTSTANDING")}, "HOLD")


def test_all_40_students_match_an_independent_calculation():
    """Recompute every expected answer straight from the Stage 1 adapter output."""
    from app.importers.accounting_csv import parse_accounting_csv
    from app.importers.library_xml import parse_library_xml
    from datetime import date

    students = json.loads((HUB / "registrar_students.json").read_text(encoding="utf-8"))["students"]
    ids = {s["student_id"] for s in students}
    lib = {r["student_id"]: r for r in parse_library_xml(LIB.read_bytes(), ids).accepted}
    acc = {r["student_id"]: r for r in parse_accounting_csv(ACC.read_bytes(), ids, date(2026, 11, 20)).accepted}
    conn = starter_db()
    cleared = 0
    for s in students:
        sid = s["student_id"]
        if s["status"] == "LOA":
            want = {"LIBRARY": ("HOLD", "ON_LOA"), "ACCOUNTING": ("HOLD", "ON_LOA"),
                    "STUDENT_AFFAIRS": ("HOLD", "ON_LOA")}
        else:
            l, a = lib.get(sid), acc.get(sid)
            want = {
                "LIBRARY": (("HOLD", "UNRETURNED_BOOKS") if l and l["unreturned_books"] > 0 else
                            ("HOLD", "UNPAID_FINES") if l and l["unpaid_fines"] > 0 else ("CLEARED", None)),
                "ACCOUNTING": (("HOLD", "NO_ACCOUNTING_RECORD") if a is None else
                               ("HOLD", "BALANCE_DUE") if a["balance"] > 0 else ("CLEARED", None)),
                "STUDENT_AFFAIRS": ("CLEARED", None),
            }
        offs, overall = offices(conn, sid)
        assert offs == want, sid
        assert overall == ("CLEARED" if all(v[0] == "CLEARED" for v in want.values()) else "HOLD")
        cleared += overall == "CLEARED"
    assert cleared == 11
    assert conn.execute("SELECT COUNT(*) FROM clearance_overall WHERE overall_status = 'CLEARED'").fetchone()[0] == 11


# ------------------------------------------------------------------ manual decisions (decision 7)
def manual_clear(conn, student_id, office):
    conn.execute("INSERT INTO users (username, password_hash, role, office_code, created_at) "
                 "VALUES ('lib', 'x', 'staff', 'LIBRARY', '2026-11-28T10:00:00+08:00')")
    conn.execute("UPDATE clearance_status SET status = 'CLEARED', reason = NULL, source = 'MANUAL', "
                 "updated_by = 1 WHERE student_id = ? AND office_code = ?", (student_id, office))


def test_manual_decision_survives_a_recompute():
    conn = starter_db()
    manual_clear(conn, "2026-19950", "LIBRARY")                       # staff clears a student with books
    assert recompute(conn) == []
    assert offices(conn, "2026-19950")[0]["LIBRARY"] == ("CLEARED", None)


def test_newer_import_that_changes_the_data_replaces_the_manual_decision():
    conn = starter_db()
    manual_clear(conn, "2026-19950", "LIBRARY")
    with tempfile.TemporaryDirectory() as folder:
        data = lib_xml(("LIB-0060", "2026-19950", 3, "0.00"))         # was 2 books, now 3: data changed
        path = write_signed(folder, "l.xml", data, "LIBRARY", 1, "n-e")
        result = import_file(conn, path, "LIBRARY", TEST_KEY)
    assert [r["student_id"] for r in result["replaced_manual"]] == ["2026-19950"]
    assert offices(conn, "2026-19950")[0]["LIBRARY"] == ("HOLD", "UNRETURNED_BOOKS")
    assert conn.execute("SELECT COUNT(*) FROM library_records WHERE student_id = '2026-19950'").fetchone()[0] == 1


# ------------------------------------------------------------------ route compatibility
def test_evaluate_clearance_still_works_for_the_existing_route():
    conn = starter_db()
    with tempfile.TemporaryDirectory() as folder:
        disk = Path(folder) / "test.db"
        target = sqlite3.connect(disk)
        conn.backup(target)
        target.close()
        old_path = app.db.DB_PATH
        app.db.DB_PATH = disk
        try:
            result = evaluate_clearance({"student_id": "2025-93355", "status": "ENROLLED"})
        finally:
            app.db.DB_PATH = old_path
    assert result == {"student_id": "2025-93355", "status": "HOLD", "reasons": ["BALANCE_DUE"]}