"""Mapping tests (Data engineer, R9/R17): Library XML and Accounting CSV adapters.

They read the real starter files in drop_folder/ and registrar_students.json, so no .env,
no server and no database are needed.
"""
import json
from datetime import date
from pathlib import Path

import pytest

from app.importers.accounting_csv import parse_accounting_csv
from app.importers.common import AdapterError, parse_count, parse_date, parse_money
from app.importers.library_xml import parse_library_xml

HUB = Path(__file__).resolve().parent.parent
EXPORT_DATE = date(2026, 11, 20)

REGISTRAR_IDS = {
    s["student_id"]
    for s in json.loads((HUB / "registrar_students.json").read_text(encoding="utf-8"))["students"]
}
LIBRARY = parse_library_xml((HUB / "drop_folder" / "library_export_2026-11-20.xml").read_bytes(), REGISTRAR_IDS)
ACCOUNTING = parse_accounting_csv(
    (HUB / "drop_folder" / "accounting_balances_2026-11-20.csv").read_bytes(), REGISTRAR_IDS, EXPORT_DATE
)


def rejects_by_ref(result):
    return {r["row_ref"]: r for r in result.rejects}


def library_xml(*borrowers):
    return ('<borrowers exported="2026-11-20">' + "".join(borrowers) + "</borrowers>").encode()


def borrower(card="LIB-9001", student_no="2023-59928", name="MORALES, Rhea B.", program="BSA",
             last="10/27/2026", books="0", fines="0.00"):
    return (f'<borrower card="{card}"><name>{name}</name><studentNo>{student_no}</studentNo>'
            f"<program>{program}</program><lastBorrowed>{last}</lastBorrowed>"
            f"<unreturnedBooks>{books}</unreturnedBooks><unpaidFines>{fines}</unpaidFines></borrower>")


def accounting_csv(*lines):
    header = "StudentNo,Name,Term,Assessed,Paid,Balance,LastPaymentDate"
    return ("\r\n".join([header, *lines]) + "\r\n").encode()


# ---------------------------------------------------------------- helpers
def test_money_thousands_separator_becomes_centavos():
    assert parse_money("10,450.50") == (1045050, None)


def test_money_plain_and_short_decimals():
    assert parse_money("40.50") == (4050, None)
    assert parse_money("5") == (500, None)
    assert parse_money("0.00") == (0, None)


def test_money_rejects_text_negative_and_bad_commas():
    assert parse_money("abc") == (None, "BAD_AMOUNT")
    assert parse_money("") == (None, "BAD_AMOUNT")
    assert parse_money(None) == (None, "BAD_AMOUNT")
    assert parse_money("1,23,456.00") == (None, "BAD_AMOUNT")
    assert parse_money("1.234") == (None, "BAD_AMOUNT")
    assert parse_money("-5.00") == (None, "NEGATIVE_AMOUNT")


def test_count_rules():
    assert parse_count("2") == (2, None)
    assert parse_count("x") == (None, "BAD_AMOUNT")
    assert parse_count("-1") == (None, "NEGATIVE_AMOUNT")


def test_date_rules():
    assert parse_date("10/27/2026", "US") == date(2026, 10, 27)
    assert parse_date("31/09/2026", "US") is None
    assert parse_date("2026-13-01", "ISO") is None
    assert parse_date("2026-10-27", "ISO") == date(2026, 10, 27)
    assert parse_date("2026-10-27", "US") is None


# ---------------------------------------------------------------- Library: starter file
def test_library_counts_match_starter_file():
    assert LIBRARY.total_rows == 29
    assert LIBRARY.accepted_count == 25
    assert LIBRARY.rejected_count == 4
    assert LIBRARY.accepted_count + LIBRARY.rejected_count == LIBRARY.total_rows


def test_library_reject_reasons():
    got = {ref: r["reason_code"] for ref, r in rejects_by_ref(LIBRARY).items()}
    assert got == {
        "LIB-0026": "NOT_IN_REGISTRAR",   # also has a bad name; first problem found wins
        "LIB-0027": "BAD_STUDENT_NO",
        "LIB-0028": "NOT_IN_REGISTRAR",   # also unknown program and impossible date
        "LIB-0029": "NEGATIVE_AMOUNT",
    }


def test_library_reject_keeps_every_problem_found():
    assert rejects_by_ref(LIBRARY)["LIB-0028"]["reasons"] == [
        "NOT_IN_REGISTRAR", "UNKNOWN_PROGRAM", "BAD_DATE"]


def test_library_duplicate_student_keeps_the_valid_row():
    kept = [r for r in LIBRARY.accepted if r["student_id"] == "2023-59928"]
    assert len(kept) == 1 and kept[0]["card_no"] == "LIB-0001"


def test_library_accepted_row_is_unified_schema():
    row = next(r for r in LIBRARY.accepted if r["card_no"] == "LIB-0002")
    assert row == {"card_no": "LIB-0002", "student_id": "2025-81367", "unreturned_books": 1,
                   "unpaid_fines": 4050, "last_borrowed": "2026-09-09"}


def test_library_accepted_students_are_all_in_registrar_and_unique():
    ids = [r["student_id"] for r in LIBRARY.accepted]
    assert set(ids) <= REGISTRAR_IDS and len(ids) == len(set(ids))


