"""Tests for the dynamic topic taxonomy (areas, intents)."""

from conversation_segmentation.taxonomy import (
    TAXONOMY_VERSION,
    Area,
    Intent,
)


def test_areas_and_intents_include_other_fallback():
    assert Area.OTHER in set(Area)
    assert Intent.OTHER in set(Intent)
    assert Area.ISTIO.value == "istio" and Intent.TROUBLESHOOTING.value == "troubleshooting"


def test_taxonomy_version_is_set():
    assert isinstance(TAXONOMY_VERSION, str) and TAXONOMY_VERSION
