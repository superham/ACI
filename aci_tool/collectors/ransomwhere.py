import json
import os

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..schemas import Payment
from ..utils import parse_dt, safe_float

DUMP = "https://api.ransomwhe.re/export"
# static data - ... use for dev


def _session_with_retries() -> requests.Session:
    # Retry transient upstream failures (502/503/504) and rate limits (429),
    # plus connection errors / read timeouts handled by urllib3 by default.
    retry = Retry(
        total=4,
        backoff_factor=2,  # 2s, 4s, 8s, 16s
        status_forcelist=(429, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
        raise_on_status=False,
    )
    s = requests.Session()
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.mount("http://", HTTPAdapter(max_retries=retry))
    return s


def fetch_payments():
    session = _session_with_retries()
    try:
        r = session.get(DUMP, timeout=30)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"[RWHERE] Error fetching payments: {e}")
        raise

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

        out.append(
            Payment(
                source="ransomwhere",
                family=row.get("family"),
                group=row.get("family"),
                address=row.get("address") or "unknown",
                first_tx_at=parse_dt(first_tx_time),
                amount_usd=safe_float(total_usd),
                tx_count=tx_count,
                extra={k: v for k, v in row.items() if k not in {"family", "address", "transactions"}},
            )
        )
    return out


def dump_raw(payments, path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        for p in payments:
            f.write(json.dumps(p.model_dump(), default=str) + "\n")
