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

# Compute (Key Delivery & Decryption Reliability)
def compute_reliability(df_group: pd.DataFrame) -> pd.Series:
    """
    reliability score per group [0,1]

    Uses:
      - sample_offer_rate
      - key_delivery_rate   (if available)
      - proof_success_rate  (optional, if available & non-NaN)

    Formula (TODO change):
      R = 0.6 * sample_offer_rate
          + 0.4 * key_delivery_rate
    If key_delivery_rate is missing, falls back to sample_offer_rate only
    """
    values = []
    for _, row in df_group.iterrows():
        sample = float(row.get("sample_offer_rate", np.nan))
        key = float(row.get("key_delivery_rate", np.nan))
        proof = float(row.get("proof_success_rate", np.nan))

        # Basic two-component weighted mean; include proof_success only if present
        components = []
        weights = []

        if not np.isnan(sample):
            components.append(sample)
            weights.append(0.6)

        if not np.isnan(key):
            components.append(key)
            weights.append(0.4)

        # TODO: needs testing
        # uncomment if proof_success can be trusted
        # if not np.isnan(proof):
        #     components.append(proof)
        #     weights.append(0.2)

        R = _nanmean(components, weights) if components else np.nan
        values.append(R)

    return pd.Series(values, index=df_group.index, name="R")

# Compute (Threat Follow-Through)
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
              publish_rate (0.6)
              leak_threat_rate (0.4)
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
            weights.append(0.6)

        if not np.isnan(leak_threat_rate):
            components.append(leak_threat_rate)
            weights.append(0.4)

        # Small bump for demonstrated on-time follow-through, if available
        if not np.isnan(on_time):
            components.append(on_time)
            weights.append(0.2)

        T = _nanmean(components, weights) if components else np.nan
        values.append(T)

    return pd.Series(values, index=df_group.index, name="T")

# Compute I_g (Post-Payment Integrity / Re-Extortion)
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
            weights.append(0.5)

        if not np.isnan(reextortion_rate):
            components.append(reextortion_rate)
            weights.append(0.3)

        if not np.isnan(resale_rate):
            components.append(resale_rate)
            weights.append(0.2)

        bad_score = _nanmean(components, weights) if components else 0.0
        bad_score = min(max(bad_score, 0.0), 1.0)  # clamp

        I = 1.0 - bad_score
        values.append(I)

    return pd.Series(values, index=df_group.index, name="I")

# Combine R, T, I -> ACI_g
def compute_aci(df_group: pd.DataFrame) -> pd.DataFrame:
    """
    Given a merged group-level feature table, compute:

      - R: key delivery & decryption reliability
      - T: threat follow-through
      - I: post-payment integrity (approximate)
      - ACI: overall attacker credibility index (0–10 scale)

    Formula (default weights):

      ACI_g_raw = 0.4 * R_g + 0.3 * T_g + 0.3 * I_g

    Then:
      ACI_g = ACI_g_raw * 10
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

    return df

# end-to-end ACI from file paths
# TODO figure out relative file paths and passing the params 
# TODO test this end-to-end
def compute_aci_from_files(
    chat_features_path: str,
    claims_path: str,
) -> pd.DataFrame:
    """
    High-level helper: read chat_features.csv and ransomware_live.jsonl,
    build group-level features, and compute ACI for each group.
    """
    # TODO: move out of function?
    from .compute import (
        load_chat_features,
        compute_chat_group_features,
        load_claims,
        compute_claim_group_features,
        combine_group_features,
    )

    df_chat = load_chat_features(chat_features_path)
    df_chat_group = compute_chat_group_features(df_chat)

    df_claims = load_claims(claims_path)
    df_claim_group = compute_claim_group_features(df_claims)

    df_group = combine_group_features(df_chat_group, df_claim_group)
    df_aci = compute_aci(df_group)
    return df_aci
