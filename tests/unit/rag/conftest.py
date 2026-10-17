import pytest

import rag.retriever as retriever_module
from unit.rag.fakes import FakeVectorDB


@pytest.fixture
def fake_db(monkeypatch):
    """Replace HanaVectorDB with FakeVectorDB; ``fake_db.missing`` lists dropped tables."""
    FakeVectorDB.missing = set()
    FakeVectorDB.created = []
    monkeypatch.setattr(retriever_module, "HanaVectorDB", FakeVectorDB)
    return FakeVectorDB
