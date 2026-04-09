"""
Generate a dashboard-ready JSON file for the ACI web dashboard.

Takes ACI scoring outputs and transforms them into the JSON structure
expected by the aci-web React frontend. Applies exclusion criteria
(groups need 2+ years of data with 1+ event per year) so only
sufficiently-documented groups appear on the dashboard.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np
import pandas as pd

from .compute import load_chat_features
from .scoring import compute_aci_from_files


def _safe_round(val: Any, decimals: int = 2) -> Any:
    """Round a value if numeric, otherwise return as-is."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    try:
        return round(float(val), decimals)
    except (TypeError, ValueError):
        return val


def _safe_int(val: Any, default: int = 0) -> int:
    """Convert a value to int, returning default for None/NaN/pd.NA."""
    if val is None or pd.isna(val):
        return default
    return int(val)


def _apply_exclusion_criteria(
    df_total: pd.DataFrame,
    df_yearly: pd.DataFrame,
    min_years: int = 2,
    min_events_per_year: int = 1,
) -> list[str]:
    """
    Return list of group names that pass the dashboard exclusion criteria.

    Criteria: A group must have at least `min_years` distinct years of data,
    with at least `min_events_per_year` documented events (negotiation chats)
    in each of those years.
    """
    if "year" not in df_yearly.columns:
        return sorted(df_total["group"].dropna().unique().tolist())

    # Filter to rows where n_chats >= min_events_per_year
    yearly_with_data = df_yearly[
        (df_yearly["year"] != "TOTAL")
        & (df_yearly["n_chats"].fillna(0) >= min_events_per_year)
    ]

    # Count distinct qualifying years per group
    year_counts = yearly_with_data.groupby("group")["year"].nunique()
    qualifying = year_counts[year_counts >= min_years].index.tolist()

    return sorted(qualifying)


def _build_overview_stats(
    df_total: pd.DataFrame,
    qualifying_groups: list[str],
    n_chats_total: int,
    n_payments_total: int,
) -> list[dict]:
    """Build the overview statistics cards."""
    filtered = df_total[df_total["group"].isin(qualifying_groups)]
    aci_vals = filtered["ACI"].dropna()

    aci_range = "N/A"
    if len(aci_vals) > 0:
        aci_range = f"{aci_vals.min():.1f} - {aci_vals.max():.1f}"

    return [
        {"label": "Ransomware Brands Scored:", "value": str(len(qualifying_groups))},
        {"label": "Negotiation Transcripts:", "value": f"{n_chats_total:,}"},
        {"label": "ACI Range", "value": aci_range},
        {"label": "Payment Records", "value": f"{n_payments_total:,}"},
    ]


def _build_total_aci_values(
    df_total: pd.DataFrame, qualifying_groups: list[str]
) -> list[dict]:
    """Build the total ACI values for the bar chart."""
    filtered = df_total[df_total["group"].isin(qualifying_groups)].copy()
    filtered = filtered.sort_values("ACI", ascending=False)

    results = []
    for _, row in filtered.iterrows():
        results.append(
            {
                "brand": str(row["group"]),
                "aciValue": _safe_round(row.get("ACI")),
            }
        )
    return results


def _build_per_year_aci_values(
    df_yearly: pd.DataFrame, qualifying_groups: list[str]
) -> list[dict]:
    """Build per-year ACI values for the line chart."""
    if "year" not in df_yearly.columns:
        return []

    filtered = df_yearly[
        (df_yearly["group"].isin(qualifying_groups))
        & (df_yearly["year"] != "TOTAL")
    ].copy()

    results = []
    for _, row in filtered.iterrows():
        year_val = row["year"]
        try:
            year_val = int(float(year_val))
        except (ValueError, TypeError):
            continue

        results.append(
            {
                "brand": str(row["group"]),
                "aciValue": _safe_round(row.get("ACI")),
                "year": year_val,
            }
        )
    return sorted(results, key=lambda x: (x["brand"], x["year"]))


def _build_rti_values(
    df_total: pd.DataFrame, qualifying_groups: list[str]
) -> list[dict]:
    """Build R, T, I component values for the clustered bar / radar charts."""
    filtered = df_total[df_total["group"].isin(qualifying_groups)].copy()
    filtered = filtered.sort_values("ACI", ascending=False)

    results = []
    for _, row in filtered.iterrows():
        results.append(
            {
                "brand": str(row["group"]),
                "r": _safe_round(row.get("R")),
                "t": _safe_round(row.get("T")),
                "i": _safe_round(row.get("I")),
            }
        )
    return results


def _build_outcome_metrics(
    df_total: pd.DataFrame,
    df_chat_features: pd.DataFrame,
    qualifying_groups: list[str],
) -> list[dict]:
    """Build outcome metrics table from chat features."""
    results = []

    for group in qualifying_groups:
        group_chats = df_chat_features[
            df_chat_features["group"].str.lower() == group.lower()
        ]
        group_aci = df_total[df_total["group"].str.lower() == group.lower()]

        if group_chats.empty:
            continue

        n = len(group_chats)
        aci_val = _safe_round(group_aci["ACI"].iloc[0]) if not group_aci.empty else None

        # Payment frequency
        paid_rate = group_chats["paid"].sum() / n if "paid" in group_chats.columns else 0
        # Discount frequency
        discount_freq = (
            group_chats["gave_discount"].mean()
            if "gave_discount" in group_chats.columns
            else 0
        )
        # Discount amount (average discount ratio among those who gave discounts)
        discount_amt = 0.0
        if "discount_ratio" in group_chats.columns and "gave_discount" in group_chats.columns:
            discounted = group_chats[group_chats["gave_discount"] == 1]
            if len(discounted) > 0:
                discount_amt = discounted["discount_ratio"].mean()

        # Re-extortion rate
        reextortion_rate = 0.0
        if "any_reextortion_behavior" in group_chats.columns:
            reextortion_rate = group_chats["any_reextortion_behavior"].sum() / n

        results.append(
            {
                "brand": group,
                "aci": aci_val,
                "frequencyOfRansomPayments": f"{paid_rate * 100:.0f}%",
                "discountFrequency": f"{discount_freq * 100:.0f}%",
                "discountAmount": f"{discount_amt * 100:.0f}%",
                "rateOfReExtortion": f"{reextortion_rate * 100:.0f}%",
            }
        )

    return sorted(results, key=lambda x: x["brand"])


