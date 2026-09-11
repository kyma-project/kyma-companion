"""Unit tests for curation.decisions_cache."""

import dataclasses
import json
import os

import pytest
from curation.decisions_cache import DecisionsCache, _cache_key
from curation.models import CandidateDoc, ClassificationResult

pytestmark = pytest.mark.unit

_ROUND_TRIP_COUNT = 5
_SINGLE_ENTRY = 1
_TWO_ENTRIES = 2


def _make_candidate(
    repo: str = "testrepo",
    path: str = "docs/file.md",
    content_hash: str = "abc123",
) -> CandidateDoc:
    return CandidateDoc(
        repo=repo,
        path=path,
        h1="Test",
        excerpt="Some excerpt.",
        directory="/data/testrepo/docs",
        residue_reason="not_in_include_patterns",
        content_hash=content_hash,
    )


def _make_result(candidate: CandidateDoc, decision: str = "include") -> ClassificationResult:
    return ClassificationResult(
        candidate=candidate,
        decision=decision,  # type: ignore[arg-type]
        doc_type="tutorial",
        module="eventing",
        confidence=0.9,
        rationale="user-facing docs",
        decided_by="agent",
    )


def _read_lines(path: str) -> list[str]:
    with open(path) as fh:
        return [line.strip() for line in fh if line.strip()]


@pytest.fixture
def tmp_decisions_file(tmp_path):
    return str(tmp_path / "curation" / "decisions.jsonl")


class TestCacheKey:
    def test_key_format(self):
        key = _cache_key("myrepo", "docs/file.md", "deadbeef")
        assert key == "myrepo::docs/file.md::deadbeef"

    def test_key_uniqueness(self):
        k1 = _cache_key("repo", "path.md", "hash1")
        k2 = _cache_key("repo", "path.md", "hash2")
        assert k1 != k2

    def test_key_changes_with_path(self):
        k1 = _cache_key("repo", "a.md", "hash")
        k2 = _cache_key("repo", "b.md", "hash")
        assert k1 != k2


class TestLoad:
    def test_missing_file_returns_empty(self, tmp_path):
        cache = DecisionsCache(str(tmp_path / "nonexistent.jsonl"))
        result = cache.load()
        assert result == {}

    def test_load_single_entry(self, tmp_decisions_file):
        candidate = _make_candidate()
        result = _make_result(candidate)

        os.makedirs(os.path.dirname(tmp_decisions_file), exist_ok=True)
        with open(tmp_decisions_file, "w") as fh:
            fh.write(json.dumps(dataclasses.asdict(result)) + "\n")

        cache = DecisionsCache(tmp_decisions_file)
        loaded = cache.load()
        assert len(loaded) == _SINGLE_ENTRY
        key = _cache_key(candidate.repo, candidate.path, candidate.content_hash)
        assert key in loaded
        assert loaded[key].decision == "include"

    def test_load_skips_malformed_lines(self, tmp_decisions_file):
        os.makedirs(os.path.dirname(tmp_decisions_file), exist_ok=True)
        with open(tmp_decisions_file, "w") as fh:
            fh.write("{not valid json\n")
            candidate = _make_candidate()
            result = _make_result(candidate)
            fh.write(json.dumps(dataclasses.asdict(result)) + "\n")

        cache = DecisionsCache(tmp_decisions_file)
        loaded = cache.load()
        # One malformed, one valid
        assert len(loaded) == _SINGLE_ENTRY


class TestSave:
    def test_save_creates_file_and_directory(self, tmp_decisions_file):
        candidate = _make_candidate()
        result = _make_result(candidate)
        cache = DecisionsCache(tmp_decisions_file)
        cache.load()
        cache.save([result])

        assert os.path.exists(tmp_decisions_file)
        assert len(_read_lines(tmp_decisions_file)) == _SINGLE_ENTRY

    def test_save_does_not_duplicate_existing(self, tmp_decisions_file):
        candidate = _make_candidate()
        result = _make_result(candidate)

        cache = DecisionsCache(tmp_decisions_file)
        cache.load()
        cache.save([result])
        # Save again -- should NOT append a duplicate
        cache.save([result])

        assert len(_read_lines(tmp_decisions_file)) == _SINGLE_ENTRY

    def test_save_appends_new_entries(self, tmp_decisions_file):
        c1 = _make_candidate(path="docs/a.md", content_hash="hash1")
        c2 = _make_candidate(path="docs/b.md", content_hash="hash2")
        r1 = _make_result(c1, "include")
        r2 = _make_result(c2, "exclude")

        cache = DecisionsCache(tmp_decisions_file)
        cache.load()
        cache.save([r1])
        cache.save([r2])

        assert len(_read_lines(tmp_decisions_file)) == _TWO_ENTRIES


class TestIsCachedAndGet:
    def test_is_cached_false_before_save(self, tmp_decisions_file):
        candidate = _make_candidate()
        cache = DecisionsCache(tmp_decisions_file)
        cache.load()
        assert not cache.is_cached(candidate)

    def test_is_cached_true_after_save(self, tmp_decisions_file):
        candidate = _make_candidate()
        result = _make_result(candidate)
        cache = DecisionsCache(tmp_decisions_file)
        cache.load()
        cache.save([result])
        assert cache.is_cached(candidate)

    def test_get_returns_none_when_missing(self, tmp_decisions_file):
        candidate = _make_candidate()
        cache = DecisionsCache(tmp_decisions_file)
        cache.load()
        assert cache.get(candidate) is None

    def test_get_returns_result_after_save(self, tmp_decisions_file):
        candidate = _make_candidate()
        result = _make_result(candidate)
        cache = DecisionsCache(tmp_decisions_file)
        cache.load()
        cache.save([result])
        retrieved = cache.get(candidate)
        assert retrieved is not None
        assert retrieved.decision == "include"

    def test_different_hash_is_not_cached(self, tmp_decisions_file):
        c1 = _make_candidate(content_hash="oldhash")
        c2 = _make_candidate(content_hash="newhash")
        result = _make_result(c1)
        cache = DecisionsCache(tmp_decisions_file)
        cache.load()
        cache.save([result])
        # c1 is cached but c2 (different hash) is not
        assert cache.is_cached(c1)
        assert not cache.is_cached(c2)


class TestRoundTrip:
    def test_load_save_load_round_trip(self, tmp_decisions_file):
        candidates = [
            _make_candidate(path=f"docs/file{i}.md", content_hash=f"hash{i}") for i in range(_ROUND_TRIP_COUNT)
        ]
        results = [_make_result(c, decision="include" if i % 2 == 0 else "exclude") for i, c in enumerate(candidates)]

        cache1 = DecisionsCache(tmp_decisions_file)
        cache1.load()
        cache1.save(results)

        # Re-load from disk
        cache2 = DecisionsCache(tmp_decisions_file)
        loaded = cache2.load()

        assert len(loaded) == _ROUND_TRIP_COUNT
        for candidate in candidates:
            assert cache2.is_cached(candidate)
