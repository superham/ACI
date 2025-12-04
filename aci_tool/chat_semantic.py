"""
Semantic feature extraction from ransomware negotiation chats.
"""

from __future__ import annotations
import json
import re
from typing import Any, Dict, List, Optional, Generator, Mapping
from sentence_transformers import SentenceTransformer, util
from aci_tool.prototypes.chat_semantic_proto import PROTOTYPES

# Lazily-loaded model + prototype embeddings
_MODEL: Optional[SentenceTransformer] = None
_PROTO_EMBS: Optional[Dict[str, Any]] = None

def _get_model_and_prototypes():
    """Load the embedding model and prototype embeddings once."""
    global _MODEL, _PROTO_EMBS
    if _MODEL is None:
        _MODEL = SentenceTransformer("all-MiniLM-L6-v2")
        _PROTO_EMBS = {
            label: _MODEL.encode(examples, normalize_embeddings=True)
            for label, examples in PROTOTYPES.items()
        }
    return _MODEL, _PROTO_EMBS

# helpers
_SENT_SPLIT_RE = re.compile(r"[.!?]\s+")
_AMOUNT_RE = re.compile(r"(\d[\d,\.]*)")

def split_sentences(text: str) -> List[str]:
    """Very rough sentence splitter; good enough for the negotiation chats"""
    if not text:
        return []
    text = text.replace("\n", " ")
    parts = _SENT_SPLIT_RE.split(text)
    out = []
    for p in parts:
        s = p.strip(" >\t\r\n")
        if s:
            out.append(s)
    return out

def parse_amount(raw: Optional[str]) -> Optional[float]:
    """
    Parse numerical amounts like '$ 900,000', '$160,000', '75000', 'N/A' -> float or None.
    """
    if not raw:
        return None
    s = raw.strip()
    if s.lower() in {"n/a", "na", "none", "null"}:
        return None
    # strip common currency markers
    s = s.replace("$", "").replace("usd", "").lower()
    m = _AMOUNT_RE.search(s)
    if not m:
        return None
    num = m.group(1).replace(",", "")
    try:
        return float(num)
    except ValueError:
        return None

def is_attacker_message(msg: Mapping[str, Any]) -> bool:
    """
    Ransomware attacker messages are any where party != 'Victim'
    given your schema.
    """
    party = (msg.get("party") or "").strip().lower()
    return party != "victim"

# Semantic classification for a single sentence
def classify_sentence_semantic(
    sentence: str,
    threshold: float = 0.6,
) -> Dict[str, bool]:
    """
    For a single sentence, return {concept_label: bool} based on
    cosine similarity to prototypes.
    https://en.wikipedia.org/wiki/Cosine_similarity
    tldr: if any prototype for a label is similar enough, we flag it.
    """
    sentence = sentence.strip()
    if not sentence:
        return {label: False for label in PROTOTYPES.keys()}

    model, proto_embs = _get_model_and_prototypes()
    emb = model.encode(sentence, normalize_embeddings=True)

    hits: Dict[str, bool] = {}
    for label, label_embs in proto_embs.items():
        # similarity vs all prototypes for this label
        sim = util.cos_sim(emb, label_embs).max().item()
        hits[label] = bool(sim >= threshold)
    return hits

# Aggregate per message & per chat
def extract_flags_from_message(
    msg: Mapping[str, Any],
    threshold: float = 0.6,
) -> Dict[str, bool]:
    """
    Apply semantic classifier across all sentences in a message / results.
    """
    content = (msg.get("content") or "").lower()
    sentences = split_sentences(content)

    agg: Dict[str, bool] = {label: False for label in PROTOTYPES.keys()}
    for sent in sentences:
        res = classify_sentence_semantic(sent, threshold=threshold)
        for label, hit in res.items():
            if hit:
                agg[label] = True
    return agg

def extract_chat_features(chat: Mapping[str, Any]) -> Dict[str, Any]:
    """
    Compute semantic + numeric features for a single chat JSON object.
    Returns a flat dict that pandas.DataFrame can use
    This is what is used to gen .csv
    """
    features: Dict[str, Any] = {}

    # Base identifiers
    features["group"] = chat.get("group")
    features["chat_id"] = chat.get("chat_id")
    meta = chat.get("meta") or {}
    features["message_count"] = meta.get("message_count")

    # Extract year from chat timestamp or chat_id
    year = None
    started_at = chat.get("started_at")
    if started_at and started_at.strip():
        try:
            from dateutil import parser as dt_parser
            dt = dt_parser.parse(started_at)
            year = dt.year
        except:
            pass
    
    # If no started_at, try to extract year from chat_id (format: YYYYMMDD)
    if year is None:
        chat_id = chat.get("chat_id", "")
        if chat_id and len(chat_id) >= 4:
            try:
                year_candidate = int(chat_id[:4])
                # Validate year is reasonable (2000-2030)
                if 2000 <= year_candidate <= 2030:
                    year = year_candidate
            except (ValueError, TypeError):
                pass
    
    features["year"] = year

    # Meta ransom behavior
    init_amt = parse_amount(meta.get("initialransom"))
    nego_amt = parse_amount(meta.get("negotiatedransom"))
    features["initial_ransom_usd"] = init_amt
    features["negotiated_ransom_usd"] = nego_amt
    features["paid"] = bool(meta.get("paid", False)) # may lead to false negatives with default false

    if init_amt is not None and nego_amt is not None and nego_amt < init_amt:
        features["gave_discount"] = 1
        features["discount_ratio"] = (init_amt - nego_amt) / init_amt
    else:
        features["gave_discount"] = 0
        features["discount_ratio"] = None

    # Initialize semantic concept counters
    for label in PROTOTYPES.keys():
        features[f"any_{label}"] = 0
        features[f"count_{label}"] = 0

    # Walk attacker messages only
    for msg in chat.get("messages", []):
        if not is_attacker_message(msg):
            continue
        flags = extract_flags_from_message(msg)
        for label, hit in flags.items():
            if hit:
                features[f"any_{label}"] = 1
                features[f"count_{label}"] += 1

    return features

# more helpers for whole file analysis
def iter_jsonl(path: str) -> Generator[Dict[str, Any], None, None]:
    """Yield parsed JSON objects from a JSONL file."""
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)

def extract_chat_features_from_jsonl(
    path: str,
) -> Generator[Dict[str, Any], None, None]:
    """
    Iterate through negotiations.jsonl and yield one feature dict per chat.
    """
    for chat in iter_jsonl(path):
        yield extract_chat_features(chat)
