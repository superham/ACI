"""Tests for aci_tool.scoring — R, T, I components and ACI composition."""

import numpy as np
import pandas as pd
import pytest

from aci_tool.scoring import (
    _compute_confidence,
    _nanmean,
    compute_aci,
    compute_integrity,
    compute_reliability,
    compute_threat_followthrough,
)


# ── _nanmean ───────────────────────────────────────────────────────────
class TestNanmean:
    def test_basic(self):
        assert _nanmean([0.5, 0.5], [1.0, 1.0]) == pytest.approx(0.5)

    def test_weighted(self):
        # 0.8*0.4 + 0.2*0.6 = 0.44;  total_weight = 1.0
        assert _nanmean([0.8, 0.2], [0.4, 0.6]) == pytest.approx(0.44)

    def test_ignores_nan(self):
        result = _nanmean([0.6, np.nan], [0.5, 0.5])
        assert result == pytest.approx(0.6)

    def test_all_nan_returns_nan(self):
        assert np.isnan(_nanmean([np.nan, np.nan], [0.5, 0.5]))

    def test_none_treated_as_nan(self):
        assert _nanmean([None, 0.4], [0.5, 0.5]) == pytest.approx(0.4)


# ── Reliability ────────────────────────────────────────────────────────
class TestReliability:
    def _make_df(self, **kwargs) -> pd.DataFrame:
        return pd.DataFrame([kwargs])

    def test_full_data(self):
        df = self._make_df(sample_offer_rate=0.8, key_delivery_rate=0.6, has_payment_data=1)
        R = compute_reliability(df)
        # (0.8*0.4 + 0.6*0.4 + 1.0*0.2) / (0.4+0.4+0.2)
        expected = (0.8 * 0.4 + 0.6 * 0.4 + 1.0 * 0.2) / 1.0
        assert R.iloc[0] == pytest.approx(expected)

    def test_missing_payment(self):
        df = self._make_df(sample_offer_rate=1.0, key_delivery_rate=1.0)
        R = compute_reliability(df)
        assert R.iloc[0] == pytest.approx(1.0)

    def test_all_nan(self):
        df = pd.DataFrame([{}])
        R = compute_reliability(df)
        assert np.isnan(R.iloc[0])


# ── Threat follow-through ─────────────────────────────────────────────
class TestThreatFollowthrough:
    def test_full_data(self):
        df = pd.DataFrame(
            [
                {
                    "publish_rate": 0.9,
                    "leak_threat_rate": 0.7,
                    "on_time_publish_rate": 0.5,
                }
            ]
        )
        T = compute_threat_followthrough(df)
        expected = (0.9 * 0.5 + 0.7 * 0.5 + 0.5 * 0.2) / (0.5 + 0.5 + 0.2)
        assert T.iloc[0] == pytest.approx(expected)

    def test_missing_on_time(self):
        df = pd.DataFrame([{"publish_rate": 0.8, "leak_threat_rate": 0.6}])
        T = compute_threat_followthrough(df)
        assert T.iloc[0] == pytest.approx(0.7)


# ── Integrity ──────────────────────────────────────────────────────────
class TestIntegrity:
    def test_no_bad_signals(self):
        df = pd.DataFrame(
            [
                {
                    "violation_claim_rate": 0.0,
                    "reextortion_behavior_rate": 0.0,
                    "data_resale_admission_rate": 0.0,
                }
            ]
        )
        I = compute_integrity(df)
        assert I.iloc[0] == pytest.approx(1.0)

    def test_all_bad(self):
        df = pd.DataFrame(
            [
                {
                    "violation_claim_rate": 1.0,
                    "reextortion_behavior_rate": 1.0,
                    "data_resale_admission_rate": 1.0,
                }
            ]
        )
        I = compute_integrity(df)
        assert I.iloc[0] == pytest.approx(0.0)

    def test_missing_signals_defaults_neutral(self):
        df = pd.DataFrame([{}])
        I = compute_integrity(df)
        assert I.iloc[0] == pytest.approx(1.0)  # no bad signals → I=1


