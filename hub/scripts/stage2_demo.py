"""Stage 2 demo (Data engineer): build a throw-away database and show real CLEARED / HOLD results.

Run from the hub/ folder:   python scripts/stage2_demo.py
It creates hub/stage2_demo.db (ignored by Git), never touches the Hub's own database, and is
replaced by scripts/run_imports.py in Stage 3.
"""
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HUB))

from app.clearance import get_clearance                      # noqa: E402
from app.config import settings                              # noqa: E402
from app.importers.service import import_file                # noqa: E402

DEMO_DB = HUB / "stage2_demo.db"
FILES = [
    ("LIBRARY", HUB / "drop_folder" / "library_export_2026-11-20.xml"),
    ("ACCOUNTING", HUB / "drop_folder" / "accounting_balances_2026-11-20.csv"),
    ("ACCOUNTING", HUB / "tamper_tests" / "accounting_balances_2026-11-20.csv"),   # must be rejected
    ("ACCOUNTING", HUB / "drop_folder" / "accounting_balances_2026-11-20.csv"),   # replay: must be rejected
]


def main():
    DEMO_DB.unlink(missing_ok=True)
    conn = sqlite3.connect(DEMO_DB)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript((HUB / "db" / "schema.sql").read_text(encoding="utf-8"))

    students = json.loads((HUB / "registrar_students.json").read_text(encoding="utf-8"))["students"]
    for s in students:
        conn.execute("INSERT INTO students VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '2026-11-20T22:30:00+08:00')",
                     (s["student_id"], s["last_name"], s["first_name"], s["middle_initial"], s["program_code"],
                      s["program_name"], s["year_level"], s["email"], s["status"]))
    conn.commit()
    print(f"Loaded {len(students)} students from registrar_students.json\n")

    for source, path in FILES:
        r = import_file(conn, path, source, settings.starter_hmac_key)
        extra = f" ({r['reject_reason']})" if r["reject_reason"] else ""
        print(f"{r['status']:<8} {path.parent.name}/{path.name}{extra}  accepted={r['accepted_rows']} rejected={r['rejected_rows']}")

    overall = Counter(row[0] for row in conn.execute("SELECT overall_status FROM clearance_overall"))
    print(f"\nOverall: CLEARED={overall['CLEARED']}  HOLD={overall['HOLD']}\n")
    for sid in ("2026-29417", "2023-59928", "2026-19950", "2025-81367"):
        data = get_clearance(conn, sid)
        parts = [f"{o['office']}={o['status']}" + (f"({o['reason']})" if o["reason"] else "") for o in data["offices"]]
        print(f"{sid}  {data['overall']:<8} " + "  ".join(parts))
    conn.close()
    print(f"\nDatabase saved at {DEMO_DB}")


if __name__ == "__main__":
    main()