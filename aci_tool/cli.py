import argparse, os, json
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from .config import Config
from .collectors.ransomware_live import fetch_claims, dump_raw as dump_rlive
from .collectors.ransomwhere import fetch_payments, dump_raw as dump_rwhere

# Load environment variables from .env file
load_dotenv()

# Helper to ensure data directories exist
def ensure_dirs(cfg: Config):
    os.makedirs(os.path.join(cfg.data_dir, "raw"), exist_ok=True)
    os.makedirs(os.path.join(cfg.data_dir, "processed"), exist_ok=True)

# Command: collect data from raw sources e.g. ransomware.live and ransomwhere
def cmd_collect(args):
    cfg = Config(rlive_api_key=os.getenv("RLIVE_API_KEY"))
    ensure_dirs(cfg)
    
    claims = fetch_claims(cfg.rlive_api_key, since=args.since) # Think of claims like a suspected attack but may be unverified
    dump_rlive(claims, os.path.join(cfg.data_dir, "raw", "ransomware_live.jsonl")) # TODO: expand to handle extra sources
    
    pays = fetch_payments()
    dump_rwhere(pays, os.path.join(cfg.data_dir, "raw", "ransomwhere.jsonl")) # TODO: same as above
   
    print(f"Collected: {len(claims)} claims, {len(pays)} payments.")

def main():
    p = argparse.ArgumentParser(prog="aci_tool")
    sub = p.add_subparsers(required=True)

    pc = sub.add_parser("collect", help="Fetch raw data from sources")
    pc.add_argument("--since", help="ISO date (e.g., 2024-01-01)", default=None)
    pc.set_defaults(func=cmd_collect)

    args = p.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
