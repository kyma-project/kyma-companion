"""Controlled vocabulary for dynamic conversation topic analysis.

The analysis model proposes a specific area/capability/intent/topic per turn (see
``segmenter``); canonicalization (see ``canonicalizer``) reduces those to a stable,
groupable ``topic_key`` so two differently-worded conversations about the same issue
count as two conversations on one topic.

``area`` and ``intent`` are constrained to these enums via structured output, so the
model cannot invent off-taxonomy values. ``capability`` is a short free-text field
that canonicalization only normalizes to a slug — it is never folded or gatekept, so
the topic table evolves organically from whatever the data actually contains.
"""

from __future__ import annotations

from enum import StrEnum

# Bump when the enums or key format change in a way that makes new topic_keys
# incomparable with previously stored ones.
TAXONOMY_VERSION = "v1"


class Area(StrEnum):
    """Kyma / Kubernetes product domain a conversation turn is about."""

    ISTIO = "istio"
    SERVERLESS = "serverless"
    API_GATEWAY = "api_gateway"
    EVENTING = "eventing"
    TELEMETRY = "telemetry"
    KYMA_RUNTIME = "kyma_runtime"
    KUBERNETES = "kubernetes"
    OTHER = "other"


class Intent(StrEnum):
    """What the user was trying to do."""

    TROUBLESHOOTING = "troubleshooting"
    CONFIGURATION = "configuration"
    SETUP = "setup"
    UPGRADE = "upgrade"
    KNOWLEDGE_SEARCH = "knowledge_search"
    OTHER = "other"


# Placeholder capability slug when the model gives no usable capability.
GENERAL_CAPABILITY = "general"
