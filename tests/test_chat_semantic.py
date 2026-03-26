"""Tests for aci_tool.chat_semantic — parsing and feature extraction helpers."""

import pytest
from aci_tool.chat_semantic import (
    split_sentences,
    parse_amount,
    is_attacker_message,
    extract_chat_features,
)

_model_available = False
try:
    from sentence_transformers import SentenceTransformer
    SentenceTransformer("all-MiniLM-L6-v2")
    _model_available = True
except Exception:
    pass

requires_model = pytest.mark.skipif(
    not _model_available,
    reason="sentence-transformers model not available (no network or not cached)",
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
