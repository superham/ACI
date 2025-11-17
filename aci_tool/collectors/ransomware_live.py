import os, json, requests
from typing import Optional, List
from ..utils import parse_dt
from ..schemas import Claim

# Pro API ransomware - used to infer leak site removal
BASE = "https://api-pro.ransomware.live"
VICTIMS_RECENT_PATH = "/victims/recent" # recent -> last 100 victims, sorted by discovery date

def fetch_claims(api_key: Optional[str], since: Optional[str] = None) -> List[Claim]:
    headers = {"User-Agent": "ACI-Toolkit/0.1"}
    if api_key:
        headers["X-API-KEY"] = api_key  # set within shell env 

    # /victims/recent supports ?order=discovered or attacked
    params = {"order": "discovered"}

    url = f"{BASE}{VICTIMS_RECENT_PATH}"
    try:
        r = requests.get(url, headers=headers, params=params, timeout=30)
        print("[RLIVE PRO] status:", r.status_code) # TODO: remove prints / clean up
        print("[RLIVE PRO] snippet:", r.text[:200]) # TODO: smart check for missing api key here
        
        if (r.status_code == 401):
            raise Exception("Check your API key")

        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print("[RLIVE PRO] ERROR:", repr(e))
        sample_path = os.path.join("data", "raw", "ransomware_live_sample.json")
        if os.path.exists(sample_path):
            print("[RLIVE PRO] Falling back to sample:", sample_path)
            data = json.load(open(sample_path))
        else:
            data = []

    claims: List[Claim] = []
    rows = data.get("victims", []) if isinstance(data, dict) else data
    print(f"[RLIVE PRO] victims in response: {len(rows)}")

    for row in rows:
        claims.append(Claim(
        source="ransomware_live_pro",

        # Actor / Group
        group=row.get("group"),
        group_alias=row.get("group"),

        # Victim identity
        victim_legal_name=row.get("victim") or row.get("website") or row.get("description"),
        victim_domain=row.get("victim") or None,

        # Metadata
        sector=row.get("activity"),
        country=row.get("country"),

        # Dates
        claim_date=parse_dt(row.get("discovered")),     # date RLIVE discovered the victim
        publish_date=parse_dt(row.get("attackdate")),   # the real attack date
        deadline=None,                                   # PRO API does not supply deadlines - data might be pay walled

        # Links
        post_url=row.get("post_url"),
        extra={
            "description": row.get("description"),
            "permalink": row.get("permalink"),
            "screenshot": row.get("screenshot"),
            "infostealer": row.get("infostealer"),
            "press": row.get("press"),
            "id": row.get("id"),
            "attackdate": row.get("attackdate"),
            "duplicates": row.get("duplicates"),
            "extrainfos": row.get("extrainfos"),
        }
    ))

    return claims

def dump_raw(claims: List[Claim], path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        for c in claims:
            f.write(json.dumps(c.model_dump(), default=str) + "\n")
