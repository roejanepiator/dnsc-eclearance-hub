# Data Mapping Specification (Data engineer, R9, Appendix F)

Version: Stage 1. Code: `app/importers/`. Reject codes and decisions: `docs/api_contract.md` section 6.
Money is stored as integer centavos. Dates are stored as `YYYY-MM-DD`.

## 1. Registrar JSON -> `students` (master record)

Pulled by `app/registrar_client.py` (API dev). The Registrar is the master list; every other source is matched against it.

+---------------------------+---------------------------+----------------+-------------------------+
| Source field              | Target field              | Transformation | Reject condition        |
+---------------------------+---------------------------+----------------+-------------------------+
| `student_id`              | `students.student_id`     | none           | not `NNNN-NNNNN`        |
+---------------------------+---------------------------+----------------+-------------------------+
| `last_name`, `first_name` | `last_name`, `first_name` | none           | empty                   |
+---------------------------+---------------------------+----------------+-------------------------+
| `middle_initial`          | `middle_initial`          | none           | none (optional)         |
+---------------------------+---------------------------+----------------+-------------------------+
| `program_code`            | `program_code`            | none           | empty                   |
+---------------------------+---------------------------+----------------+-------------------------+
| `program_name`            | `program_name`            | none           | none (optional)         |
+---------------------------+---------------------------+----------------+-------------------------+
| `year_level`              | `year_level`              | none           | not 1-6                 |
+---------------------------+---------------------------+----------------+-------------------------+
| `email`                   | `email`                   | none           | none (optional)         |
+---------------------------+---------------------------+----------------+-------------------------+
| `status`                  | `status`                  | none           | not `ENROLLED` or `LOA` |
+---------------------------+---------------------------+----------------+-------------------------+
| (generated)               | `synced_at`               | time of sync   | n/a                     |
+---------------------------+---------------------------+----------------+-------------------------+

An LOA student is stored normally; the Hub sets every office to HOLD with reason `ON_LOA` (decision 1).

## 2. Library XML -> `library_records`

File: `<borrowers exported=...>` with one `<borrower card=...>` per borrower. Adapter: `parse_library_xml`.

+----------------------+--------------------+--------------------------+----------------------------+
| Source field         | Target field       | Transformation           | Reject condition           |
+----------------------+--------------------+--------------------------+----------------------------+
| `@card`              | `card_no`          | trim                     | none (row reference in the |
|                      |                    |                          | reject log)                |
+----------------------+--------------------+--------------------------+----------------------------+
| `studentNo`          | `student_id`       | trim                     | not `NNNN-NNNNN` ->        |
|                      |                    |                          | `BAD_STUDENT_NO`; not in   |
|                      |                    |                          | Registrar ->               |
|                      |                    |                          | `NOT_IN_REGISTRAR`         |
+----------------------+--------------------+--------------------------+----------------------------+
| `name`               | (not stored)       | format check only        | not `SURNAME, Given M.` -> |
|                      |                    |                          | `BAD_NAME`                 |
+----------------------+--------------------+--------------------------+----------------------------+
| `program`            | (not stored)       | check against crosswalk  | any other code ->          |
|                      |                    | (BSA, BSED-MATH, BSCRIM, | `UNKNOWN_PROGRAM`          |
|                      |                    | BSIT, BSIS)              |                            |
+----------------------+--------------------+--------------------------+----------------------------+
| `lastBorrowed`       | `last_borrowed`    | `MM/DD/YYYY` ->          | impossible date ->         |
|                      |                    | `YYYY-MM-DD`; empty ->   | `BAD_DATE`                 |
|                      |                    | NULL                     |                            |
+----------------------+--------------------+--------------------------+----------------------------+
| `unreturnedBooks`    | `unreturned_books` | integer                  | not a whole number ->      |
|                      |                    |                          | `BAD_AMOUNT`; negative ->  |
|                      |                    |                          | `NEGATIVE_AMOUNT`          |
+----------------------+--------------------+--------------------------+----------------------------+
| `unpaidFines`        | `unpaid_fines`     | pesos -> centavos        | not money -> `BAD_AMOUNT`; |
|                      |                    |                          | negative ->                |
|                      |                    |                          | `NEGATIVE_AMOUNT`          |
+----------------------+--------------------+--------------------------+----------------------------+
| `yearLevel`, `email` | (ignored)          | Registrar is the source  | none                       |
|                      |                    | of truth                 |                            |
+----------------------+--------------------+--------------------------+----------------------------+

