"""
Semantic feature extraction from ransomware negotiation chats.
v1 used small dataset of 5 groups to prototype this feature
TODO make large call then modify this to fit additional data
"""

from __future__ import annotations
import json
import math
import re
from typing import Any, Dict, Iterable, List, Optional, Generator, Mapping
from sentence_transformers import SentenceTransformer, util

# TODO: This will grow so move to its own file
PROTOTYPES: Dict[str, List[str]] = {
    # KEY DELIVERY & DECRYPTION RELIABILITY
    # Attacker offers to decrypt a few files as proof
    "proof_offer": [
        "send us some encrypted files and we will decrypt them",
        "we can decrypt test files for you",
        "we will decrypt a few files as proof",
        "we will show you we can decrypt your data",
        "upload several encrypted files for verification",
        "we will return decrypted samples so you can verify",
        "we will decrypt sample files to prove we have the key",
    ],

    # Victim confirms the sample decryption worked
    "proof_success": [
        "the decrypted files work",
        "the sample you returned is correct",
        "we can open the decrypted files",
        "the decryption was successful",
        "the files you sent back were properly decrypted",
        "the decrypted samples opened successfully",
    ],

    # Attacker sends or references a decryptor/key (key delivery)
    "key_delivery": [
        "here is your decryptor",
        "here is the decryption tool",
        "we provide the decryptor",
        "we will send you the key",
        "here is the key",
        "download your decryptor here",
        "you can download the decryption key",
        "the decryptor is available at this link",
    ],

    # THREAT FOLLOW-THROUGH (Leaking/Shaming/Auctioning data)
    "leak_threat": [
        "we will publish your data",
        "your data will be published",
        "we will leak your files",
        "your files will be leaked",
        "we will release your data",
        "your data will be uploaded",
        "we will make your data public",
        "we will put your data on our site",
        "your company will appear on our news column",
        "your data will be sold",
        "we will sell your data",
        "we will auction your data",
    ],

    # Explicit “follow-through” language — attacker says they already leaked
    # or are currently leaking (evidence they tend to act on threats)
    "leak_followthrough": [
        "your data has been published",
        "your data is already published",
        "your data has been leaked",
        "we have released your data",
        "we already leaked your files",
        "your files are already on our site",
        "your data is now public",
        "your leaks are posted",
    ],

    # POST-PAYMENT INTEGRITY & RE-EXTORTION
    # Attacker promises deletion / non-disclosure after payment
    "deletion_promise": [
        "we will delete your data after payment",
        "we will erase your data",
        "we will remove your files from our servers",
        "we guarantee data deletion after you pay",
        "after payment your data will be deleted",
        "we will not publish your data once payment is received",
    ],

    # Attacker explicitly promises no future extortion
    "no_future_extortion_promise": [
        "we will not attack you again",
        "you will not be targeted again",
        "we will not ask for more money",
        "there will be no second demand",
        "after payment this matter is closed",
        "we will not return to you again",
    ],

    # Victim accuses attacker of breaking a promise (strong signal)
    "violation_claim": [
        "you promised to delete our data",
        "you said the data would be deleted",
        "you said you would not publish our files",
        "you said you would not attack us again",
        "you asked for more money after we paid",
        "you leaked our data even after payment",
    ],

    # Attacker openly engages in re-extortion behavior
    "reextortion_behavior": [
        "you must pay again",
        "the price has increased even after payment",
        "you need to make another payment",
        "we require additional money",
        "you still have to pay more",
    ],

    # Attacker states that they sell or reuse data
    # → strong negative for integrity score
    "data_resale_admission": [
        "we sell data",
        "your data will be sold to third parties",
        "we resell company data",
        "we sell leaked data",
        "we redistribute exfiltrated data",
    ],
}


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
