# Determines decrption success rate, time to key, and re-extortion attempts
# NOTE: Modify the --neg-limit flag to limit the number of groups we pull
#       It defaults to only 5 in cli.py
#       This is a time-consuming process, so ramp up the neg-limit in increments

import os, json, requests
from typing import Optional, List
from ..schemas import Negotiation
from ..utils import parse_dt  # TODO can use to normalize timestamps later 

BASE = "https://api-pro.ransomware.live"

# Call /negotiations to get list of groups that have negotiation logs.
def fetch_negotiation_groups(api_key: str):
    headers = {"User-Agent": "ACI-Toolkit/0.1", "X-API-KEY": api_key}
    url = f"{BASE}/negotiations"
    r = requests.get(url, headers=headers, timeout=30)
    print("[NEGOTIATIONS] groups status:", r.status_code)
    r.raise_for_status()
    data = r.json()
    
    print (f"[NEGOTIATIONS] groups in response: {len(data)}")
    # print(data)
    return data

# Call /negotiations/{group} to list chat metadata for that group.
def fetch_group_chats(api_key: str, group: str):
    headers = {"User-Agent": "ACI-Toolkit/0.1", "X-API-KEY": api_key}
    url = f"{BASE}/negotiations/{group}"
    r = requests.get(url, headers=headers, timeout=30)
    print(f"[NEGOTIATIONS] {group} chats status:", r.status_code)
    if r.status_code == 404: # Not sure why it is returning this value tbh TODO investigate later
        print(f"[NEGOTIATIONS] {group} has no chats (404), skipping.")
        return []
    r.raise_for_status()
    data = r.json()
    
    # Response format: {"client": "...", "group": "Akira", "count": 61, "chats": [{"id": "20230529", ...}, ...]}
    if isinstance(data, dict) and "chats" in data:
        return data["chats"]
    
    #print(f"[NEGOTIATIONS] {group} chats in response: {len(data)}")
    #print(data)
    return data


# Call /negotiations/{group}/{chat_id} to get full messages + ransom info.
def fetch_chat_detail(api_key: str, group: str, chat_id: str):
    headers = {"User-Agent": "ACI-Toolkit/0.1", "X-API-KEY": api_key}
    url = f"{BASE}/negotiations/{group}/{chat_id}"
    r = requests.get(url, headers=headers, timeout=30)
    print(f"[NEGOTIATIONS] {group}/{chat_id} detail status:", r.status_code)
    r.raise_for_status()
    return r.json()


def fetch_negotiations(api_key: Optional[str], limit_groups: Optional[int] = None) -> List[Negotiation]:
    """
    High-level collector:
      - lists groups with negotiations
      - fetches each group's chat metadata
      - fetches full chat detail for each chat
      - returns list[Negotiation]
    """
    if not api_key:
        print("[NEGOTIATIONS] No API key; returning empty list.")
        return []

    groups_info = fetch_negotiation_groups(api_key)
    # Example response format: {"client": "...", "count": 24, "groups": [{"group": "Akira", "chats": 61}, ...]}
    if isinstance(groups_info, dict) and "groups" in groups_info:
        groups = [g["group"] for g in groups_info["groups"] if "group" in g]
    elif isinstance(groups_info, dict):
        groups = list(groups_info.keys())
    elif groups_info and isinstance(groups_info[0], dict):
        groups = [g["group"] for g in groups_info if "group" in g]
    else:
        groups = [str(g) for g in groups_info]

    if limit_groups is not None:
        groups = groups[:limit_groups]

    records: List[Negotiation] = []

    for g in groups:
        print(f"[NEGOTIATIONS] Fetching chats for group: {g}")
        chats_meta = fetch_group_chats(api_key, g)
        for chat in chats_meta:
            # Chat object has "id" field, not "chat_id"
            chat_id = chat.get("id") or chat.get("chat_id")
            if not chat_id:
                continue

            detail = fetch_chat_detail(api_key, g, chat_id)

            messages = detail.get("messages", [])
            ransominfo = detail.get("ransominfo", {})

            # Try to pull some generic time bounds; actual feature logic will be elsewhere
            started_at = None
            ended_at = None
            if messages:
                # assuming messages have a "time" or "timestamp" field
                first = messages[0]
                last = messages[-1]
                started_at = first.get("time") or first.get("timestamp")
                ended_at = last.get("time") or last.get("timestamp")

            rec = Negotiation(
                group=g,
                chat_id=str(chat_id),
                victim=chat.get("victim") or ransominfo.get("victim"),
                started_at=started_at,
                ended_at=ended_at,
                messages=messages,
                ransominfo=ransominfo,
                meta={k: v for k, v in chat.items() if k not in {"chat_id", "id", "victim"}}
            )
            records.append(rec)

    print(f"[NEGOTIATIONS] collected {len(records)} chats across {len(groups)} groups.")
    return records


def dump_raw_negotations(records: List[Negotiation], path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        for rec in records:
            f.write(json.dumps(rec.model_dump(), default=str) + "\n")