## 3. Accounting CSV -> `accounting_records`

Header: `StudentNo,Name,Term,Assessed,Paid,Balance,LastPaymentDate`. Adapter: `parse_accounting_csv`.
The export date comes from the signed manifest (`created_at`).

+-------------------+----------------------+--------------------------+--------------------------------+
| Source field      | Target field         | Transformation           | Reject condition               |
+-------------------+----------------------+--------------------------+--------------------------------+
| `StudentNo`       | `student_id`         | trim                     | `BAD_STUDENT_NO`;              |
|                   |                      |                          | `NOT_IN_REGISTRAR`             |
+-------------------+----------------------+--------------------------+--------------------------------+
| `Name`            | (ignored)            | Registrar is the source  | none                           |
|                   |                      | of truth                 |                                |
+-------------------+----------------------+--------------------------+--------------------------------+
| `Term`            | `term`               | trim                     | not validated (no reject code  |
|                   |                      |                          | exists)                        |
+-------------------+----------------------+--------------------------+--------------------------------+
| `Assessed`,       | `assessed`, `paid`,  | remove thousands commas, | not money -> `BAD_AMOUNT`;     |
| `Paid`, `Balance` | `balance`            | pesos -> centavos        | negative -> `NEGATIVE_AMOUNT`  |
+-------------------+----------------------+--------------------------+--------------------------------+
| `LastPaymentDate` | `last_payment_date`  | ISO date; empty -> NULL  | impossible date -> `BAD_DATE`; |
|                   |                      |                          | after export date ->           |
|                   |                      |                          | `FUTURE_DATE`                  |
+-------------------+----------------------+--------------------------+--------------------------------+

## 4. Rules that apply to both files

1. A file that cannot be read (broken XML, not UTF-8, missing CSV column) is rejected whole (`AdapterError`).
2. A row is checked in this order: student number, Registrar lookup, name, program, date, amounts. All problems are recorded in `reasons`; the first one is the `reason_code`.
3. Duplicates are resolved after validation (decision 5): one valid row is kept; identical valid rows -> first kept, others `DUPLICATE`; valid rows that disagree -> all `DATA_CONFLICT`.
4. Every input row ends in exactly one place: accepted or rejected (`total = accepted + rejected`).

## 5. Result on the starter files (export 2026-11-20)

+----------------+------+----------+----------+
| File           | Rows | Accepted | Rejected |
+----------------+------+----------+----------+
| Library XML    | 29   | 25       | 4        |
+----------------+------+----------+----------+
| Accounting CSV | 42   | 37       | 5        |
+----------------+------+----------+----------+

+--------------------+-------------------------------------------------------------------------+
| Row                | Reason                                                                  |
+--------------------+-------------------------------------------------------------------------+
| LIB-0026           | `NOT_IN_REGISTRAR` (also `BAD_NAME`)                                    |
+--------------------+-------------------------------------------------------------------------+
| LIB-0027           | `BAD_STUDENT_NO`                                                        |
+--------------------+-------------------------------------------------------------------------+
| LIB-0028           | `NOT_IN_REGISTRAR` (also `UNKNOWN_PROGRAM`, `BAD_DATE`)                 |
+--------------------+-------------------------------------------------------------------------+
| LIB-0029           | `NEGATIVE_AMOUNT` (duplicate card of 2023-59928; LIB-0001 is kept)      |
+--------------------+-------------------------------------------------------------------------+
| CSV line 7, 13, 25 | `FUTURE_DATE`                                                           |
+--------------------+-------------------------------------------------------------------------+
| CSV line 42        | `NOT_IN_REGISTRAR`                                                      |
+--------------------+-------------------------------------------------------------------------+
| CSV line 43        | `BAD_AMOUNT` (also `BAD_DATE`; duplicate of 2024-45481, line 4 is kept) |
+--------------------+-------------------------------------------------------------------------+  