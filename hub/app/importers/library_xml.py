"""Library adapter (Data engineer, R9): Library XML -> unified library_records rows.

Input : the raw bytes of the XML file + the set of student IDs from the Registrar masterlist.
Output: ImportResult(accepted=[...], rejects=[...]). Nothing is saved here (Stage 2 does that).
Rules : docs/mapping_spec.md section 2. Reject codes: docs/api_contract.md section 6.
"""
import re

from defusedxml import ElementTree as SafeET           # safe against XML attacks (XXE, entity bombs)
from defusedxml.common import DefusedXmlException

from .common import (
    STUDENT_ID_RE,
    AdapterError,
    ImportResult,
    add_reason,
    make_reject,
    parse_count,
    parse_date,
    parse_money,
    resolve_duplicates,
)

# Library program code -> Registrar program code. Keep in sync with the seed data in db/schema.sql.
# BSHM is deliberately missing: the Registrar has no such program, so those rows are rejected.
LIBRARY_PROGRAM_CROSSWALK = {
    "BSA": "AGRI",
    "BSED-MATH": "EDMATH",
    "BSCRIM": "CRIM",
    "BSIT": "IT",
    "BSIS": "IS",
}

# "LAST NAME, Given Names M."  (surname in capitals, optional middle initial with a dot)
_NAME_RE = re.compile(
    r"[A-ZÑ][A-ZÑ'\-]*(?: [A-ZÑ][A-ZÑ'\-]*)*"          # SURNAME (may have several words)
    r", "
    r"[A-ZÑ][A-Za-zÑñ'\-]*(?: [A-ZÑ][A-Za-zÑñ'\-]*)*"  # Given names
    r"(?: [A-ZÑ]\.)?"                                    # optional middle initial
)


def parse_library_xml(data, registrar_ids):
    """Map the Library XML bytes to unified rows. Raises AdapterError if the file is unusable."""
    registrar_ids = set(registrar_ids)
    try:
        root = SafeET.fromstring(data)
    except (SafeET.ParseError, DefusedXmlException) as exc:
        raise AdapterError(f"Library XML cannot be read: {exc}") from exc
    if root.tag != "borrowers":
        raise AdapterError(f"Library XML root must be <borrowers>, found <{root.tag}>")

    result = ImportResult(source="LIBRARY")
    valid_rows = []  # (record, row_ref, raw_data) for rows that passed every check

    for position, borrower in enumerate(root.findall("borrower"), start=1):
        result.total_rows += 1
        card = (borrower.get("card") or "").strip()
        row_ref = card or f"borrower#{position}"
        raw = {"card": borrower.get("card")}
        for child in borrower:
            raw[child.tag] = (child.text or "").strip()

        student_no = raw.get("studentNo", "")
        reasons = []

        # 1. Student number: right shape, then known to the Registrar.
        id_ok = bool(STUDENT_ID_RE.fullmatch(student_no))
        if not id_ok:
            add_reason(reasons, "BAD_STUDENT_NO")
        elif student_no not in registrar_ids:
            add_reason(reasons, "NOT_IN_REGISTRAR")

        # 2. Name format.
        if not _NAME_RE.fullmatch(raw.get("name", "")):
            add_reason(reasons, "BAD_NAME")

        # 3. Program must exist in the crosswalk.
        if raw.get("program", "") not in LIBRARY_PROGRAM_CROSSWALK:
            add_reason(reasons, "UNKNOWN_PROGRAM")

        # 4. Last borrowed date: empty is allowed (None), otherwise a real MM/DD/YYYY date.
        last_borrowed = None
        if raw.get("lastBorrowed", ""):
            parsed = parse_date(raw["lastBorrowed"], "US")
            if parsed is None:
                add_reason(reasons, "BAD_DATE")
            else:
                last_borrowed = parsed.isoformat()

        # 5. Numbers: books are a whole number, fines are money (centavos).
        books, error = parse_count(raw.get("unreturnedBooks"))
        if error:
            add_reason(reasons, error)
        fines, error = parse_money(raw.get("unpaidFines"))
        if error:
            add_reason(reasons, error)

        if reasons:
            result.rejects.append(make_reject(row_ref, reasons, student_no if id_ok else None, raw))
            continue

        record = {
            "card_no": card,
            "student_id": student_no,
            "unreturned_books": books,
            "unpaid_fines": fines,
            "last_borrowed": last_borrowed,
        }
        valid_rows.append((record, row_ref, raw))

    # One Library record per student (api_contract decision 5).
    kept, duplicate_rejects = resolve_duplicates(
        valid_rows,
        key_of=lambda r: r["student_id"],
        compare_of=lambda r: (r["unreturned_books"], r["unpaid_fines"]),
    )
    result.accepted = kept
    result.rejects.extend(duplicate_rejects)
    return result