# ---------------------------------------------------------------- Library: small cases
def test_library_conflicting_duplicates_are_all_rejected():
    data = library_xml(borrower(card="LIB-1", books="0"), borrower(card="LIB-2", books="3"))
    result = parse_library_xml(data, REGISTRAR_IDS)
    assert result.accepted_count == 0
    assert [r["reason_code"] for r in result.rejects] == ["DATA_CONFLICT", "DATA_CONFLICT"]


def test_library_identical_duplicates_keep_first_reject_rest():
    data = library_xml(borrower(card="LIB-1"), borrower(card="LIB-2"))
    result = parse_library_xml(data, REGISTRAR_IDS)
    assert [r["card_no"] for r in result.accepted] == ["LIB-1"]
    assert [r["reason_code"] for r in result.rejects] == ["DUPLICATE"]


def test_library_empty_last_borrowed_is_allowed():
    result = parse_library_xml(library_xml(borrower(last="")), REGISTRAR_IDS)
    assert result.accepted[0]["last_borrowed"] is None


def test_library_missing_fields_are_rejected_not_crashed():
    data = b'<borrowers><borrower card="LIB-5"><studentNo>2023-59928</studentNo></borrower></borrowers>'
    result = parse_library_xml(data, REGISTRAR_IDS)
    assert result.accepted_count == 0
    assert result.rejects[0]["reasons"] == ["BAD_NAME", "UNKNOWN_PROGRAM", "BAD_AMOUNT"]


def test_library_broken_xml_raises_adapter_error():
    with pytest.raises(AdapterError):
        parse_library_xml(b"<borrowers><borrower>", REGISTRAR_IDS)


def test_library_wrong_root_raises_adapter_error():
    with pytest.raises(AdapterError):
        parse_library_xml(b"<students></students>", REGISTRAR_IDS)


def test_library_xml_entity_attack_is_blocked():
    evil = (b'<?xml version="1.0"?><!DOCTYPE b [<!ENTITY x "boom">]>'
            b"<borrowers><borrower card='L'><name>&x;</name></borrower></borrowers>")
    with pytest.raises(AdapterError):
        parse_library_xml(evil, REGISTRAR_IDS)


# ---------------------------------------------------------------- Accounting: starter file
def test_accounting_counts_match_starter_file():
    assert ACCOUNTING.total_rows == 42
    assert ACCOUNTING.accepted_count == 37
    assert ACCOUNTING.rejected_count == 5
    assert ACCOUNTING.accepted_count + ACCOUNTING.rejected_count == ACCOUNTING.total_rows


def test_accounting_reject_reasons():
    got = {ref: r["reason_code"] for ref, r in rejects_by_ref(ACCOUNTING).items()}
    assert got == {
        "line 7": "FUTURE_DATE",
        "line 13": "FUTURE_DATE",
        "line 25": "FUTURE_DATE",
        "line 42": "NOT_IN_REGISTRAR",
        "line 43": "BAD_AMOUNT",
    }


def test_accounting_corrupted_row_keeps_every_problem_found():
    assert rejects_by_ref(ACCOUNTING)["line 43"]["reasons"] == ["BAD_AMOUNT", "BAD_DATE"]


def test_accounting_thousands_separator_row_is_converted():
    row = next(r for r in ACCOUNTING.accepted if r["student_id"] == "2025-93355")
    assert row == {"student_id": "2025-93355", "term": "1S 2026-2027", "assessed": 1045050,
                   "paid": 0, "balance": 1045050, "last_payment_date": None}


def test_accounting_duplicate_student_keeps_the_valid_row():
    kept = [r for r in ACCOUNTING.accepted if r["student_id"] == "2024-45481"]
    assert len(kept) == 1 and kept[0]["balance"] == 0


def test_accounting_future_date_students_end_up_with_no_record():
    accepted_ids = {r["student_id"] for r in ACCOUNTING.accepted}
    assert not {"2025-81367", "2026-19950", "2023-21256"} & accepted_ids


# ---------------------------------------------------------------- Accounting: small cases
def test_accounting_payment_on_export_date_is_allowed():
    line = '2023-59928,"Morales, Rhea",1S 2026-2027,"1,000.00",0.00,"1,000.00",2026-11-20'
    assert parse_accounting_csv(accounting_csv(line), REGISTRAR_IDS, EXPORT_DATE).accepted_count == 1


def test_accounting_conflicting_duplicates_are_all_rejected():
    a = '2023-59928,"Morales, Rhea",1S 2026-2027,"1,000.00",0.00,"1,000.00",'
    b = '2023-59928,"Morales, Rhea",1S 2026-2027,"1,000.00","1,000.00",0.00,2026-11-01'
    result = parse_accounting_csv(accounting_csv(a, b), REGISTRAR_IDS, EXPORT_DATE)
    assert result.accepted_count == 0
    assert [r["reason_code"] for r in result.rejects] == ["DATA_CONFLICT", "DATA_CONFLICT"]


def test_accounting_short_row_is_rejected_not_crashed():
    result = parse_accounting_csv(accounting_csv("2023-59928,Morales"), REGISTRAR_IDS, EXPORT_DATE)
    assert result.accepted_count == 0 and result.rejects[0]["reason_code"] == "BAD_AMOUNT"


def test_accounting_missing_column_raises_adapter_error():
    with pytest.raises(AdapterError):
        parse_accounting_csv(b"StudentNo,Name\r\n2023-59928,x\r\n", REGISTRAR_IDS, EXPORT_DATE)


def test_accounting_non_utf8_raises_adapter_error():
    with pytest.raises(AdapterError):
        parse_accounting_csv(b"\xff\xfe\x00bad", REGISTRAR_IDS, EXPORT_DATE)