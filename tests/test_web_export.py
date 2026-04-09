"""
Tests for the web_export module — dashboard JSON generation and exclusion criteria.
"""

import numpy as np
import pandas as pd

from aci_tool.web_export import (
    _apply_exclusion_criteria,
    _build_confidence_data,
    _build_group_details,
    _build_outcome_metrics,
    _build_overview_stats,
    _build_per_year_aci_values,
    _build_rti_values,
    _build_total_aci_values,
    _safe_int,
    _safe_round,
)

# ── _safe_round ──────────────────────────────────────────────────────────


class TestSafeRound:
    def test_normal_float(self):
        assert _safe_round(3.14159, 2) == 3.14

    def test_nan_returns_none(self):
        assert _safe_round(float("nan")) is None

    def test_none_returns_none(self):
        assert _safe_round(None) is None

    def test_integer(self):
        assert _safe_round(5) == 5.0

    def test_string_returns_as_is(self):
        assert _safe_round("hello") == "hello"

    def test_zero(self):
        assert _safe_round(0.0) == 0.0


# ── _safe_int ───────────────────────────────────────────────────────────


class TestSafeInt:
    def test_normal_int(self):
        assert _safe_int(5) == 5

    def test_normal_float(self):
        assert _safe_int(3.9) == 3

    def test_python_nan(self):
        assert _safe_int(float("nan")) == 0

    def test_numpy_nan(self):
        assert _safe_int(np.nan) == 0

    def test_numpy_float64_nan(self):
        assert _safe_int(np.float64("nan")) == 0

    def test_none(self):
        assert _safe_int(None) == 0

    def test_pd_na(self):
        assert _safe_int(pd.NA) == 0

    def test_custom_default(self):
        assert _safe_int(None, default=-1) == -1

    def test_zero(self):
        assert _safe_int(0) == 0


# ── _build_confidence_data with NaN ──────────────────────────────────


class TestBuildConfidenceDataNaN:
    def test_nan_fields_dont_crash(self):
        df = pd.DataFrame(
            {
                "group": ["alpha"],
                "confidence": [0.85],
                "n_chats": [np.nan],
                "total_claims": [np.nan],
                "low_data": [np.nan],
            }
        )
        result = _build_confidence_data(df, ["alpha"])
        assert len(result) == 1
        assert result[0]["nChats"] == 0
        assert result[0]["totalClaims"] == 0
        assert result[0]["lowData"] is False


# ── _apply_exclusion_criteria ──────────────────────────────────────────


class TestExclusionCriteria:
    def _make_total(self, groups):
        return pd.DataFrame({"group": groups, "ACI": [5.0] * len(groups)})

    def _make_yearly(self, data):
        """data: list of (group, year, n_chats)"""
        return pd.DataFrame(data, columns=["group", "year", "n_chats"])

    def test_group_with_two_years_passes(self):
        df_total = self._make_total(["alpha"])
        df_yearly = self._make_yearly(
            [
                ("alpha", 2023, 3),
                ("alpha", 2024, 5),
            ]
        )
        result = _apply_exclusion_criteria(df_total, df_yearly)
        assert result == ["alpha"]

    def test_group_with_one_year_fails(self):
        df_total = self._make_total(["beta"])
        df_yearly = self._make_yearly(
            [
                ("beta", 2024, 10),
            ]
        )
        result = _apply_exclusion_criteria(df_total, df_yearly)
        assert result == []

    def test_group_with_zero_chats_in_one_year_fails(self):
        """Even if 2 years exist, a year with 0 chats shouldn't count."""
        df_total = self._make_total(["gamma"])
        df_yearly = self._make_yearly(
            [
                ("gamma", 2023, 5),
                ("gamma", 2024, 0),
            ]
        )
        result = _apply_exclusion_criteria(df_total, df_yearly)
        assert result == []

    def test_multiple_groups_mixed(self):
        df_total = self._make_total(["alpha", "beta", "gamma"])
        df_yearly = self._make_yearly(
            [
                ("alpha", 2023, 3),
                ("alpha", 2024, 5),
                ("beta", 2024, 10),
                ("gamma", 2022, 2),
                ("gamma", 2023, 4),
                ("gamma", 2024, 6),
            ]
        )
        result = _apply_exclusion_criteria(df_total, df_yearly)
        assert result == ["alpha", "gamma"]

    def test_total_row_excluded(self):
        """Rows with year='TOTAL' should not count toward year requirements."""
        df_total = self._make_total(["delta"])
        df_yearly = self._make_yearly(
            [
                ("delta", 2024, 5),
                ("delta", "TOTAL", 5),
            ]
        )
        result = _apply_exclusion_criteria(df_total, df_yearly)
        assert result == []

    def test_no_year_column_returns_all(self):
        """If yearly data has no 'year' column, return all groups."""
        df_total = self._make_total(["alpha", "beta"])
        df_yearly = pd.DataFrame({"group": ["alpha", "beta"], "n_chats": [5, 3]})
        result = _apply_exclusion_criteria(df_total, df_yearly)
        assert result == ["alpha", "beta"]

    def test_empty_dataframes(self):
        df_total = pd.DataFrame({"group": [], "ACI": []})
        df_yearly = pd.DataFrame({"group": [], "year": [], "n_chats": []})
        result = _apply_exclusion_criteria(df_total, df_yearly)
        assert result == []