def _build_confidence_data(
    df_total: pd.DataFrame, qualifying_groups: list[str]
) -> list[dict]:
    """Build confidence scores and data volume metadata per group."""
    filtered = df_total[df_total["group"].isin(qualifying_groups)].copy()

    results = []
    for _, row in filtered.iterrows():
        results.append(
            {
                "brand": str(row["group"]),
                "confidence": _safe_round(row.get("confidence")),
                "nChats": _safe_int(row.get("n_chats")),
                "totalClaims": _safe_int(row.get("total_claims")),
                "lowData": bool(_safe_int(row.get("low_data"))),
            }
        )
    return sorted(results, key=lambda x: x["brand"])


def _build_group_details(
    df_total: pd.DataFrame,
    df_yearly: pd.DataFrame,
    df_chat_features: pd.DataFrame,
    qualifying_groups: list[str],
) -> list[dict]:
    """Build detailed per-group data for group detail pages."""
    results = []

    for group in qualifying_groups:
        group_total = df_total[df_total["group"].str.lower() == group.lower()]
        if group_total.empty:
            continue
        row = group_total.iloc[0]

        # Years active
        group_yearly = df_yearly[
            (df_yearly["group"].str.lower() == group.lower())
            & (df_yearly["year"] != "TOTAL")
        ] if "year" in df_yearly.columns else pd.DataFrame()

        years_active = sorted(
            [int(float(y)) for y in group_yearly["year"].dropna().unique()
             if str(y) != "TOTAL"]
        ) if not group_yearly.empty else []

        # Per-year trend
        yearly_trend = []
        for _, yr_row in group_yearly.iterrows():
            try:
                year_val = int(float(yr_row["year"]))
            except (ValueError, TypeError):
                continue
            yearly_trend.append(
                {
                    "year": year_val,
                    "aci": _safe_round(yr_row.get("ACI")),
                    "r": _safe_round(yr_row.get("R")),
                    "t": _safe_round(yr_row.get("T")),
                    "i": _safe_round(yr_row.get("I")),
                }
            )
        yearly_trend.sort(key=lambda x: x["year"])

        results.append(
            {
                "brand": group,
                "aci": _safe_round(row.get("ACI")),
                "r": _safe_round(row.get("R")),
                "t": _safe_round(row.get("T")),
                "i": _safe_round(row.get("I")),
                "confidence": _safe_round(row.get("confidence")),
                "nChats": _safe_int(row.get("n_chats")),
                "totalClaims": _safe_int(row.get("total_claims")),
                "yearsActive": years_active,
                "yearlyTrend": yearly_trend,
            }
        )

    return sorted(results, key=lambda x: x["brand"])


def generate_dashboard_json(
    chat_features_path: str,
    claims_path: str,
    payments_path: Optional[str] = None,
) -> dict:
    """
    Generate the complete dashboard JSON structure.

    Runs ACI scoring (total + per-year), applies exclusion criteria,
    and builds all data sections needed by the aci-web frontend.
    """
    # Compute total scores
    df_total = compute_aci_from_files(
        chat_features_path=chat_features_path,
        claims_path=claims_path,
        payments_path=payments_path,
        by_year=False,
    )

    # Compute per-year scores
    df_yearly = compute_aci_from_files(
        chat_features_path=chat_features_path,
        claims_path=claims_path,
        payments_path=payments_path,
        by_year=True,
    )

    # Load chat features for outcome metrics
    df_chat_features = load_chat_features(chat_features_path)

    # Apply exclusion criteria
    qualifying_groups = _apply_exclusion_criteria(df_total, df_yearly)

    # Count totals for overview
    n_chats_total = int(df_chat_features["chat_id"].nunique()) if "chat_id" in df_chat_features.columns else len(df_chat_features)
    n_payments_total = 0
    if payments_path and os.path.exists(payments_path):
        try:
            df_payments = pd.read_json(payments_path, lines=True)
            n_payments_total = len(df_payments)
        except Exception:
            pass

    # Build all sections
    dashboard = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "overviewStats": _build_overview_stats(
            df_total, qualifying_groups, n_chats_total, n_payments_total
        ),
        "totalACIValues": _build_total_aci_values(df_total, qualifying_groups),
        "perYearACIValues": _build_per_year_aci_values(df_yearly, qualifying_groups),
        "rtiValues": _build_rti_values(df_total, qualifying_groups),
        "outcomeMetrics": _build_outcome_metrics(
            df_total, df_chat_features, qualifying_groups
        ),
        "confidenceData": _build_confidence_data(df_total, qualifying_groups),
        "groupDetails": _build_group_details(
            df_total, df_yearly, df_chat_features, qualifying_groups
        ),
    }

    return dashboard


def write_dashboard_json(dashboard: dict, output_path: str) -> None:
    """Write the dashboard JSON to a file."""
    parent = os.path.dirname(output_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(dashboard, f, indent=2)

    n_groups = len(dashboard.get("totalACIValues", []))
    print(f"[ACI] Dashboard JSON written: {n_groups} groups \u2192 {output_path}")
