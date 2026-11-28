"""Manifest check (R14): runs BEFORE any record of an import file is read.

A manifest is a small JSON file next to the data file. It carries the file's SHA-256, the record
count, a creation time, a one-time nonce and an HMAC-SHA256 signature of all those fields.
Same method as the starter kit's verify_manifest.py.
"""
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import date, datetime

REQUIRED_FIELDS = ("file", "source", "sha256", "record_count", "created_at", "nonce", "signature")


class ManifestError(Exception):
    """The file must be rejected whole. `code` becomes import_files.reject_reason."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


@dataclass
class Manifest:
    file: str
    source: str          # "LIBRARY" or "ACCOUNTING"
    sha256: str
    record_count: int
    created_at: str
    nonce: str
    export_date: date    # the date part of created_at


def verify_manifest(data, manifest_bytes, key, expected_source):
    """Check a data file against its manifest. Returns a Manifest or raises ManifestError.

    data            raw bytes of the data file (the SAME bytes the adapter will parse)
    manifest_bytes  raw bytes of the .manifest.json file
    key             the HMAC key (str or bytes)
    expected_source "LIBRARY" or "ACCOUNTING"
    Error codes: BAD_MANIFEST, SIGNATURE_INVALID, HASH_MISMATCH.
    """
    try:
        m = json.loads(manifest_bytes.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ManifestError("BAD_MANIFEST", f"Manifest is not valid JSON: {exc}") from exc
    if not isinstance(m, dict) or any(f not in m for f in REQUIRED_FIELDS):
        raise ManifestError("BAD_MANIFEST", "Manifest is missing required fields")
    if not all(isinstance(m[f], str) for f in REQUIRED_FIELDS if f != "record_count"):
        raise ManifestError("BAD_MANIFEST", "Manifest fields must be text")
    if isinstance(m["record_count"], bool) or not isinstance(m["record_count"], int):
        raise ManifestError("BAD_MANIFEST", "record_count must be a whole number")

    # 1. Signature first: nothing else in the manifest is trusted until this passes.
    key_bytes = key.encode() if isinstance(key, str) else key
    body = json.dumps({k: v for k, v in m.items() if k != "signature"},
                      sort_keys=True, separators=(",", ":")).encode()
    expected = hmac.new(key_bytes, body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, m["signature"]):
        raise ManifestError("SIGNATURE_INVALID", "Manifest signature is invalid")

    # 2. The file must be exactly what was signed.
    if hashlib.sha256(data).hexdigest() != m["sha256"]:
        raise ManifestError("HASH_MISMATCH", "File was altered after signing (SHA-256 mismatch)")

    # 3. Right kind of file, and a readable creation time.
    if m["source"].strip().upper() != expected_source:
        raise ManifestError("BAD_MANIFEST", f"Manifest says source={m['source']!r}, expected {expected_source}")
    try:
        export_date = datetime.fromisoformat(m["created_at"]).date()
    except ValueError as exc:
        raise ManifestError("BAD_MANIFEST", f"created_at is not an ISO date-time: {exc}") from exc

    return Manifest(m["file"], expected_source, m["sha256"], m["record_count"],
                    m["created_at"], m["nonce"], export_date)