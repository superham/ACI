"""Tests for aci_tool.collectors.ransomwhere — transient HTTP failure handling."""

import pytest
import requests

from aci_tool.collectors import ransomwhere


class _FakeResponse:
    def __init__(self, status_code: int, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {"result": []}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} Server Error", response=self)

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def get(self, *_args, **_kwargs):
        self.calls += 1
        resp = self._responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return resp

    def mount(self, *_args, **_kwargs):
        pass


def test_fetch_payments_succeeds_after_transient_502(monkeypatch):
    """Retry layer should turn a 502 into a successful retry under the hood;
    we simulate that by having the (fake) session return a 200 directly,
    and assert fetch_payments reaches the parsing path."""
    fake = _FakeSession(
        [
            _FakeResponse(
                200,
                {
                    "result": [
                        {
                            "family": "TestFamily",
                            "address": "abc123",
                            "transactions": [{"amountUSD": 100.0, "time": 1700000000}],
                        }
                    ]
                },
            )
        ]
    )
    monkeypatch.setattr(ransomwhere, "_session_with_retries", lambda: fake)

    payments = ransomwhere.fetch_payments()

    assert fake.calls == 1
    assert len(payments) == 1
    assert payments[0].family == "TestFamily"
    assert payments[0].amount_usd == 100.0


def test_fetch_payments_raises_on_terminal_failure(monkeypatch, capsys):
    """After the retry layer gives up, fetch_payments should raise — not silently
    return [] — so the monthly update script fails loudly instead of producing
    empty data."""
    fake = _FakeSession([_FakeResponse(502)])
    monkeypatch.setattr(ransomwhere, "_session_with_retries", lambda: fake)

    with pytest.raises(requests.HTTPError):
        ransomwhere.fetch_payments()

    captured = capsys.readouterr()
    assert "[RWHERE] Error fetching payments" in captured.out


def test_session_with_retries_configures_5xx_and_429():
    session = ransomwhere._session_with_retries()
    adapter = session.get_adapter("https://api.ransomwhe.re/export")
    retry = adapter.max_retries

    assert retry.total == 4
    assert retry.backoff_factor == 2
    assert set(retry.status_forcelist) >= {429, 502, 503, 504}
