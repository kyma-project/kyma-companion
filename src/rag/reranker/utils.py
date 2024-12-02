import json

from langchain.load import dumpd
from langchain_core.documents import Document


def document_to_str(doc: Document) -> str:
    """
    Convert a document to a string.
    It is used to convert a document to a string for serialization.
    It returns a JSON string of the document object with the page_content field only set.
    :param doc: A document object.
    :return: A JSON string representation of the document.
    """
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
    """
    Convert a dictionary to a document.
    It is used to convert a dictionary to a document after deserialization.
    It returns a document object with the page_content field only set.
    :param obj: A dictionary object.
    :return: A document object.
    """
    return Document(page_content=obj["kwargs"]["page_content"])


def str_to_document(s: str) -> Document:
    """
    Convert a string to a document.
    It is used to convert a string to a document after deserialization.
    It returns a document object with the page_content field only set.
    :param s: A string representation of a document.
    :return: A document object.
    """
    obj = json.loads(s)
    return dict_to_document(obj)
