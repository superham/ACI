# Attacker Credibility Index (ACI)

# Version 1.0

# Created by Alex Kaariainen

Collect, normalize, and score ransomware groups for an **Attacker Credibility Index (ACI)**.

Sources: Ransomware.live (claims), Ransomwhere (payments), more to be added...

## Quick start

Got to https://www.ransomware.live/api and get a free API key for the pro service

```bash
python -m venv .venv && source .venv/bin/activate # init of python env may differ
pip install -r requirements.txt

# Set API Key
export RLIVE_API_KEY="< insert key here >" # Do this for each instance of shell running the tool

# Collect sample/real data
python -m aci_tool.cli collect --since 2024-01-01 --neg-limit 24

# Gather data from negotiation data / chats
python -m aci_tool.cli chat-features --input './data/raw/negotiations.jsonl' --out './data/processed/chat_features.csv'

# Compute group-based ACI scores based on previously collected and gathered data
python -m aci_tool.cli compute-aci --chat-features './data/processed/chat_features.csv' --claims './data/raw/ransomware_live.jsonl' --out './reports/aci_scores.csv'

# Optional: Compute ACI scores year-by-year
python -m aci_tool.cli compute-aci --chat-features './data/processed/chat_features.csv' --claims './data/raw/ransomware_live.jsonl' --out './reports/aci_scores_by_year.csv' --by-year

# Optional: Compute ACI scores up to a specific year (e.g., 2020)
python -m aci_tool.cli compute-aci --chat-features './data/processed/chat_features.csv' --claims './data/raw/ransomware_live.jsonl' --out './reports/aci_scores_2020.csv' --as-of-year 2020

```
