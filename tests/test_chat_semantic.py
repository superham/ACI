"""Tests for aci_tool.chat_semantic — parsing and feature extraction helpers."""

import os

import pytest

from aci_tool.chat_semantic import (
    extract_chat_features,
    is_attacker_message,
    parse_amount,
    split_sentences,
)

_model_available = False
try:
    from sentence_transformers import SentenceTransformer

    # Only check local cache — don't trigger a network download at import time
    cache_dir = os.path.join(
        os.getenv("HF_HOME", os.path.join(os.path.expanduser("~"), ".cache", "huggingface")),
        "hub",
    )
    # If the model dir exists in cache, it's safe to load
    model_dirs = [d for d in os.listdir(cache_dir) if "all-MiniLM-L6-v2" in d] if os.path.isdir(cache_dir) else []
    if model_dirs or os.getenv("ACI_TEST_WITH_MODEL"):
        SentenceTransformer("all-MiniLM-L6-v2")
        _model_available = True
except Exception:
    pass

requires_model = pytest.mark.skipif(
    not _model_available,
    reason="sentence-transformers model not cached (set ACI_TEST_WITH_MODEL=1 to download)",
)


class TestSplitSentences:
    def test_basic(self):
        result = split_sentences("Hello world. How are you? Fine!")
        assert len(result) == 3

    def test_empty(self):
        assert split_sentences("") == []
        assert split_sentences(None) == []

    def test_newlines_collapsed(self):
        result = split_sentences("line one.\nline two.")
        assert len(result) >= 1  # newline becomes space


class TestParseAmount:
    def test_usd(self):
        assert parse_amount("$900,000") == pytest.approx(900000)

    def test_plain(self):
        assert parse_amount("75000") == pytest.approx(75000)

    def test_na(self):
        assert parse_amount("N/A") is None
        assert parse_amount("") is None
        assert parse_amount(None) is None

    def test_with_spaces(self):
        assert parse_amount("$ 160,000") == pytest.approx(160000)


class TestIsAttackerMessage:
    def test_attacker(self):
        assert is_attacker_message({"party": "Operator"}) is True
        assert is_attacker_message({"party": "Support"}) is True

    def test_victim(self):
        assert is_attacker_message({"party": "Victim"}) is False

    def test_missing(self):
        assert is_attacker_message({}) is True  # default: not victim


class TestExtractChatFeatures:
    @requires_model
    def test_basic_chat(self):
        chat = {
            "group": "testgroup",
            "chat_id": "20240101",
            "started_at": "2024-01-01T00:00:00",
            "meta": {
                "message_count": 5,
                "initialransom": "$100,000",
                "negotiatedransom": "$50,000",
                "paid": True,
            },
            "messages": [
                {"party": "Operator", "content": "send us some encrypted files and we will decrypt them for free"},
                {"party": "Victim", "content": "ok here are the files"},
                {"party": "Operator", "content": "if you do not pay we will publish your data on our leak site"},
            ],
        }
        features = extract_chat_features(chat)
        assert features["group"] == "testgroup"
        assert features["chat_id"] == "20240101"
        assert features["year"] == 2024
        assert features["paid"] is True
        assert features["gave_discount"] == 1
        assert features["discount_ratio"] == pytest.approx(0.5)
        assert features["initial_ransom_usd"] == pytest.approx(100000)
        assert features["negotiated_ransom_usd"] == pytest.approx(50000)

    def test_no_discount(self):
        chat = {
            "group": "g",
            "chat_id": "1",
            "meta": {"initialransom": "$100,000", "negotiatedransom": "$100,000"},
            "messages": [],
        }
        features = extract_chat_features(chat)
        assert features["gave_discount"] == 0
        assert features["discount_ratio"] is None

    def test_year_from_chat_id(self):
        chat = {
            "group": "g",
            "chat_id": "20230515",
            "meta": {},
            "messages": [],
        }
        features = extract_chat_features(chat)
        assert features["year"] == 2023
