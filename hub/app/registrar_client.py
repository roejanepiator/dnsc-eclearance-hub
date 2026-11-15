"""Client for the Registrar REST API (R5): auth header, paging, 503 retry."""
import time

import httpx

from .config import settings


class RegistrarError(Exception):
    """Registrar failed in a way we should not retry (bad key, bad request, gave up)."""


class RegistrarClient:
    def __init__(self, base_url=None, api_key=None, transport=None, max_retries=4):
        self._http = httpx.Client(
            base_url=base_url or settings.registrar_base_url,
            headers={"X-API-Key": api_key or settings.registrar_api_key},
            timeout=10.0,
            transport=transport,  # lets tests inject a fake server
        )
        self.max_retries = max_retries

    def _get(self, path, **params):
        for attempt in range(self.max_retries + 1):
            try:
                r = self._http.get(path, params=params or None)
            except httpx.TransportError as e:  # server down, timeout, etc.
                if attempt == self.max_retries:
                    raise RegistrarError(f"Registrar unreachable: {e}") from e
                time.sleep(min(2 ** attempt, 8))
                continue
            if r.status_code == 503:  # busy: honour Retry-After, then try again
                if attempt == self.max_retries:
                    raise RegistrarError("Registrar still busy after retries")
                time.sleep(float(r.headers.get("Retry-After", 2)))
                continue
            return r
        raise RegistrarError("unreachable")

    def get_student(self, student_id: str):
        """Return the student dict, or None if the Registrar has no such student (404)."""
        r = self._get(f"/students/{student_id}")
        if r.status_code == 404:
            return None
        if r.status_code != 200:
            raise RegistrarError(f"{r.status_code}: {r.text}")
        return r.json()

    def get_all_students(self, size=20):
        """Walk every page and return the full masterlist."""
        students, page = [], 1
        while True:
            r = self._get("/students", page=page, size=size)
            if r.status_code != 200:  # 401 / 400 are not retryable
                raise RegistrarError(f"{r.status_code}: {r.text}")
            body = r.json()
            students.extend(body["data"])
            if not body["has_next"]:
                return students
            page += 1
