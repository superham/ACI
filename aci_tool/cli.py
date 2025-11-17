import argparse, os, json
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from .config import Config
from .collectors.ransomware_live import fetch_claims, dump_raw as dump_rlive
from .collectors.ransomwhere import fetch_payments, dump_raw as dump_rwhere
from .collectors.negotiations import fetch_negotiations, dump_raw_negotations
from .chat_semantic import extract_chat_features_from_jsonl
from .scoring import compute_aci_from_files

# Load environment variables from .env file
# Only thing we currently care about is the API key for ransomware.live
load_dotenv()

# Helper to ensure data directories exist
def ensure_dirs(cfg: Config):
    os.makedirs(os.path.join(cfg.data_dir, "raw"), exist_ok=True)
    os.makedirs(os.path.join(cfg.data_dir, "processed"), exist_ok=True)

# Load JSONL data from a file ( I really should have used json at this point but too far to to go back)
def load_jsonl(path):
    rows = []
    if not os.path.exists(path): 
        return rows
    with open(os.path) as f:
        for line in f:
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows

# Command: collect data from raw sources e.g. ransomware.live and ransomwhere
def cmd_collect(args):
    cfg = Config(rlive_api_key=os.getenv("RLIVE_API_KEY"))
    ensure_dirs(cfg)
    
    claims = fetch_claims(cfg.rlive_api_key, since=args.since) # Think of claims like a suspected attack but may be unverified
    dump_rlive(claims, os.path.join(cfg.data_dir, "raw", "ransomware_live.jsonl")) # TODO: expand to handle extra sources
    
    pays = fetch_payments()
    dump_rwhere(pays, os.path.join(cfg.data_dir, "raw", "ransomwhere.jsonl")) # TODO: same as above

    negs = fetch_negotiations(cfg.rlive_api_key, limit_groups=args.neg_limit)
    dump_raw_negotations(negs, os.path.join(cfg.data_dir, "raw", "negotiations.jsonl"))
   
    print(f"Collected: {len(claims)} claims, {len(pays)} payments.")

# Command: extract chat features from negotiations.jsonl
def cmd_chat_features(args):
    rows = list(extract_chat_features_from_jsonl(args.input))
    df = pd.DataFrame(rows)
    df.to_csv(args.out, index=False)
    print(f"[ACI] Wrote {len(df)} chat feature rows → {args.out}")

# Command: compute ACI from chat features and claims
def cmd_score_aci(args):
    """
    Compute the Attacker Credibility Index (ACI) per group and write to CSV.
    """


    df = compute_aci_from_files(
        chat_features_path=args.chat_features,
        claims_path=args.claims,
    )
    # Save as CSV
    df.to_csv(args.out, index=False)
    print(f"[ACI] Wrote ACI scores for {len(df)} groups → {args.out}")


def main():
    p = argparse.ArgumentParser(prog="aci_tool")
    sub = p.add_subparsers(required=True)

    # collect
    pc = sub.add_parser("collect", help="Fetch raw data from sources")
    pc.add_argument("--since", help="ISO date (e.g., 2024-01-01)", default=None)
    pc.add_argument(
        "--neg-limit",
        type=int,
        default=5, # default of 5 because each group has lots of chats
        help="Max negotiation groups to fetch from the ransomware.live API",
    )
    pc.set_defaults(func=cmd_collect)

    # chat features
    pc = sub.add_parser("chat-features")
    pc.add_argument("--input", required=True, help="Path to negotiations.jsonl") # TODO: make this a relative path
    pc.add_argument("--out", required=True, help="Where to write chat_features.csv")
    pc.set_defaults(func=cmd_chat_features)

    # compute ACI
    pc = sub.add_parser("compute-aci")
    pc.add_argument("--chat-features", required=True, help="Path to chat_features.csv") # TODO: make this a relative path
    pc.add_argument("--claims", required=True, help="Path to ransomware_live.jsonl") # TODO: make this a relative path
    pc.add_argument("--out", required=True, help="Where to write ACI scores (CSV)")
    pc.set_defaults(func=cmd_score_aci)

    args = p.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
