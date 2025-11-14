# Attacker Credibility Index (ACI)

# Version 1.0

# Created by Alex Kaariainen

Collect, normalize, and score ransomware groups for an **Attacker Credibility Index (ACI)**.

Sources: Ransomware.live (claims), Ransomwhere (payments), more to be added...

## Quick start

Got to https://www.ransomware.live/api and get a free API key for the pro service

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Set API Key
export RLIVE_API_KEY="< insert key here >" # Do this for each instance of shell running the tool
# I'll make this easier later

# Collect sample/real data (optional)
python -m aci_tool.cli collect --since 2024-01-01

```
