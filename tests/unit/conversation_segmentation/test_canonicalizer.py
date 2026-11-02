"""Tests for topic canonicalization: stable grouping keys and summary sanitization."""

import pytest

from conversation_segmentation.canonicalizer import (
    MAX_CAPABILITY_LEN,
    build_topic_key,
    canonical_capability,
    canonicalize,
    sanitize_label,
    sanitize_summary,
    slugify,
)
from conversation_segmentation.taxonomy import Area, Intent


def test_slugify_normalizes_to_hyphenated_lowercase():
    assert slugify("  mTLS Traffic  Routing! ") == "mtls-traffic-routing"
    assert slugify("") == ""


def test_canonical_capability_slugifies_without_folding():
    # No synonym map: wording is only normalized to a slug, kept distinct as the data has it.
    assert canonical_capability("Mutual TLS") == "mutual-tls"
    assert canonical_capability("TLS") == "tls"
    assert canonical_capability("routing") == "routing"


def test_canonical_capability_defaults_to_general_when_empty():
    assert canonical_capability("   ") == "general"


def test_oversized_capability_is_shortened_with_a_stable_hash_suffix():
    first = canonical_capability("capability " * 30)
    second = canonical_capability("capability " * 29 + "routing")
    assert len(first) == MAX_CAPABILITY_LEN
    assert first == canonical_capability("capability " * 30)
    assert first != second


def test_topic_key_rejects_values_over_the_persistence_limit():
    with pytest.raises(ValueError, match="persistence limit"):
        build_topic_key(Area.ISTIO, Intent.TROUBLESHOOTING, "a" * 256)


def test_same_capability_wording_shares_one_topic_key():
    a = canonicalize(
        area=Area.ISTIO,
        intent=Intent.TROUBLESHOOTING,
        capability="mTLS",
        topic="mTLS broken",
        summary="mTLS stopped working",
        confidence=0.9,
    )
    b = canonicalize(
        area=Area.ISTIO,
        intent=Intent.TROUBLESHOOTING,
        capability="mtls",
        topic="STRICT mode killed traffic",
        summary="strict mtls broke traffic",
        confidence=0.8,
    )
    assert a.topic_key == b.topic_key == "istio/troubleshooting/mtls"


def test_istio_and_serverless_troubleshooting_are_distinct():
    istio = build_topic_key(Area.ISTIO, Intent.TROUBLESHOOTING, "mtls")
    serverless = build_topic_key(Area.SERVERLESS, Intent.TROUBLESHOOTING, "build")
    assert istio != serverless


def test_sanitize_summary_strips_identifiers_and_truncates():
    raw = "user in namespace: prod-123 hit https://foo.bar/x from 10.0.0.1 token abcdefABCDEF0123456789abcdefABCDEF01"
    cleaned = sanitize_summary(raw)
    assert "10.0.0.1" not in cleaned
    assert "https://foo.bar" not in cleaned
    assert "prod-123" not in cleaned
    assert "<ip>" in cleaned and "<url>" in cleaned

    long = sanitize_summary("x " * 300)
    assert len(long) <= 201  # noqa: PLR2004  # truncated with ellipsis


def test_sanitize_label_strips_identifiers():
    cleaned = sanitize_label("mTLS failing for svc at 10.0.0.1 in namespace: prod-1")
    assert "10.0.0.1" not in cleaned and "prod-1" not in cleaned
    assert "<ip>" in cleaned and "<namespace>" in cleaned


def test_canonical_capability_scrubs_identifiers_before_slugifying():
    # A capability that leaks an IP/URL must not survive into the slug or topic_key.
    slug = canonical_capability("mtls https://secret.internal/x")
    assert "secret.internal" not in slug and "https" not in slug


def test_canonicalize_scrubs_identifiers_from_every_stored_field():
    topic = canonicalize(
        area=Area.ISTIO,
        intent=Intent.TROUBLESHOOTING,
        capability="mtls for 10.0.0.1",
        topic="mTLS broke in namespace: prod-99",
        summary="user at admin@corp.com could not reach https://svc.local",
        confidence=0.9,
    )
    blob = f"{topic.topic_key} {topic.capability} {topic.label} {topic.summary}"
    for leaked in ("10.0.0.1", "prod-99", "admin@corp.com", "svc.local"):
        assert leaked not in blob
