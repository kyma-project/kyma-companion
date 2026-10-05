import pytest

from conversation_segmentation.watermark import head_fingerprint, select_new_turns, session_key

pytestmark = pytest.mark.unit


def test_session_key_is_stable_64_hex_and_not_the_raw_id():
    k = session_key("abc-123")
    assert len(k) == 64 and all(ch in "0123456789abcdef" for ch in k)  # noqa: PLR2004
    assert k == session_key("abc-123") and "abc-123" not in k


def test_select_new_turns_returns_only_turns_beyond_watermark():
    turns = [{"turn_index": i} for i in range(5)]
    assert select_new_turns(turns, already=3) == [{"turn_index": 3}, {"turn_index": 4}]
    assert select_new_turns(turns, already=5) == []
    assert select_new_turns(turns, already=0) == turns


def test_head_fingerprint_stable_64_hex_for_same_first_turn():
    turns = [{"turn_index": 0, "query": "hello world", "response": "hi"}]
    fp = head_fingerprint(turns)
    assert len(fp) == 64  # noqa: PLR2004
    assert all(ch in "0123456789abcdef" for ch in fp)
    assert fp == head_fingerprint(turns)


def test_head_fingerprint_differs_for_different_first_query():
    turns_a = [{"turn_index": 0, "query": "hello", "response": "hi"}]
    turns_b = [{"turn_index": 0, "query": "goodbye", "response": "bye"}]
    assert head_fingerprint(turns_a) != head_fingerprint(turns_b)


def test_head_fingerprint_empty_string_for_no_turns():
    assert head_fingerprint([]) == ""
