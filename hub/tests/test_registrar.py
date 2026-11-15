import httpx
import pytest

from app import registrar_client as rc
from app.registrar_client import RegistrarClient, RegistrarError


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(rc.time, "sleep", lambda s: None)


def make_client(handler, **kw):
    return RegistrarClient(base_url="http://test/api/v1", api_key="k",
                           transport=httpx.MockTransport(handler), **kw)


def test_retries_503_then_succeeds():
    calls = {"n": 0}

    def handler(req):
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503, headers={"Retry-After": "2"})
        return httpx.Response(200, json={"student_id": "2023-59928"})

    assert make_client(handler).get_student("2023-59928")["student_id"] == "2023-59928"
    assert calls["n"] == 3


def test_gives_up_after_max_retries():
    with pytest.raises(RegistrarError):
        make_client(lambda req: httpx.Response(503), max_retries=2).get_student("2023-59928")


def test_404_returns_none():
    assert make_client(lambda req: httpx.Response(404)).get_student("2099-00000") is None


def test_401_is_not_retried():
    calls = {"n": 0}

    def handler(req):
        calls["n"] += 1
        return httpx.Response(401, json={"error": "bad key"})

    with pytest.raises(RegistrarError):
        make_client(handler).get_all_students()
    assert calls["n"] == 1


def test_pages_through_everything():
    def handler(req):
        page = int(req.url.params["page"])
        return httpx.Response(200, json={"data": [{"n": page}], "has_next": page < 3})

    assert make_client(handler).get_all_students() == [{"n": 1}, {"n": 2}, {"n": 3}]


def test_sends_api_key_header():
    seen = {}

    def handler(req):
        seen["key"] = req.headers["x-api-key"]
        return httpx.Response(200, json={"data": [], "has_next": False})

    make_client(handler).get_all_students()
    assert seen["key"] == "k"