# ── Full ACI ───────────────────────────────────────────────────────────
class TestComputeACI:
    def test_perfect_group(self):
        df = pd.DataFrame(
            [
                {
                    "group": "perfect",
                    "sample_offer_rate": 1.0,
                    "key_delivery_rate": 1.0,
                    "has_payment_data": 1,
                    "publish_rate": 1.0,
                    "leak_threat_rate": 1.0,
                    "violation_claim_rate": 0.0,
                    "reextortion_behavior_rate": 0.0,
                    "data_resale_admission_rate": 0.0,
                    "n_chats": 50,
                    "total_claims": 100,
                }
            ]
        )
        result = compute_aci(df)
        assert result["ACI"].iloc[0] == pytest.approx(10.0)
        assert result["R"].iloc[0] == pytest.approx(1.0)
        assert result["T"].iloc[0] == pytest.approx(1.0)
        assert result["I"].iloc[0] == pytest.approx(1.0)

    def test_zero_group(self):
        df = pd.DataFrame(
            [
                {
                    "group": "zero",
                    "sample_offer_rate": 0.0,
                    "key_delivery_rate": 0.0,
                    "has_payment_data": 0,
                    "publish_rate": 0.0,
                    "leak_threat_rate": 0.0,
                    "violation_claim_rate": 1.0,
                    "reextortion_behavior_rate": 1.0,
                    "data_resale_admission_rate": 1.0,
                    "n_chats": 10,
                    "total_claims": 20,
                }
            ]
        )
        result = compute_aci(df)
        assert result["ACI"].iloc[0] == pytest.approx(0.0)

    def test_aci_scale_0_to_10(self):
        df = pd.DataFrame(
            [
                {
                    "group": "mid",
                    "sample_offer_rate": 0.5,
                    "key_delivery_rate": 0.5,
                    "publish_rate": 0.5,
                    "leak_threat_rate": 0.5,
                    "violation_claim_rate": 0.0,
                    "reextortion_behavior_rate": 0.0,
                    "n_chats": 5,
                    "total_claims": 10,
                }
            ]
        )
        result = compute_aci(df)
        assert 0 <= result["ACI"].iloc[0] <= 10

    def test_missing_r_not_inflated(self):
        """When R is NaN, ACI should NOT be inflated by weight renormalization."""
        df = pd.DataFrame(
            [
                {
                    "group": "partial",
                    # R components missing → R = NaN
                    "publish_rate": 1.0,
                    "leak_threat_rate": 1.0,
                    "violation_claim_rate": 0.0,
                    "reextortion_behavior_rate": 0.0,
                    "data_resale_admission_rate": 0.0,
                    "n_chats": 5,
                    "total_claims": 10,
                }
            ]
        )
        result = compute_aci(df)
        assert np.isnan(result["R"].iloc[0])
        assert result["T"].iloc[0] == pytest.approx(1.0)
        assert result["I"].iloc[0] == pytest.approx(1.0)
        # Missing R treated as 0: ACI = (0.4*0 + 0.3*1.0 + 0.3*1.0) * 10 = 6.0
        assert result["ACI"].iloc[0] == pytest.approx(6.0)

    def test_missing_r_and_t(self):
        """When R and T are both NaN, only I contributes."""
        df = pd.DataFrame(
            [
                {
                    "group": "minimal",
                    "violation_claim_rate": 0.0,
                    "reextortion_behavior_rate": 0.0,
                    "data_resale_admission_rate": 0.0,
                    "n_chats": 5,
                    "total_claims": 10,
                }
            ]
        )
        result = compute_aci(df)
        # Only I=1.0 present: ACI = (0.4*0 + 0.3*0 + 0.3*1.0) * 10 = 3.0
        assert result["ACI"].iloc[0] == pytest.approx(3.0)

    def test_missing_r_t_with_default_integrity(self):
        """When R and T are NaN, I defaults to 1.0 (no bad signals) and contributes 3.0 ACI."""
        df = pd.DataFrame(
            [
                {
                    "group": "empty",
                    "n_chats": 0,
                    "total_claims": 0,
                }
            ]
        )
        result = compute_aci(df)
        # R=NaN, T=NaN → treated as 0; I defaults to 1.0 (no bad signals)
        # ACI = (0.4*0 + 0.3*0 + 0.3*1.0) * 10 = 3.0
        assert result["ACI"].iloc[0] == pytest.approx(3.0)

    def test_multiple_groups(self):
        df = pd.DataFrame(
            [
                {
                    "group": "a",
                    "sample_offer_rate": 1.0,
                    "key_delivery_rate": 1.0,
                    "publish_rate": 1.0,
                    "leak_threat_rate": 1.0,
                    "violation_claim_rate": 0.0,
                    "reextortion_behavior_rate": 0.0,
                },
                {
                    "group": "b",
                    "sample_offer_rate": 0.0,
                    "key_delivery_rate": 0.0,
                    "publish_rate": 0.0,
                    "leak_threat_rate": 0.0,
                    "violation_claim_rate": 1.0,
                    "reextortion_behavior_rate": 1.0,
                },
            ]
        )
        result = compute_aci(df)
        assert len(result) == 2
        assert result.iloc[0]["ACI"] > result.iloc[1]["ACI"]


# ── Confidence ─────────────────────────────────────────────────────────
class TestConfidence:
    def test_high_data(self):
        df = pd.DataFrame(
            [
                {
                    "n_chats": 20,
                    "total_claims": 100,
                    "R": 0.5,
                    "T": 0.5,
                    "I": 0.5,
                }
            ]
        )
        conf = _compute_confidence(df)
        assert conf.iloc[0] == pytest.approx(1.0)

    def test_low_data(self):
        df = pd.DataFrame(
            [
                {
                    "n_chats": 1,
                    "total_claims": 2,
                    "R": 0.5,
                    "T": np.nan,
                    "I": np.nan,
                }
            ]
        )
        conf = _compute_confidence(df)
        assert conf.iloc[0] < 0.5

    def test_no_data(self):
        df = pd.DataFrame(
            [
                {
                    "n_chats": 0,
                    "total_claims": 0,
                    "R": np.nan,
                    "T": np.nan,
                    "I": np.nan,
                }
            ]
        )
        conf = _compute_confidence(df)
        assert conf.iloc[0] == pytest.approx(0.0)
