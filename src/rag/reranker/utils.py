import json

from langchain.load import dumpd
from langchain_core.documents import Document


def document_to_str(doc: Document) -> str:
    """TODO(marcobebway)"""
    obj = dumpd(doc)

    # remove unnecessary fields
    if "type" in obj:
        del obj["type"]
    if "type" in obj["kwargs"]:
        del obj["kwargs"]["type"]
    if "metadata" in obj["kwargs"]:
        del obj["kwargs"]["metadata"]

    obj = {"kwargs": obj["kwargs"]}
    return json.dumps(obj).strip()


def dict_to_document(obj: dict) -> Document:
    """TODO(marcobebway)"""
    return Document(page_content=obj["kwargs"]["page_content"])


def str_to_document(s: str) -> Document:
    """TODO(marcobebway)"""
    obj = json.loads(s)
    return dict_to_document(obj)
