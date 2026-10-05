"""Fixed segmentation taxonomy (from the PoC notebooks) and crosstab column names."""

from enum import StrEnum


class Category(StrEnum):
    """Conversation topic categories derived from the PoC classification notebooks."""

    KNOWLEDGE_SEARCH = "knowledge_search"
    SETUP_CONFIGURATION = "setup_configuration"
    TROUBLESHOOTING = "troubleshooting"
    CLUSTER_AND_CLUSTER_ANALYSIS = "cluster_and_cluster_analysis"
    BEST_PRACTICES = "best_practices"
    SECURITY_COMPLIANCE = "security_compliance"
    PERFORMANCE_SCALING = "performance_scaling"
    RELEASE_UPGRADE_MIGRATION = "release_upgrade_migration"
    OTHER = "other"


class Judgement(StrEnum):
    """LLM quality verdict for a single conversation turn."""

    SUFFICIENT = "SUFFICIENT"
    PARTIAL = "PARTIAL"
    INSUFFICIENT = "INSUFFICIENT"


def cell_column(category: Category, judgement: Judgement) -> str:
    """HANA column name for one crosstab cell, e.g. C_TROUBLESHOOTING_INSUFFICIENT."""
    return f"C_{category.value.upper()}_{judgement.value.upper()}"


def crosstab_columns() -> list[str]:
    """All 27 crosstab column names in a stable order."""
    return [cell_column(c, j) for c in Category for j in Judgement]
