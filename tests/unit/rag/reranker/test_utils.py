import pytest

from rag.reranker.utils import (
    TMP_DOC_ID_PREFIX,
    get_tmp_document_id,
)


@pytest.mark.parametrize(
    "identifier, prefix, expected",
    [
        ("abc", TMP_DOC_ID_PREFIX, "tmp-id-abc"),
        ("123", "custom-", "custom-123"),
        ("", TMP_DOC_ID_PREFIX, "tmp-id-"),
        ("xyz", "", "xyz"),
        ("test", None, "tmp-id-test"),
    ],
)
def test_get_tmp_document_id(identifier, prefix, expected):
    if prefix is None:
        assert get_tmp_document_id(identifier) == expected
    else:
        assert get_tmp_document_id(identifier, prefix) == expected
