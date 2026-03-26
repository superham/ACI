"""
Compute the Attacker Credibility Index (ACI) for each ransomware group.

Inputs:
  - A group-level feature table, e.g. from:
        from aci.features.compute import (
            load_chat_features,
            compute_chat_group_features,
            load_claims,
            compute_claim_group_features,
            combine_group_features,
        )

Outputs:
  - DataFrame with:
      group, R, T, I, ACI, and supporting counts/metrics
"""

from __future__ import annotations
from typing import Optional
import pandas as pd
import numpy as np

# helpers - safe combine with NaN-aware weights
def _nanmean(values: list[Optional[float]], weights: list[float]) -> float:
    """
    Weighted mean that ignores NaNs. If all values are NaN, returns NaN.
    """
    assert len(values) == len(weights)
    total_weight = 0.0
    total = 0.0
    for v, w in zip(values, weights):
        if v is None or (isinstance(v, float) and np.isnan(v)):
            continue
        total += v * w
        total_weight += w
    if total_weight == 0.0:
        return np.nan
    return total / total_weight

# Compute R - (Key Delivery & Decryption Reliability)
def compute_reliability(df_group: pd.DataFrame) -> pd.Series:
    """
    Reliability score per group [0,1].

    Components:
      - sample_offer_rate  (0.4) — how often attackers offer free test decryption
      - key_delivery_rate  (0.4) — how often they reference sending decryptors
      - has_payment_data   (0.2) — ransomwhere confirms payments were received,
        which is a real-world signal that the group operates a functional
        payment→decryption pipeline
    """
    values = []
    for _, row in df_group.iterrows():
        sample = float(row.get("sample_offer_rate", np.nan))
        key = float(row.get("key_delivery_rate", np.nan))
        has_pay = float(row.get("has_payment_data", np.nan))

        components = []
        weights = []

        if not np.isnan(sample):
            components.append(sample)
            weights.append(0.4)

        if not np.isnan(key):
            components.append(key)
            weights.append(0.4)

        if not np.isnan(has_pay):
            components.append(has_pay)
            weights.append(0.2)

        R = _nanmean(components, weights) if components else np.nan
        values.append(R)

    return pd.Series(values, index=df_group.index, name="R")

# ComputeT - (Threat Follow-Through)
def compute_threat_followthrough(df_group: pd.DataFrame) -> pd.Series:
    """
    threat follow-through per group [0,1]

    Uses:
      - publish_rate         (share of claims that ended up with publish_date)
      - leak_threat_rate     (how often leak threats are made in chats)
      - on_time_publish_rate (if present)

    Idea is that:
      If a group frequently threatens leaks and a high fraction of its claims
      end up published, its threats are highly credible

    Formula (default):
      T = weighted mean of:
              publish_rate (0.5)
              leak_threat_rate (0.5)
      on_time_publish_rate is folded in lightly if available.
    """
    values = []
    for _, row in df_group.iterrows():
        publish_rate = float(row.get("publish_rate", np.nan))
        leak_threat_rate = float(row.get("leak_threat_rate", np.nan))
        on_time = float(row.get("on_time_publish_rate", np.nan))

        components = []
        weights = []

        if not np.isnan(publish_rate):
            components.append(publish_rate)
            weights.append(0.5)

        if not np.isnan(leak_threat_rate):
            components.append(leak_threat_rate)
            weights.append(0.5)

        # Small bump for demonstrated on-time follow-through, if available
        # TODO consider removing this if on_time_publish_rate is not reliable
        if not np.isnan(on_time):
            components.append(on_time)
            weights.append(0.2)

        T = _nanmean(components, weights) if components else np.nan
        values.append(T)

    return pd.Series(values, index=df_group.index, name="T")

# Compute I - (Post-Payment Integrity / Re-Extortion)
def compute_integrity(df_group: pd.DataFrame) -> pd.Series:
    """
    post-payment integrity per group [0, 1]

    The v1 implementation relies on primarily on *semantic chat signals:
      - deletion_promise_rate
      - violation_claim_rate
      - reextortion_behavior_rate
      - data_resale_admission_rate

    Currently, there is no per-victim linkage (e.g. connecting that victim A was attacked, paid,
    and at a later date the attacker re-attacked / re-extorted that same victim). 
    This is a major limition of the curent tool. TODO
    
    approximating integrity as:
      I = 1 - f(violation_claim_rate, reextortion_behavior_rate,
                  data_resale_admission_rate)

    Interpretation:
      - Higher I = fewer visible signals of broken promises and re-extortion.
      - Lower I = more accusations / admissions of misuse.
    """
    values = []
    for _, row in df_group.iterrows():
        # Rates defined in compute_chat_group_features if semantic labels exist
        deletion_promise_rate = float(row.get("deletion_promise_rate", np.nan))
        violation_claim_rate = float(row.get("violation_claim_rate", np.nan))
        reextortion_rate = float(row.get("reextortion_behavior_rate", np.nan))
        resale_rate = float(row.get("data_resale_admission_rate", np.nan))

        # If there are no negative signals at all, default to "unknown but assume neutral"
        components = []
        weights = []

        # Treat these as "bad" signals; they will be subtracted from 1
        if not np.isnan(violation_claim_rate):
            components.append(violation_claim_rate)
            weights.append(0.4)

        if not np.isnan(reextortion_rate):
            components.append(reextortion_rate)
            weights.append(0.4)

        if not np.isnan(resale_rate):
            components.append(resale_rate)
            weights.append(0.2)

        # Compute the "bad" score (0 = no negative signals, 1 = all negative)
        bad_score = _nanmean(components, weights) if components else 0.0
        bad_score = min(max(bad_score, 0.0), 1.0)  # clamp

        I = 1.0 - bad_score
        values.append(I)

    return pd.Series(values, index=df_group.index, name="I")

