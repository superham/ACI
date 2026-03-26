import argparse, os, json, sys
import pandas as pd
from dotenv import load_dotenv
from .config import Config
from .collectors.ransomware_live import fetch_claims, dump_raw as dump_rlive
from .collectors.ransomwhere import fetch_payments, dump_raw as dump_rwhere
from .collectors.negotiations import fetch_negotiations, dump_raw_negotations
from .chat_semantic import extract_chat_features_from_jsonl
from .scoring import compute_aci_from_files

load_dotenv()

# ── Default paths ──────────────────────────────────────────────────────
DATA_DIR = "data"
RAW_DIR = os.path.join(DATA_DIR, "raw")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
REPORTS_DIR = "reports"

DEFAULT_CLAIMS = os.path.join(RAW_DIR, "ransomware_live.jsonl")
DEFAULT_PAYMENTS = os.path.join(RAW_DIR, "ransomwhere.jsonl")
DEFAULT_NEGOTIATIONS = os.path.join(RAW_DIR, "negotiations.jsonl")
DEFAULT_CHAT_FEATURES = os.path.join(PROCESSED_DIR, "chat_features.csv")
DEFAULT_ACI_OUT = os.path.join(REPORTS_DIR, "aci_scores.csv")


def _ensure_dirs():
    for d in [RAW_DIR, PROCESSED_DIR, REPORTS_DIR]:
        os.makedirs(d, exist_ok=True)


# ── Output formatters ──────────────────────────────────────────────────
def _output(df: pd.DataFrame, path: str, fmt: str):
    """Write a DataFrame to the requested format and print a summary."""
    if fmt == "json":
        if not path.endswith(".json"):
            path = path.rsplit(".", 1)[0] + ".json"
        df.to_json(path, orient="records", indent=2)
    elif fmt == "table":
        print(df.to_string(index=False))
        return  # no file written
    else:  # csv (default)
        df.to_csv(path, index=False)
    print(f"[ACI] Wrote {len(df)} rows → {path}")


# ── Score display columns ─────────────────────────────────────────────
DISPLAY_COLS = [
    "group", "ACI", "R", "T", "I",
    "confidence", "low_data", "n_chats", "total_claims",
]

