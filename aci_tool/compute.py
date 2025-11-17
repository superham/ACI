"""
Compute group-level features needed to build the Attacker Credibility Index (ACI)

Inputs:
- chat_features.csv     (output from chat_semantic.extract_chat_features_from_jsonl)
- ransomware_live.jsonl (raw claims data from ransomware.live collectors)

Outputs
- Group-level chat behavior features
- Group-level claim/publish features
- A merged DataFrame per group, ready for scoring func
"""

from __future__ import annotations
from typing import Optional
import pandas as pd
import numpy as np

# aggregate chat_features.csv → per-group features
def load_chat_features(path: str) -> pd.DataFrame:
    """
    Load chat_features.csv produced by chat_semantic.py.

    Expected columns (required):
      - group
      - chat_id
      - paid
      - any_proof_offer
      - any_leak_threat
      - gave_discount
      - discount_ratio

    Optional columns (for future updated PROTOTYPES and redo extractions):
      - any_key_delivery
      - any_deletion_promise
      - any_violation_claim
      - any_reextortion_behavior
      - any_data_resale_admission
      - any_proof_success
    """
    df = pd.read_csv(path)
    if "group" not in df.columns:
        raise ValueError("chat_features.csv must contain a 'group' column.")
    return df


def compute_chat_group_features(df_chat: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate chat-level semantic features to one row per ransomware group.

    Returns a DataFrame with columns like:
      - group
      - n_chats
      - n_paid_chats
      - sample_offer_rate
      - key_delivery_rate (if available)
      - leak_threat_rate
      - discount_frequency
      - discount_generosity
      - deletion_promise_rate (if available)
      - violation_claim_rate (if available)
      - reextortion_behavior_rate (if available)
      - data_resale_admission_rate (if available)
    """
    records = []

    # Check optional columns ahead of time
    optional_any_cols = [
        "any_key_delivery",
        "any_deletion_promise",
        "any_violation_claim",
        "any_reextortion_behavior",
        "any_data_resale_admission",
        "any_proof_success",
    ]
    has_col = {c: c in df_chat.columns for c in optional_any_cols}

    for group, sub in df_chat.groupby("group"):
        row: dict[str, Optional[float]] = {"group": group}

        n_chats = len(sub)
        row["n_chats"] = int(n_chats)
        row["n_paid_chats"] = int(sub.get("paid", 0).sum())

        # Core: sample offers
        if "any_proof_offer" in sub.columns:
            row["sample_offer_rate"] = float(sub["any_proof_offer"].sum() / n_chats)
        else:
            row["sample_offer_rate"] = np.nan

        # Core: key delivery (optional semantic label)
        if has_col["any_key_delivery"]:
            row["key_delivery_rate"] = float(sub["any_key_delivery"].sum() / max(n_chats, 1))
        else:
            row["key_delivery_rate"] = np.nan

        # Optional: proof success rate (among chats with proof_offer)
        if has_col["any_proof_success"] and "any_proof_offer" in sub.columns:
            offers = sub[sub["any_proof_offer"] == 1]
            if len(offers) > 0:
                row["proof_success_rate"] = float(offers["any_proof_success"].sum() / len(offers))
            else:
                row["proof_success_rate"] = np.nan
        else:
            row["proof_success_rate"] = np.nan

        # Leak threat usage in negotiations
        if "any_leak_threat" in sub.columns:
            row["leak_threat_rate"] = float(sub["any_leak_threat"].sum() / n_chats)
        else:
            row["leak_threat_rate"] = np.nan

        # Discount behavior
        if "gave_discount" in sub.columns:
            row["discount_frequency"] = float(sub["gave_discount"].mean())
        else:
            row["discount_frequency"] = np.nan

        if "discount_ratio" in sub.columns:
            row["discount_generosity"] = float(sub["discount_ratio"].mean(skipna=True))
        else:
            row["discount_generosity"] = np.nan

        # Deletion/re-extortion semantics if present
        if has_col["any_deletion_promise"]:
            row["deletion_promise_rate"] = float(sub["any_deletion_promise"].sum() / n_chats)
        else:
            row["deletion_promise_rate"] = np.nan

        if has_col["any_violation_claim"]:
            row["violation_claim_rate"] = float(sub["any_violation_claim"].sum() / n_chats)
        else:
            row["violation_claim_rate"] = np.nan

        if has_col["any_reextortion_behavior"]:
            row["reextortion_behavior_rate"] = float(sub["any_reextortion_behavior"].sum() / n_chats)
        else:
            row["reextortion_behavior_rate"] = np.nan

        if has_col["any_data_resale_admission"]:
            row["data_resale_admission_rate"] = float(sub["any_data_resale_admission"].sum() / n_chats)
        else:
            row["data_resale_admission_rate"] = np.nan

        records.append(row)

    return pd.DataFrame.from_records(records)


# CLAIM FEATURES: aggregate ransomware_live.jsonl → per-group features
def load_claims(path: str) -> pd.DataFrame:
    """
    Load ransomware_live.jsonl that contains raw claims/leak data.

    Expected columns:
      - group
      - claim_date
      - publish_date  (might be null / empty if not yet leaked)
      - deadline      (might be null)
    """
    df = pd.read_json(path, lines=True)
    if "group" not in df.columns:
        raise ValueError("ransomware_live.jsonl must contain a 'group' column.")
    return df


def compute_claim_group_features(df_claims: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate ransomware.live claims to one row per group.

    Features:
      - total_claims
      - published_claims
      - publish_rate
      - with_deadline
      - with_deadline_and_publish
      - on_time_publish_rate (if deadlines present/found/parsed)
    """
    # Normalize publish_date as a boolean "has_publish"
    has_publish = df_claims["publish_date"].astype(str).str.strip().ne("")
    df_claims = df_claims.assign(has_publish=has_publish)

    # Parse datetime where possible
    for col in ["claim_date", "publish_date", "deadline"]:
        if col in df_claims.columns:
            df_claims[col] = pd.to_datetime(df_claims[col], errors="coerce")

    records = []
    for group, sub in df_claims.groupby("group"):
        row: dict[str, Optional[float]] = {"group": group}
        total = len(sub)
        row["total_claims"] = int(total)

        published = int(sub["has_publish"].sum())
        row["published_claims"] = published
        row["publish_rate"] = float(published / total) if total else np.nan

        # Basic deadline / on-time publish (only where both exist)
        has_deadline = sub["deadline"].notna().sum() if "deadline" in sub.columns else 0
        row["claims_with_deadline"] = int(has_deadline)

        on_time = np.nan
        on_time_rate = np.nan

        if has_deadline and "deadline" in sub.columns:
            # On-time where publish_date <= deadline
            mask = sub["deadline"].notna() & sub["publish_date"].notna()
            with_deadline_and_publish = sub[mask]
            row["claims_with_deadline_and_publish"] = int(len(with_deadline_and_publish))
            if len(with_deadline_and_publish) > 0:
                on_time = (with_deadline_and_publish["publish_date"] <= with_deadline_and_publish["deadline"]).sum()
                on_time_rate = float(on_time / len(with_deadline_and_publish))
            else:
                on_time_rate = np.nan
        else:
            row["claims_with_deadline_and_publish"] = 0

        row["on_time_publish_rate"] = on_time_rate

        records.append(row)

    return pd.DataFrame.from_records(records)


# COMBINE CHAT w/ CLAIM FEATURES → group-level feature table
def combine_group_features(
    df_chat_group: pd.DataFrame,
    df_claim_group: pd.DataFrame,
) -> pd.DataFrame:
    """
    Merge chat-derived features and claim-derived features on 'group'.

    Returns a single DataFrame per group with all intermediate features that
    scoring.py will use to build the ACI.
    """
    df = pd.merge(df_chat_group, df_claim_group, on="group", how="outer", suffixes=("_chat", "_claims"))
    # Sort groups alphabetically for sanity
    return df.sort_values("group").reset_index(drop=True)
