TMP_DOC_ID_PREFIX = "tmp-id-"


def get_tmp_document_id(identifier: str, prefix: str = TMP_DOC_ID_PREFIX) -> str:
    """Generate a temporary document ID with a given prefix."""
    return f"{prefix}{identifier}"
