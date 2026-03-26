# Attacker Credibility Index (ACI)

**Version 1.1** | Created by Alex Kaariainen

Collect, normalize, and score ransomware groups for an **Attacker Credibility Index (ACI)**.

Scores groups on three axes (0–10 scale):
- **R** (Reliability) — key delivery & decryption proof
- **T** (Threat Follow-Through) — do they act on leak threats?
- **I** (Integrity) — post-payment behavior, re-extortion signals

Sources: Ransomware.live (claims + negotiations), Ransomwhere (payments)

## Install

```bash
pip install -e ".[dev]"    # editable install with test deps
export RLIVE_API_KEY="<your key>"   # get one at https://www.ransomware.live/api
```

## Quick start — one command

```bash
# Full pipeline: collect → extract features → score
aci run --since 2024-01-01

# Same, but output as JSON
aci run --since 2024-01-01 --format json

# Reuse previously collected data (skip API calls)
aci run --skip-collect --format table
```

## Step-by-step usage

```bash
# 1. Collect raw data
aci collect --since 2024-01-01

# 2. Extract semantic features from negotiation chats
aci chat-features

# 3. Compute ACI scores
aci compute-aci
aci compute-aci --format table          # print to terminal
aci compute-aci --format json --out reports/scores.json
aci compute-aci --by-year               # year-by-year breakdown
aci compute-aci --as-of-year 2023       # cumulative up to 2023
```

## Query a single group

```bash
aci query lockbit
aci query "black basta" --by-year
aci query conti --format json
```

## Output formats

| Flag | Description |
|------|-------------|
| `--format csv` | CSV file (default) |
| `--format json` | JSON array of records |
| `--format table` | Pretty-printed terminal table |

All commands use sensible default paths (`data/raw/`, `data/processed/`, `reports/`). Override with `--out`, `--claims`, `--chat-features`, `--payments` as needed.

## Scoring methodology

```
ACI = (0.4 × R + 0.3 × T + 0.3 × I) × 10
```

Each score includes a **confidence** indicator (0–1) based on data volume (chat count, claim count, component coverage) and a **low_data** flag for groups with fewer than 2 negotiation chats.

## Development

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## Data flow

```
ransomware.live API ──→ claims.jsonl ──┐
                   ──→ negotiations.jsonl ──→ chat_features.csv ──┐
ransomwhere API ───→ ransomwhere.jsonl ──────────────────────────→├──→ ACI scores
                                                                  │
                                        claims.jsonl ─────────────┘
```
