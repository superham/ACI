import os, json, requests
from ..utils import parse_dt, safe_float
from ..schemas import Payment

DUMP = "https://ransomwhere.github.io/ransomwhere-data/ransomwhere_data.json"
# static data - ... use for dev 

def fetch_payments():
    try:
        r = requests.get(DUMP, timeout=30)
        r.raise_for_status()
        data = r.json()
    except Exception: # TODO - no need to catch the failed request for full releae
        sample_path = os.path.join("data", "raw", "ransomwhere_sample.json")
        data = json.load(open(sample_path)) if os.path.exists(sample_path) else []

    out = []
    for row in data:
        out.append(Payment(
            source="ransomwhere",
            family=row.get("ransomware_family"),
            group=row.get("ransomware_family"),
            address=row.get("payment_address") or "unknown",
            first_tx_at=parse_dt(row.get("first_transaction_time")),
            amount_usd=safe_float(row.get("total_usd_paid")),
            tx_count=row.get("transaction_count"),
            extra={k: v for k, v in row.items() if k not in {
                "ransomware_family","payment_address","first_transaction_time","total_usd_paid","transaction_count"}}
        ))
    return out

def dump_raw(payments, path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        for p in payments:
            f.write(json.dumps(p.model_dump(), default=str) + "\n")