# ── _build_total_aci_values ────────────────────────────────────────────


class TestBuildTotalACIValues:
    def test_filters_to_qualifying_groups(self):
        df = pd.DataFrame(
            {
                "group": ["alpha", "beta", "gamma"],
                "ACI": [7.5, 6.0, 4.2],
            }
        )
        result = _build_total_aci_values(df, ["alpha", "gamma"])
        brands = [r["brand"] for r in result]
        assert "beta" not in brands
        assert len(result) == 2

    def test_sorted_by_aci_descending(self):
        df = pd.DataFrame(
            {
                "group": ["low", "high", "mid"],
                "ACI": [3.0, 9.0, 6.0],
            }
        )
        result = _build_total_aci_values(df, ["low", "high", "mid"])
        assert result[0]["brand"] == "high"
        assert result[-1]["brand"] == "low"

    def test_nan_aci_becomes_none(self):
        df = pd.DataFrame(
            {
                "group": ["alpha"],
                "ACI": [float("nan")],
            }
        )
        result = _build_total_aci_values(df, ["alpha"])
        assert result[0]["aciValue"] is None


# ── _build_per_year_aci_values ─────────────────────────────────────────


class TestBuildPerYearACIValues:
    def test_basic(self):
        df = pd.DataFrame(
            {
                "group": ["alpha", "alpha", "beta"],
                "year": [2023, 2024, 2024],
                "ACI": [7.0, 7.5, 6.0],
            }
        )
        result = _build_per_year_aci_values(df, ["alpha"])
        assert len(result) == 2
        assert all(r["brand"] == "alpha" for r in result)

    def test_total_rows_excluded(self):
        df = pd.DataFrame(
            {
                "group": ["alpha", "alpha"],
                "year": [2024, "TOTAL"],
                "ACI": [7.0, 7.2],
            }
        )
        result = _build_per_year_aci_values(df, ["alpha"])
        assert len(result) == 1

    def test_no_year_column(self):
        df = pd.DataFrame({"group": ["alpha"], "ACI": [7.0]})
        result = _build_per_year_aci_values(df, ["alpha"])
        assert result == []


# ── _build_rti_values ────────────────────────────────────────────────────


class TestBuildRTIValues:
    def test_basic(self):
        df = pd.DataFrame(
            {
                "group": ["alpha"],
                "ACI": [7.0],
                "R": [0.8],
                "T": [0.7],
                "I": [0.6],
            }
        )
        result = _build_rti_values(df, ["alpha"])
        assert len(result) == 1
        assert result[0]["r"] == 0.8
        assert result[0]["t"] == 0.7
        assert result[0]["i"] == 0.6