# Combine R, T, I -> ACI
def compute_aci(df_group: pd.DataFrame) -> pd.DataFrame:
    """
    Given a merged group-level feature table, compute:

      - R: key delivery & decryption reliability
      - T: threat follow-through
      - I: post-payment integrity (approximate)
      - ACI: overall attacker credibility index (0–10 scale)

    Formula (default weights):

      ACI_raw = 0.4 * R_g + 0.3 * T_g + 0.3 * I_g

    Then:
      ACI = ACI_raw * 10
    """
    df = df_group.copy()

    df["R"] = compute_reliability(df)
    df["T"] = compute_threat_followthrough(df)
    df["I"] = compute_integrity(df)

    # Weighted sum (NaN-safe: if some components are NaN, they just disappear)
    aci_raw = []
    for _, row in df.iterrows():
        R = float(row.get("R", np.nan))
        T = float(row.get("T", np.nan))
        I = float(row.get("I", np.nan))

        components = []
        weights = []

        if not np.isnan(R):
            components.append(R)
            weights.append(0.4)
        if not np.isnan(T):
            components.append(T)
            weights.append(0.3)
        if not np.isnan(I):
            components.append(I)
            weights.append(0.3)

        val = _nanmean(components, weights) if components else np.nan
        aci_raw.append(val)

    df["ACI_raw"] = aci_raw
    df["ACI"] = df["ACI_raw"] * 10.0

    # Confidence: how much data backs the score (0–1)
    df["confidence"] = _compute_confidence(df)

    return df


def _compute_confidence(df: pd.DataFrame) -> pd.Series:
    """
    Heuristic confidence score [0, 1] based on data volume.

    Factors:
      - n_chats: more negotiation chats = more reliable behavioral signals
      - total_claims: more claims = more reliable publish/threat metrics
      - component coverage: how many of R, T, I were non-NaN

    Thresholds (saturates at 1.0):
      - 10+ chats  → full chat confidence
      - 50+ claims → full claim confidence
    """
    CHAT_SATURATE = 10
    CLAIM_SATURATE = 50

    values = []
    for _, row in df.iterrows():
        n_chats = float(row.get("n_chats", 0) or 0)
        n_claims = float(row.get("total_claims", 0) or 0)

        chat_conf = min(n_chats / CHAT_SATURATE, 1.0)
        claim_conf = min(n_claims / CLAIM_SATURATE, 1.0)

        # Component coverage: how many of R/T/I are non-NaN
        n_components = sum(
            1 for c in ["R", "T", "I"]
            if c in row and pd.notna(row[c])
        )
        coverage = n_components / 3.0

        # Weighted blend
        conf = 0.4 * chat_conf + 0.3 * claim_conf + 0.3 * coverage
        values.append(round(conf, 3))

    return pd.Series(values, index=df.index, name="confidence")

MIN_CHATS_FOR_SCORE = 2  # Groups with fewer chats get a low-confidence warning


def compute_aci_from_files(
    chat_features_path: str,
    claims_path: str,
    payments_path: Optional[str] = None,
    by_year: bool = False,
    as_of_year: Optional[int] = None,
) -> pd.DataFrame:
    """
    End-to-end: read data files, build group features, compute ACI.

    Args:
        chat_features_path: Path to chat_features.csv
        claims_path: Path to ransomware_live.jsonl
        payments_path: Optional path to ransomwhere.jsonl (enriches Reliability)
        by_year: If True, compute separate ACI scores per year
        as_of_year: If provided, compute cumulative scores up to this year

    Returns:
        DataFrame with ACI scores (per group or per group-year)
    """
    import os
    from .compute import (
        load_chat_features,
        compute_chat_group_features,
        load_claims,
        compute_claim_group_features,
        load_payments,
        compute_payment_group_features,
        combine_group_features,
    )

    df_chat = load_chat_features(chat_features_path)
    df_claims = load_claims(claims_path)

    # Load payment data if available
    df_payment_group = None
    if payments_path and os.path.exists(payments_path):
        df_payments = load_payments(payments_path)
        if not df_payments.empty:
            df_payment_group = compute_payment_group_features(df_payments)

    # Filter by as_of_year if specified
    if as_of_year is not None:
        if "year" in df_chat.columns:
            df_chat = df_chat[df_chat["year"] <= as_of_year]
        if "claim_date" in df_claims.columns:
            df_claims["year"] = pd.to_datetime(df_claims["claim_date"], errors="coerce").dt.year
            df_claims = df_claims[df_claims["year"] <= as_of_year]

    df_chat_group = compute_chat_group_features(df_chat, by_year=by_year)
    df_claim_group = compute_claim_group_features(df_claims, by_year=by_year)

    df_group = combine_group_features(df_chat_group, df_claim_group, df_payment_group)
    df_aci = compute_aci(df_group)

    # Flag low-data groups
    if "n_chats" in df_aci.columns:
        df_aci["low_data"] = (df_aci["n_chats"].fillna(0) < MIN_CHATS_FOR_SCORE).astype(int)

    if by_year and "year" in df_aci.columns:
        df_total = compute_chat_group_features(df_chat, by_year=False)
        df_total_claims = compute_claim_group_features(df_claims, by_year=False)
        df_total_group = combine_group_features(df_total, df_total_claims, df_payment_group)
        df_total_aci = compute_aci(df_total_group)
        df_total_aci["year"] = "TOTAL"
        df_aci = pd.concat([df_aci, df_total_aci], ignore_index=True)

    return df_aci
