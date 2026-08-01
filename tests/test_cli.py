"""
Tests for CLI-layer collection behaviour — specifically that an outage on the
optional payments source degrades instead of aborting the whole run.

Background: the 2026-08-01 monthly dashboard run failed outright because
api.ransomwhe.re returned 502. Payment data only enriches Reliability scoring,
so losing it should cost the payments section, not the entire update.
"""

import pytest
import requests

from aci_tool import cli


class TestFetchPaymentsOptional:
    def test_returns_payments_on_success(self, monkeypatch):
        monkeypatch.setattr(cli, "fetch_payments", lambda: ["p1", "p2"])

        assert cli._fetch_payments_optional() == ["p1", "p2"]

    def test_returns_none_on_upstream_5xx(self, monkeypatch, capsys):
        """The exact failure mode that broke the monthly run."""

        def _boom():
            raise requests.HTTPError("502 Server Error: Bad Gateway for url: https://api.ransomwhe.re/export")

        monkeypatch.setattr(cli, "fetch_payments", _boom)

        assert cli._fetch_payments_optional() is None
        assert "payment data unavailable" in capsys.readouterr().out

    def test_returns_none_on_connection_error(self, monkeypatch):
        def _boom():
            raise requests.ConnectionError("connection refused")

        monkeypatch.setattr(cli, "fetch_payments", _boom)

        assert cli._fetch_payments_optional() is None

    def test_empty_result_is_distinct_from_unavailable(self, monkeypatch):
        """[] means 'fetched, no records'; None means 'could not fetch'."""
        monkeypatch.setattr(cli, "fetch_payments", lambda: [])

        assert cli._fetch_payments_optional() == []

    def test_non_transport_errors_still_propagate(self, monkeypatch):
        """A parsing bug in the collector is not an outage — keep it loud."""

        def _boom():
            raise ValueError("malformed row")

        monkeypatch.setattr(cli, "fetch_payments", _boom)

        with pytest.raises(ValueError):
            cli._fetch_payments_optional()


class TestPaymentsSummary:
    def test_counts_records(self):
        assert cli._payments_summary(["a", "b", "c"]) == "3 payments"

    def test_reports_unavailable(self):
        assert cli._payments_summary(None) == "payments unavailable"

    def test_empty_is_zero_not_unavailable(self):
        assert cli._payments_summary([]) == "0 payments"
