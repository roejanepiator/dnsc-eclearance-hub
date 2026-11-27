"""Accounting adapter (Data engineer, R9): Accounting CSV -> unified accounting_records rows.

Input : the raw bytes of the CSV file, the Registrar student IDs, and the export date
        (rows with a payment date AFTER the export date are rejected as FUTURE_DATE).
Output: ImportResult(accepted=[...], rejects=[...]). Nothing is saved here (Stage 2 does that).
Rules : docs/mapping_spec.md section 3. Reject codes: docs/api_contract.md section 6.
"""
import csv
import io

from .common import (
    STUDENT_ID_RE,
    AdapterError,
    ImportResult,
    add_reason,
    make_reject,
    parse_date,
    parse_money,
    resolve_duplicates,
)

REQUIRED_COLUMNS = ("StudentNo", "Name", "Term", "Assessed", "Paid", "Balance", "LastPaymentDate")


def _cell(row, column):
    """Return the stripped text of a CSV cell, or None if the row is too short."""
    value = row.get(column)
    return value.strip() if isinstance(value, str) else None


def parse_accounting_csv(data, registrar_ids, export_date):
    """Map the Accounting CSV bytes to unified rows. Raises AdapterError if the file is unusable.

    export_date is a datetime.date (Stage 2 takes it from the signed manifest).
    """
    registrar_ids = set(registrar_ids)
    try:
        text = data.decode("utf-8-sig")  # utf-8-sig also removes an Excel byte-order mark
    except UnicodeDecodeError as exc:
        raise AdapterError(f"Accounting CSV is not valid UTF-8: {exc}") from exc

    reader = csv.DictReader(io.StringIO(text, newline=""))
    missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
    if missing:
        raise AdapterError(f"Accounting CSV is missing column(s): {', '.join(missing)}")

    result = ImportResult(source="ACCOUNTING")
    valid_rows = []

    for row in reader:
        result.total_rows += 1
        row_ref = f"line {reader.line_num}"  # line number in the file; the header is line 1
        raw = {k: v for k, v in row.items() if k is not None}
        if None in row:  # more cells than headers
            raw["_extra"] = row[None]

        student_no = _cell(row, "StudentNo") or ""
        reasons = []

        # 1. Student number: right shape, then known to the Registrar.
        id_ok = bool(STUDENT_ID_RE.fullmatch(student_no))
        if not id_ok:
            add_reason(reasons, "BAD_STUDENT_NO")
        elif student_no not in registrar_ids:
            add_reason(reasons, "NOT_IN_REGISTRAR")

        # 2. Money columns ("10,450.50" -> 1045050 centavos).
        amounts = {}
        for column in ("Assessed", "Paid", "Balance"):
            centavos, error = parse_money(_cell(row, column))
            if error:
                add_reason(reasons, error)
            amounts[column] = centavos

        # 3. Last payment date: empty is allowed (None); otherwise a real date, not after the export.
        last_payment = None
        if _cell(row, "LastPaymentDate"):
            parsed = parse_date(_cell(row, "LastPaymentDate"), "ISO")
            if parsed is None:
                add_reason(reasons, "BAD_DATE")
            elif parsed > export_date:
                add_reason(reasons, "FUTURE_DATE")
            else:
                last_payment = parsed.isoformat()

        if reasons:
            result.rejects.append(make_reject(row_ref, reasons, student_no if id_ok else None, raw))
            continue

        record = {
            "student_id": student_no,
            "term": _cell(row, "Term") or "",
            "assessed": amounts["Assessed"],
            "paid": amounts["Paid"],
            "balance": amounts["Balance"],
            "last_payment_date": last_payment,
        }
        valid_rows.append((record, row_ref, raw))

    # One Accounting record per student and term (primary key in db/schema.sql).
    kept, duplicate_rejects = resolve_duplicates(
        valid_rows,
        key_of=lambda r: (r["student_id"], r["term"]),
        compare_of=lambda r: (r["assessed"], r["paid"], r["balance"]),
    )
    result.accepted = kept
    result.rejects.extend(duplicate_rejects)
    return result