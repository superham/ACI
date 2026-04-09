# Attacker Credibility Index (ACI)

**Version 1.1** | Created by Alex Kaariainen

A quantitative framework for scoring ransomware groups on behavioral credibility. ACI collects operational data from public sources, extracts behavioral signals using NLP, and produces a per-group credibility score (ACI, 0-10 scale) derived from three behavioral axes (each 0-1). Designed for incident responders, ransom negotiation teams, and threat intelligence analysts who need to assess how credible a threat actor's promises and threats actually are.

## What ACI measures

Scores are computed on three axes (each 0-1):

- **R (Reliability)** -- Do they deliver working decryptors after payment? Measures proof-of-decryption offers, key delivery signals, and evidence of a functional payment-to-decryption pipeline.
- **T (Threat Follow-Through)** -- Do they act on their leak threats? Measures the rate at which threatened data publications actually occur and how often leak threats appear in negotiations.
- **I (Integrity)** -- Do they honor post-payment promises? Inversely measures re-extortion behavior, data resale admissions, and victim accusations of broken promises.

**Composite score:** `ACI = (0.4 x R + 0.3 x T + 0.3 x I) x 10`

Higher ACI = more credible (and therefore more dangerous) threat actor.

**Data sources:** [ransomware.live](https://www.ransomware.live) (claims + negotiation chats), [ransomwhere.re](https://ransomwhe.re) (cryptocurrency payments)

## Prerequisites

- Python >= 3.10
- A ransomware.live API key (get one at <https://www.ransomware.live/api>)
- On first run, the `all-MiniLM-L6-v2` sentence-transformer model (~80 MB) is downloaded automatically. This requires PyTorch, which is installed as a dependency.

## Install

```bash
pip install -e ".[dev]"    # editable install with test deps
export RLIVE_API_KEY="<your key>"   # get one at https://www.ransomware.live/api
```

## Quick start -- one command

```bash
# Full pipeline: collect -> extract features -> score
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

## How it works

1. **Collect** -- Pulls ransomware victim claims and full negotiation chat logs from the ransomware.live API, plus cryptocurrency payment data from ransomwhere.re. Raw data is saved as JSONL files in `data/raw/`.

2. **Extract features** -- Each negotiation chat message is embedded using a sentence-transformer model (`all-MiniLM-L6-v2`) and compared via cosine similarity against hand-crafted prototype sentences for behavioral categories: proof offers, key delivery, leak threats, deletion promises, re-extortion signals, and more. This produces per-chat feature flags, saved to `data/processed/chat_features.csv`.

3. **Score** -- Chat-derived behavioral rates are aggregated to the group level, then combined with claim-level statistics (publish rates, deadline adherence) and payment data. The three axis scores (R, T, I) are computed as weighted means of their components, then combined into the final ACI composite. Each score includes a confidence metric and a low-data flag.

## Scoring methodology

### Reliability (R)

Weighted mean of:

| Component | Weight | Source | Description |
|-----------|--------|--------|-------------|
| `sample_offer_rate` | 0.4 | Chat semantics | How often the group offers free test decryption |
| `key_delivery_rate` | 0.4 | Chat semantics | How often they reference sending a decryptor/key |
| `has_payment_data` | 0.2 | ransomwhere.re | Whether confirmed payments exist (proxy for functional payment pipeline) |

### Threat Follow-Through (T)

Weighted mean of:

| Component | Weight | Source | Description |
|-----------|--------|--------|-------------|
| `publish_rate` | 0.5 | Claims data | Share of claims that resulted in a data publication |
| `leak_threat_rate` | 0.5 | Chat semantics | How often leak threats appear in negotiation chats |
| `on_time_publish_rate` | 0.2 | Claims data | Bonus for publishing on or before stated deadline (if available) |

### Integrity (I)

`I = 1 - bad_score`, where `bad_score` is the weighted mean of:

| Component | Weight | Source | Description |
|-----------|--------|--------|-------------|
| `violation_claim_rate` | 0.4 | Chat semantics | Victim accusations of broken promises |
| `reextortion_behavior_rate` | 0.4 | Chat semantics | Signals of post-payment re-extortion |
| `data_resale_admission_rate` | 0.2 | Chat semantics | Admissions of selling or sharing stolen data |

### Confidence

A heuristic confidence score (0-1) based on data volume:

- **Chat confidence** -- saturates at 10+ negotiation chats per group
- **Claim confidence** -- saturates at 50+ claims per group
- **Component coverage** -- fraction of R, T, I that are non-NaN

Blended as: `confidence = 0.4 x chat_conf + 0.3 x claim_conf + 0.3 x coverage`

Groups with fewer than 2 negotiation chats are flagged with `low_data=1`.

All calculations are NaN-safe: missing components are skipped and weights are renormalized over available data.

## Web dashboard

ACI scores are published to an interactive web dashboard built with React ([superham/aci-web](https://github.com/superham/aci-web)). The dashboard lets users explore scores, filter by confidence, drill into individual groups, and view year-over-year trends.

### Monthly data flow

A GitHub Actions workflow (`.github/workflows/monthly-update.yml`) runs on the 1st of each month:

1. **Collect** -- fetches the latest claims, negotiation chats, and payment data from APIs
2. **Score** -- runs the full pipeline (`aci web-export`) to produce `dashboard.json`
3. **Push** -- commits the updated `dashboard.json` to the `aci-web` repo at `public/data/dashboard.json`

The web dashboard loads this static JSON file at runtime -- no backend API is required. The workflow can also be triggered manually via `workflow_dispatch` if an ad-hoc refresh is needed.

### Export command

```bash
# Generate dashboard-ready JSON for the web frontend
aci web-export --since 2020-01-01 --out reports/dashboard.json
```

The export applies inclusion criteria (groups need 2+ years of data with 1+ event per year) so only sufficiently-documented groups appear on the dashboard. The output includes overview stats, per-group R/T/I breakdowns, yearly trends, confidence data, and outcome metrics.

## Data flow

```
                       ransomware.live API
                      /                    \
                     v                      v
            claims.jsonl            negotiations.jsonl
                 |                          |
                 |                 sentence-transformers
                 |                  (all-MiniLM-L6-v2)
                 |                          |
                 |                          v
                 |                  chat_features.csv
                 |                          |
                 v                          v
             +--------------------------------------+
             |        Feature Aggregation           |<-- ransomwhere.jsonl <-- ransomwhere.re API
             |        (group-level rates)           |
             +------------------+-------------------+
                                |
                                v
                      +-------------------+
                      |   ACI Scoring     |
                      |   R, T, I -> ACI  |
                      +--------+----------+
                               |
                     +---------+---------+
                     |                   |
                     v                   v
          reports/aci_scores.csv   dashboard.json
                                         |
                              (monthly GitHub Action)
                                         |
                                         v
                              aci-web/public/data/
                                  dashboard.json
                                         |
                                         v
                               React web dashboard
```

## Project structure

```
aci_tool/
├── cli.py                      # CLI entry point (6 subcommands)
├── config.py                   # API keys, default paths
├── schemas.py                  # Pydantic models: Claim, Payment, Negotiation
├── compute.py                  # Feature aggregation (chat/claims/payments -> group-level)
├── scoring.py                  # ACI scoring algorithm (R, T, I, confidence)
├── chat_semantic.py            # Sentence-transformer feature extraction
├── web_export.py               # Dashboard JSON generation for aci-web
├── utils.py                    # Shared helpers
├── collectors/
│   ├── ransomware_live.py      # ransomware.live API client (claims)
│   ├── ransomwhere.py          # ransomwhere.re API client (payments)
│   └── negotiations.py         # Negotiation chat fetcher
└── prototypes/
    └── chat_semantic_proto.py  # Prototype sentences for semantic classification
```

## Development

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

Tests cover the scoring algorithm, feature aggregation, and semantic extraction modules.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