# ── _build_overview_stats ────────────────────────────────────────────────


class TestBuildOverviewStats:
    def test_basic(self):
        df = pd.DataFrame(
            {
                "group": ["alpha", "beta"],
                "ACI": [7.5, 4.2],
            }
        )
        result = _build_overview_stats(df, ["alpha", "beta"], 50, 1000)
        assert result[0]["value"] == "2"  # brands scored
        assert result[1]["value"] == "50"  # transcripts
        assert "4.2" in result[2]["value"]  # ACI range min
        assert "7.5" in result[2]["value"]  # ACI range max
        assert result[3]["value"] == "1,000"  # payments


# ── _build_confidence_data ─────────────────────────────────────────────


class TestBuildConfidenceData:
    def test_basic(self):
        df = pd.DataFrame(
            {
                "group": ["alpha"],
                "confidence": [0.85],
                "n_chats": [20],
                "total_claims": [100],
                "low_data": [0],
            }
        )
        result = _build_confidence_data(df, ["alpha"])
        assert len(result) == 1
        assert result[0]["confidence"] == 0.85
        assert result[0]["nChats"] == 20
        assert result[0]["lowData"] is False


# ── _build_outcome_metrics ─────────────────────────────────────────────


class TestBuildOutcomeMetrics:
    def test_basic(self):
        df_total = pd.DataFrame(
            {
                "group": ["alpha"],
                "ACI": [7.0],
            }
        )
        df_chat = pd.DataFrame(
            {
                "group": ["alpha", "alpha", "alpha", "alpha"],
                "paid": [1, 0, 1, 0],
                "gave_discount": [1, 0, 1, 0],
                "discount_ratio": [0.5, 0.0, 0.3, 0.0],
                "any_reextortion_behavior": [0, 0, 1, 0],
            }
        )
        result = _build_outcome_metrics(df_total, df_chat, ["alpha"])
        assert len(result) == 1
        assert result[0]["frequencyOfRansomPayments"] == "50%"
        assert result[0]["discountFrequency"] == "50%"
        assert result[0]["rateOfReExtortion"] == "25%"

    def test_empty_chat_features_excluded(self):
        df_total = pd.DataFrame({"group": ["alpha"], "ACI": [7.0]})
        df_chat = pd.DataFrame(
            {
                "group": ["beta"],
                "paid": [1],
                "gave_discount": [0],
                "discount_ratio": [0.0],
                "any_reextortion_behavior": [0],
            }
        )
        result = _build_outcome_metrics(df_total, df_chat, ["alpha"])
        assert result == []


# ── _build_group_details ───────────────────────────────────────────────


class TestBuildGroupDetails:
    def test_includes_yearly_trend(self):
        df_total = pd.DataFrame(
            {
                "group": ["alpha"],
                "ACI": [7.0],
                "R": [0.8],
                "T": [0.7],
                "I": [0.6],
                "confidence": [0.9],
                "n_chats": [15],
                "total_claims": [80],
            }
        )
        df_yearly = pd.DataFrame(
            {
                "group": ["alpha", "alpha", "alpha"],
                "year": [2023, 2024, "TOTAL"],
                "ACI": [6.8, 7.2, 7.0],
                "R": [0.75, 0.85, 0.8],
                "T": [0.65, 0.75, 0.7],
                "I": [0.55, 0.65, 0.6],
            }
        )
        df_chat = pd.DataFrame({"group": ["alpha"], "chat_id": ["c1"]})
        result = _build_group_details(df_total, df_yearly, df_chat, ["alpha"])

        assert len(result) == 1
        detail = result[0]
        assert detail["brand"] == "alpha"
        assert detail["yearsActive"] == [2023, 2024]
        assert len(detail["yearlyTrend"]) == 2
        assert detail["yearlyTrend"][0]["year"] == 2023
