import pandas as pd

# NOTE: this file converts per-group metrics into a 0 - 1 scale, then combines them into a single ACI score

# NOTE: This is where the weights can be modified - will implement better controls in future
FEATURE_WEIGHTS_OLD = {
    "claim_confirm_rate": 0.35, # How often do claims get confirmed?
    "on_time_rate": 0.15, # Does the attacker follow through on the agreement?
    "payment_incidence": 0.35, # How often do victims pay?
    "reextortion_inverse": 0.10, # How often do victims pay more than once?
    "ops_maturity": 0.05, # How mature are the attacker operations?
}

FEATURE_WEIGHTS = {
    "decrypt_success_rate": 0.35,
    "median_key_delivery_time": 0.25,
    "leak_removal_rate": 0.25,
    "reextortion_inverse": 0.15
}

# TODO !!!! - Implement features from thesis aka constrcut them from the raw data
# Decyrption Success Rate -> How often do victims get their data back?
# Median Time to Decryption -> How long does it take for victims to get their data back
# Leak Site Removal Adherence -> How often do attackers remove data from leak sites after payment?
# Reextortion Incidence -> How often do victims get re-extorted after initial payment?

def scale_0_1(s: pd.Series) -> pd.Series:
    s = s.astype(float)
    lo, hi = s.min(), s.max()
    if hi == lo:
        return s*0
    return (s - lo) / (hi - lo)

def combine_features(*dfs: pd.DataFrame) -> pd.DataFrame:
    out = None
    for d in dfs:
        if d is None or d.empty: 
            continue
        out = d if out is None else out.merge(d, on="group", how="outer")
    return out if out is not None else pd.DataFrame(columns=["group"])

def score(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["group","aci_score"])
    for k in FEATURE_WEIGHTS.keys():
        if k not in df:
            df[k] = None
    for col in ["claim_confirm_rate","on_time_rate","payment_incidence","reextortion_inverse","ops_maturity"]:
        if col in df and df[col].notna().any():
            df[col] = df[col].fillna(df[col].median())
            df[col] = scale_0_1(df[col])
        else:
            df[col] = 0.0
    avail = {k: w for k, w in FEATURE_WEIGHTS.items() if k in df.columns}
    wsum = sum(avail.values()) if avail else 1.0
    for k in avail:
        avail[k] = avail[k] / wsum
    df["aci_0_1"] = sum(df.get(k, 0)*w for k, w in avail.items())
    df["aci_score"] = (df["aci_0_1"] * 9 + 1).round(2)
    keep = ["group","aci_score","aci_0_1"] + [c for c in df.columns if c not in {"aci_score","aci_0_1"}]
    return df[keep].sort_values("aci_score", ascending=False)
