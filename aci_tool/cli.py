import argparse, os, json
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from .config import Config
from .collectors.ransomware_live import fetch_claims, dump_raw as dump_rlive
from .collectors.ransomwhere import fetch_payments, dump_raw as dump_rwhere
from .collectors.negotiations import fetch_negotiations, dump_raw_negotations
from .chat_semantic import extract_chat_features_from_jsonl
import pandas as pd
# from .compute import claim_confirmation_rate, on_time_publish_rate, payment_incidence
# from .linkage import link_claims_to_confirms
# from .scoring import combine_features, score

# Load environment variables from .env file
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

def cmd_chat_features(args):
    rows = list(extract_chat_features_from_jsonl(args.input))
    df = pd.DataFrame(rows)
    df.to_csv(args.out, index=False)
    print(f"[ACI] Wrote {len(df)} chat feature rows → {args.out}")

# Command: compute ACI scores with data from the collect call 
# def cmd_compute(args):
#     cfg = Config()
#     claims = pd.DataFrame(load_jsonl(os.path.join(cfg.data_dir, "raw", "ransomware_live.jsonl")))
#     pays = pd.DataFrame(load_jsonl(os.path.join(cfg.data_dir, "raw", "ransomwhere.jsonl")))
#     confirms = pd.DataFrame()

#     if args.window:
#         cutoff = pd.Timestamp.utcnow() - pd.Timedelta(days=args.window)
#         if not claims.empty and 'claim_date' in claims:
#             claims['claim_date'] = pd.to_datetime(claims['claim_date'], errors='coerce')
#             cutoff_naive = cutoff.tz_localize(None) if cutoff.tz else cutoff
#             claims = claims[claims['claim_date'].isna() | (claims['claim_date'] >= cutoff_naive)]
#         if not pays.empty and 'first_tx_at' in pays:
#             pays['first_tx_at'] = pd.to_datetime(pays['first_tx_at'], errors='coerce', utc=True)
#             pays = pays[pays['first_tx_at'].isna() | (pays['first_tx_at'] >= cutoff)]

#     links = link_claims_to_confirms(claims, confirms) if not claims.empty else pd.DataFrame()
#     f1 = claim_confirmation_rate(links)
#     f2 = on_time_publish_rate(claims)
#     f3 = payment_incidence(pays)

#     feats = combine_features(f1, f2, f3)
#     out = score(feats)
#     if args.out:
#         os.makedirs(os.path.dirname(args.out), exist_ok=True)
#         out.to_csv(args.out, index=False)
#         print(f"Wrote {args.out} (rows={len(out)})")
#     else:
#         print(out.head(20).to_string(index=False))

def main():
    p = argparse.ArgumentParser(prog="aci_tool")
    sub = p.add_subparsers(required=True)

    pc = sub.add_parser("collect", help="Fetch raw data from sources")
    pc.add_argument("--since", help="ISO date (e.g., 2024-01-01)", default=None)
    pc.add_argument(
        "--neg-limit",
        type=int,
        default=5, # default of 5 because each group has lots of chats
        help="Max negotiation groups to fetch from the ransomware.live API",
    )
    pc.set_defaults(func=cmd_collect)

    pc = sub.add_parser("chat-features")
    pc.add_argument("--input", required=True, help="Path to negotiations.jsonl") # TODO: make this a relative path
    pc.add_argument("--out", required=True, help="Where to write chat_features.csv")
    pc.set_defaults(func=cmd_chat_features)

    args = p.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