def _display_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Select and round the standard display columns that exist in df."""
    cols = [c for c in DISPLAY_COLS if c in df.columns]
    out = df[cols].copy()
    for c in ["ACI", "R", "T", "I", "confidence"]:
        if c in out.columns:
            out[c] = out[c].round(2)
    return out.sort_values("ACI", ascending=False).reset_index(drop=True)


# ── Commands ───────────────────────────────────────────────────────────
def cmd_collect(args):
    cfg = Config(rlive_api_key=os.getenv("RLIVE_API_KEY"))
    _ensure_dirs()

    claims = fetch_claims(cfg.rlive_api_key, since=args.since)
    dump_rlive(claims, DEFAULT_CLAIMS)

    pays = fetch_payments()
    dump_rwhere(pays, DEFAULT_PAYMENTS)

    negs = fetch_negotiations(cfg.rlive_api_key, limit_groups=args.neg_limit)
    dump_raw_negotations(negs, DEFAULT_NEGOTIATIONS)

    print(f"[ACI] Collected {len(claims)} claims, {len(pays)} payments, {len(negs)} negotiation chats.")


def cmd_chat_features(args):
    inpath = args.input or DEFAULT_NEGOTIATIONS
    outpath = args.out or DEFAULT_CHAT_FEATURES
    os.makedirs(os.path.dirname(outpath), exist_ok=True)
    print("[ACI] Extracting chat features (this may take a few minutes)...")
    rows = list(extract_chat_features_from_jsonl(inpath))
    df = pd.DataFrame(rows)
    df.to_csv(outpath, index=False)
    print(f"[ACI] Wrote {len(df)} chat feature rows → {outpath}")


def cmd_score_aci(args):
    chat_feat = args.chat_features or DEFAULT_CHAT_FEATURES
    claims = args.claims or DEFAULT_CLAIMS
    out = args.out or DEFAULT_ACI_OUT
    fmt = getattr(args, "format", "csv") or "csv"
    os.makedirs(os.path.dirname(out), exist_ok=True)

    payments = getattr(args, "payments", None) or DEFAULT_PAYMENTS
    df = compute_aci_from_files(
        chat_features_path=chat_feat,
        claims_path=claims,
        payments_path=payments,
        by_year=args.by_year,
        as_of_year=args.as_of_year,
    )
    _output(df, out, fmt)


def cmd_run(args):
    """One-shot pipeline: collect → extract features → compute ACI."""
    _ensure_dirs()

    # Step 1: Collect
    if not args.skip_collect:
        print("[ACI] Step 1/3: Collecting data...")
        cfg = Config(rlive_api_key=os.getenv("RLIVE_API_KEY"))
        claims = fetch_claims(cfg.rlive_api_key, since=args.since)
        dump_rlive(claims, DEFAULT_CLAIMS)
        pays = fetch_payments()
        dump_rwhere(pays, DEFAULT_PAYMENTS)
        negs = fetch_negotiations(cfg.rlive_api_key, limit_groups=args.neg_limit)
        dump_raw_negotations(negs, DEFAULT_NEGOTIATIONS)
        print(f"[ACI]   → {len(claims)} claims, {len(pays)} payments, {len(negs)} chats")
    else:
        print("[ACI] Step 1/3: Skipping collection (--skip-collect)")

    # Step 2: Chat features
    print("[ACI] Step 2/3: Extracting chat features...")
    rows = list(extract_chat_features_from_jsonl(DEFAULT_NEGOTIATIONS))
    df_feats = pd.DataFrame(rows)
    df_feats.to_csv(DEFAULT_CHAT_FEATURES, index=False)
    print(f"[ACI]   → {len(df_feats)} chat features extracted")

    # Step 3: Compute ACI
    print("[ACI] Step 3/3: Computing ACI scores...")
    out = args.out or DEFAULT_ACI_OUT
    fmt = getattr(args, "format", "csv") or "csv"

    df = compute_aci_from_files(
        chat_features_path=DEFAULT_CHAT_FEATURES,
        claims_path=DEFAULT_CLAIMS,
        payments_path=DEFAULT_PAYMENTS,
        by_year=args.by_year,
        as_of_year=args.as_of_year,
    )
    _output(df, out, fmt)

    # Always print a summary table at the end
    print("\n── ACI Scores ──")
    print(_display_cols(df).to_string(index=False))


def cmd_query(args):
    """Look up ACI score(s) for a specific group."""
    chat_feat = args.chat_features or DEFAULT_CHAT_FEATURES
    claims = args.claims or DEFAULT_CLAIMS
    fmt = getattr(args, "format", "table") or "table"

    if not os.path.exists(chat_feat):
        sys.exit(f"[ACI] Chat features not found at {chat_feat} — run 'aci run' or 'aci chat-features' first.")
    if not os.path.exists(claims):
        sys.exit(f"[ACI] Claims not found at {claims} — run 'aci run' or 'aci collect' first.")

    payments = getattr(args, "payments", None) or DEFAULT_PAYMENTS
    df = compute_aci_from_files(
        chat_features_path=chat_feat,
        claims_path=claims,
        payments_path=payments,
        by_year=args.by_year,
        as_of_year=args.as_of_year,
    )

    # Filter to requested group (case-insensitive partial match)
    target = args.group.strip().lower()
    mask = df["group"].str.lower().str.contains(target, na=False)
    matches = df[mask]

    if matches.empty:
        print(f"[ACI] No group matching '{args.group}' found.")
        available = sorted(df["group"].dropna().unique())
        if available:
            print(f"  Available groups: {', '.join(available[:20])}")
            if len(available) > 20:
                print(f"  ... and {len(available) - 20} more")
        return

    display = _display_cols(matches)

    if fmt == "json":
        print(matches.to_json(orient="records", indent=2))
    elif fmt == "csv":
        print(matches.to_csv(index=False))
    else:
        print(display.to_string(index=False))

    # Show detailed breakdown for single matches
    if len(matches) == 1:
        row = matches.iloc[0]
        print(f"\n── Breakdown: {row['group']} ──")
        print(f"  Reliability (R):        {row.get('R', 'N/A'):.2f}  (key delivery & decryption proof)")
        print(f"  Threat Follow-Through (T): {row.get('T', 'N/A'):.2f}  (leak threats acted on)")
        print(f"  Integrity (I):          {row.get('I', 'N/A'):.2f}  (post-payment behavior)")
        print(f"  ACI Score:              {row.get('ACI', 'N/A'):.2f} / 10")
        if "confidence" in row and pd.notna(row["confidence"]):
            print(f"  Confidence:             {row['confidence']:.2f}  (based on {int(row.get('n_chats', 0))} chats, {int(row.get('total_claims', 0))} claims)")


# ── Argument parser ────────────────────────────────────────────────────
def _add_format_arg(parser):
    parser.add_argument(
        "--format", "-f",
        choices=["csv", "json", "table"],
        default="csv",
        help="Output format (default: csv)",
    )


def main():
    p = argparse.ArgumentParser(
        prog="aci",
        description="Attacker Credibility Index — score ransomware groups on reliability, threat follow-through, and integrity.",
    )
    sub = p.add_subparsers(dest="command")

    # ── run (one-shot pipeline) ──
    pr = sub.add_parser("run", help="Full pipeline: collect → extract → score")
    pr.add_argument("--since", help="ISO date filter for claims (e.g., 2024-01-01)")
    pr.add_argument("--neg-limit", type=int, default=24, help="Max negotiation groups to fetch")
    pr.add_argument("--skip-collect", action="store_true", help="Skip data collection, reuse existing data")
    pr.add_argument("--out", help=f"Output path (default: {DEFAULT_ACI_OUT})")
    pr.add_argument("--by-year", action="store_true", help="Compute scores per year")
    pr.add_argument("--as-of-year", type=int, help="Compute scores up to this year")
    _add_format_arg(pr)
    pr.set_defaults(func=cmd_run)

    # ── collect ──
    pc = sub.add_parser("collect", help="Fetch raw data from sources")
    pc.add_argument("--since", help="ISO date filter for claims (e.g., 2024-01-01)")
    pc.add_argument("--neg-limit", type=int, default=24, help="Max negotiation groups to fetch")
    pc.set_defaults(func=cmd_collect)

    # ── chat-features ──
    pf = sub.add_parser("chat-features", help="Extract semantic features from negotiation chats")
    pf.add_argument("--input", help=f"Path to negotiations.jsonl (default: {DEFAULT_NEGOTIATIONS})")
    pf.add_argument("--out", help=f"Output path (default: {DEFAULT_CHAT_FEATURES})")
    pf.set_defaults(func=cmd_chat_features)

    # ── compute-aci ──
    pa = sub.add_parser("compute-aci", help="Compute ACI scores from processed data")
    pa.add_argument("--chat-features", help=f"Path to chat_features.csv (default: {DEFAULT_CHAT_FEATURES})")
    pa.add_argument("--claims", help=f"Path to ransomware_live.jsonl (default: {DEFAULT_CLAIMS})")
    pa.add_argument("--payments", help=f"Path to ransomwhere.jsonl (default: {DEFAULT_PAYMENTS})")
    pa.add_argument("--out", help=f"Output path (default: {DEFAULT_ACI_OUT})")
    pa.add_argument("--by-year", action="store_true", help="Compute scores per year")
    pa.add_argument("--as-of-year", type=int, help="Compute scores up to this year")
    _add_format_arg(pa)
    pa.set_defaults(func=cmd_score_aci)

    # ── query ──
    pq = sub.add_parser("query", help="Look up ACI score for a specific group")
    pq.add_argument("group", help="Group name (partial match, case-insensitive)")
    pq.add_argument("--chat-features", help=f"Path to chat_features.csv (default: {DEFAULT_CHAT_FEATURES})")
    pq.add_argument("--claims", help=f"Path to ransomware_live.jsonl (default: {DEFAULT_CLAIMS})")
    pq.add_argument("--by-year", action="store_true", help="Show scores per year")
    pq.add_argument("--as-of-year", type=int, help="Show scores up to this year")
    _add_format_arg(pq)
    pq.set_defaults(func=cmd_query)

    args = p.parse_args()
    if not args.command:
        p.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
