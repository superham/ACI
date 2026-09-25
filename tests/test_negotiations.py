"""Tests for aci_tool.collectors.negotiations — transient HTTP failure handling."""

import pytest
import requests

from aci_tool.collectors import negotiations


def _http_error(url):
    return requests.HTTPError(f"502 Server Error: Bad Gateway for url: {url}")


@pytest.fixture
def fake_api(monkeypatch):
    """Two groups with chats; chat IDs listed in `broken` raise after retries."""
    chats = {"REvil": ["20210709", "20210710"], "Akira": [str(i) for i in range(20)]}
    broken = set()

    monkeypatch.setattr(
        negotiations,
        "fetch_negotiation_groups",
        lambda _key: {"groups": [{"group": g} for g in chats]},
    )
    monkeypatch.setattr(negotiations, "fetch_group_chats", lambda _key, g: [{"id": c} for c in chats[g]])

    def fake_detail(_key, g, chat_id):
        if (g, chat_id) in broken:
            raise _http_error(f"{negotiations.BASE}/negotiations/{g}/{chat_id}")
        return {"messages": [], "ransominfo": {}}

    monkeypatch.setattr(negotiations, "fetch_chat_detail", fake_detail)
    return broken


def test_single_failing_chat_is_skipped(fake_api, capsys):
    fake_api.add(("REvil", "20210709"))

    records = negotiations.fetch_negotiations("key")

    assert len(records) == 21
    assert ("REvil", "20210709") not in {(r.group, r.chat_id) for r in records}
    assert "skipping REvil/20210709" in capsys.readouterr().out


def test_widespread_failures_abort(fake_api):
    fake_api.update(("Akira", str(i)) for i in range(10))

    with pytest.raises(requests.HTTPError, match="10/22 negotiation chats failed"):
        negotiations.fetch_negotiations("key")


def test_requests_go_through_retrying_session(monkeypatch):
    calls = []

    class FakeSession:
        def get(self, url, **_kwargs):
            calls.append(url)
            resp = requests.Response()
            resp.status_code = 200
            resp._content = b'{"messages": [], "ransominfo": {}}'
            return resp

    monkeypatch.setattr(negotiations, "_session", None)
    monkeypatch.setattr(negotiations, "session_with_retries", FakeSession)

    negotiations.fetch_chat_detail("key", "REvil", "20210709")

    assert calls == [f"{negotiations.BASE}/negotiations/REvil/20210709"]


def test_retry_policy_covers_502():
    retry = negotiations.session_with_retries().get_adapter(negotiations.BASE).max_retries

    assert 502 in retry.status_forcelist
    assert retry.total == 4
