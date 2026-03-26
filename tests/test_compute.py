"""Tests for aci_tool.compute — feature aggregation and merging."""

import numpy as np
import pandas as pd
import pytest
from aci_tool.compute import (
    compute_chat_group_features,
    compute_claim_group_features,
    compute_payment_group_features,
    combine_group_features,
)


# ── Chat group features ───────────────────────────────────────────────
class TestChatGroupFeatures:
    def _make_chat_df(self, rows):
        return pd.DataFrame(rows)

    def test_single_group(self):
        df = self._make_chat_df([
            {"group": "lockbit", "chat_id": "1", "paid": True,
             "any_proof_offer": 1, "any_leak_threat": 1,
             "gave_discount": 1, "discount_ratio": 0.5},
            {"group": "lockbit", "chat_id": "2", "paid": False,
             "any_proof_offer": 0, "any_leak_threat": 1,
             "gave_discount": 0, "discount_ratio": None},
        ])
        result = compute_chat_group_features(df)
        assert len(result) == 1
        assert result.iloc[0]["group"] == "lockbit"
        assert result.iloc[0]["n_chats"] == 2
        assert result.iloc[0]["n_paid_chats"] == 1
        assert result.iloc[0]["sample_offer_rate"] == pytest.approx(0.5)
        assert result.iloc[0]["leak_threat_rate"] == pytest.approx(1.0)

    def test_multiple_groups(self):
        df = self._make_chat_df([
            {"group": "a", "chat_id": "1", "paid": True, "any_proof_offer": 1, "any_leak_threat": 0, "gave_discount": 0},
            {"group": "b", "chat_id": "2", "paid": False, "any_proof_offer": 0, "any_leak_threat": 1, "gave_discount": 0},
        ])
        result = compute_chat_group_features(df)
        assert len(result) == 2

    def test_by_year(self):
        df = self._make_chat_df([
            {"group": "a", "chat_id": "1", "year": 2023, "paid": True,
             "any_proof_offer": 1, "any_leak_threat": 1, "gave_discount": 0},
            {"group": "a", "chat_id": "2", "year": 2024, "paid": False,
             "any_proof_offer": 0, "any_leak_threat": 1, "gave_discount": 0},
        ])
        result = compute_chat_group_features(df, by_year=True)
        assert len(result) == 2
        assert set(result["year"]) == {2023, 2024}

    def test_group_name_normalized(self):
        df = self._make_chat_df([
            {"group": "  LockBit  ", "chat_id": "1", "paid": False,
             "any_proof_offer": 1, "any_leak_threat": 0, "gave_discount": 0},
        ])
        # load_chat_features does the normalization, simulate it
        df["group"] = df["group"].str.strip().str.lower()
        result = compute_chat_group_features(df)
        assert result.iloc[0]["group"] == "lockbit"


# ── Claim group features ──────────────────────────────────────────────
class TestClaimGroupFeatures:
    def test_basic(self):
        df = pd.DataFrame([
            {"group": "lockbit", "claim_date": "2024-01-01", "publish_date": "2024-01-15", "deadline": "2024-01-20"},
            {"group": "lockbit", "claim_date": "2024-02-01", "publish_date": "", "deadline": None},
        ])
        result = compute_claim_group_features(df)
        assert len(result) == 1
        assert result.iloc[0]["total_claims"] == 2
        assert result.iloc[0]["published_claims"] == 1
        assert result.iloc[0]["publish_rate"] == pytest.approx(0.5)

    def test_on_time_publish(self):
        df = pd.DataFrame([
            {"group": "a", "claim_date": "2024-01-01", "publish_date": "2024-01-10", "deadline": "2024-01-15"},
            {"group": "a", "claim_date": "2024-02-01", "publish_date": "2024-03-01", "deadline": "2024-02-15"},
        ])
        result = compute_claim_group_features(df)
        assert result.iloc[0]["on_time_publish_rate"] == pytest.approx(0.5)


# ── Payment group features ────────────────────────────────────────────
class TestPaymentGroupFeatures:
    def test_basic(self):
        df = pd.DataFrame([
            {"group": "lockbit", "address": "addr1", "amount_usd": 50000, "tx_count": 2},
            {"group": "lockbit", "address": "addr2", "amount_usd": 30000, "tx_count": 1},
            {"group": "conti", "address": "addr3", "amount_usd": 100000, "tx_count": 5},
        ])
        result = compute_payment_group_features(df)
        assert len(result) == 2
        lb = result[result["group"] == "lockbit"].iloc[0]
        assert lb["total_payment_usd"] == pytest.approx(80000)
        assert lb["n_payment_addresses"] == 2
        assert lb["has_payment_data"] == 1

    def test_empty_df(self):
        df = pd.DataFrame()
        result = compute_payment_group_features(df)
        assert result.empty

    def test_zero_amount(self):
        df = pd.DataFrame([
            {"group": "nocoins", "address": "addr1", "amount_usd": 0, "tx_count": 0},
        ])
        result = compute_payment_group_features(df)
        assert result.iloc[0]["has_payment_data"] == 0


# ── Combine features ──────────────────────────────────────────────────
class TestCombineGroupFeatures:
    def test_merge_chat_and_claims(self):
        chat = pd.DataFrame([{"group": "a", "n_chats": 5, "sample_offer_rate": 0.8}])
        claims = pd.DataFrame([{"group": "a", "total_claims": 10, "publish_rate": 0.7}])
        result = combine_group_features(chat, claims)
        assert len(result) == 1
        assert result.iloc[0]["n_chats"] == 5
        assert result.iloc[0]["total_claims"] == 10

    def test_outer_join_keeps_all_groups(self):
        chat = pd.DataFrame([{"group": "a", "n_chats": 5}])
        claims = pd.DataFrame([{"group": "b", "total_claims": 10}])
        result = combine_group_features(chat, claims)
        assert len(result) == 2

    def test_with_payments(self):
        chat = pd.DataFrame([{"group": "a", "n_chats": 5}])
        claims = pd.DataFrame([{"group": "a", "total_claims": 10}])
        payments = pd.DataFrame([{"group": "a", "total_payment_usd": 50000, "has_payment_data": 1}])
        result = combine_group_features(chat, claims, payments)
        assert result.iloc[0]["has_payment_data"] == 1
