"""Shared helpers for the Library and Accounting adapters (Data engineer, R9, R11).

These functions do NOT touch the database, the network or any other part of the Hub.
They only turn raw text into clean values (or a reject code), so they are easy to test.
"""
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

# Allow-lists (R11): a value is accepted only if it matches one of these exact shapes.
STUDENT_ID_RE = re.compile(r"[0-9]{4}-[0-9]{5}")             # 2023-59928
_MONEY_RE = re.compile(r"-?(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]{1,2})?")  # 10,450.50
_COUNT_RE = re.compile(r"-?[0-9]+")                           # 0, 1, 2 ...
_US_DATE_RE = re.compile(r"[0-9]{2}/[0-9]{2}/[0-9]{4}")       # MM/DD/YYYY (Library)
_ISO_DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")      # YYYY-MM-DD (Accounting)


class AdapterError(Exception):
    """The WHOLE file is unusable (not UTF-8, broken XML, missing CSV columns).

    Row-level problems are never raised; they become entries in ImportResult.rejects.
    """


@dataclass
class ImportResult:
    """What an adapter returns: the good rows and the rejected rows."""

    source: str                                   # "LIBRARY" or "ACCOUNTING"
    total_rows: int = 0                           # rows found in the file
    accepted: list = field(default_factory=list)  # unified rows, ready for the database
    rejects: list = field(default_factory=list)   # one dict per rejected row

    @property
    def accepted_count(self):
        return len(self.accepted)

    @property
    def rejected_count(self):
        return len(self.rejects)


def add_reason(reasons, code):
    """Append a reject code once (keeps the order in which problems were found)."""
    if code not in reasons:
        reasons.append(code)


def parse_money(text):
    """'10,450.50' -> (1045050, None). Money becomes integer centavos, never a float.

    Returns (centavos, None) on success or (None, 'BAD_AMOUNT' | 'NEGATIVE_AMOUNT').
    """
    s = text.strip() if isinstance(text, str) else ""
    if not _MONEY_RE.fullmatch(s):
        return None, "BAD_AMOUNT"
    value = Decimal(s.replace(",", ""))
    if value < 0:
        return None, "NEGATIVE_AMOUNT"
    return int(value * 100), None


def parse_count(text):
    """'2' -> (2, None). Same return style as parse_money, for whole numbers."""
    s = text.strip() if isinstance(text, str) else ""
    if not _COUNT_RE.fullmatch(s):
        return None, "BAD_AMOUNT"
    number = int(s)
    if number < 0:
        return None, "NEGATIVE_AMOUNT"
    return number, None


def parse_date(text, style):
    """Return a real date, or None if the text is not a valid calendar date.

    style 'US'  -> MM/DD/YYYY   (Library export)
    style 'ISO' -> YYYY-MM-DD   (Accounting export)
    """
    s = text.strip() if isinstance(text, str) else ""
    try:
        if style == "US":
            if _US_DATE_RE.fullmatch(s):
                return datetime.strptime(s, "%m/%d/%Y").date()
        elif style == "ISO":
            if _ISO_DATE_RE.fullmatch(s):
                return date.fromisoformat(s)
    except ValueError:  # e.g. 31/09/2026 or 2026-13-01: right shape, impossible date
        return None
    return None


def make_reject(row_ref, reasons, student_id, raw_data):
    """Build one reject entry. reason_code is the FIRST problem found; reasons has them all."""
    return {
        "row_ref": row_ref,
        "reason_code": reasons[0],
        "reasons": list(reasons),
        "student_id": student_id,
        "raw_data": raw_data,
    }


def resolve_duplicates(valid_rows, key_of, compare_of):
    """Apply decision 5 of docs/api_contract.md to rows that already passed validation.

    valid_rows: list of (record, row_ref, raw_data) in file order.
    key_of(record)     -> what makes two rows "the same" (e.g. the student ID)
    compare_of(record) -> the values that must agree for two rows to be the same fact

    * one valid row for a key            -> keep it
    * several, all agree                 -> keep the first, reject the others as DUPLICATE
    * several, they disagree             -> reject ALL as DATA_CONFLICT
    Returns (kept_records, extra_rejects).
    """
    groups = {}
    for item in valid_rows:
        groups.setdefault(key_of(item[0]), []).append(item)

    kept, rejects = [], []
    for items in groups.values():
        if len(items) == 1:
            kept.append(items[0][0])
            continue
        agree = len({compare_of(record) for record, _, _ in items}) == 1
        if agree:
            kept.append(items[0][0])
            for record, row_ref, raw in items[1:]:
                rejects.append(make_reject(row_ref, ["DUPLICATE"], record["student_id"], raw))
        else:
            for record, row_ref, raw in items:
                rejects.append(make_reject(row_ref, ["DATA_CONFLICT"], record["student_id"], raw))
    return kept, rejects


def now_iso():
    """Current time as ISO-8601 text with the Philippine offset, e.g. 2026-11-28T14:05:09+08:00."""
    manila = timezone(timedelta(hours=8))
    return datetime.now(manila).isoformat(timespec="seconds")