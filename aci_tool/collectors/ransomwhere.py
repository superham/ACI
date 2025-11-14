import os, json, requests
from ..utils import parse_dt, safe_float
from ..schemas import Payment

DUMP = "https://api.ransomwhe.re/export"
# static data - ... use for dev 

def fetch_payments():
    # print("I made it here lol")

    try:
        r = requests.get(DUMP, timeout=30)
        r.raise_for_status()
        data = r.json()
    except Exception: # TODO - no need to catch the failed request for full releae
        sample_path = os.path.join("data", "raw", "ransomwhere_sample.json")
        data = json.load(open(sample_path)) if os.path.exists(sample_path) else []
        
        if (not data):
            print("[RWHERE] No data available" ) # TODO: make this more verbose

    out = []
    # The API returns {"result": [...]} wrapper
    results = data.get("result", []) if isinstance(data, dict) else data
    
    for row in results:
        # Calculate total USD from transactions if available
        total_usd = 0
        tx_count = 0
        first_tx_time = None
        
        if "transactions" in row and row["transactions"]:
            tx_count = len(row["transactions"])
            total_usd = sum(tx.get("amountUSD", 0) for tx in row["transactions"])
            # Get earliest transaction time
            tx_times = [tx.get("time") for tx in row["transactions"] if tx.get("time")]
            first_tx_time = min(tx_times) if tx_times else None
        
        out.append(Payment(
            source="ransomwhere",
            family=row.get("family"),
            group=row.get("family"),
            address=row.get("address") or "unknown",
            first_tx_at=parse_dt(first_tx_time),
            amount_usd=safe_float(total_usd),
            tx_count=tx_count,
            extra={k: v for k, v in row.items() if k not in {
                "family", "address", "transactions"}}
        ))
    return out

def dump_raw(payments, path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        for p in payments:
            f.write(json.dumps(p.model_dump(), default=str) + "\n")
