import json

from pydantic import BaseModel


class DocumentsSource(BaseModel):
    """Model for the documents source."""

    name: str
    source_type: str
    url: str
    include_files: list[str] | None
    exclude_files: list[str] | None
    filter_file_types: list[str] = ["md"]


def get_documents_sources(path: str) -> list[DocumentsSource]:
    """Reads the documents sources from the json file."""
    sources = []
    with open(path) as f:
        json_obj = json.load(f)
        for item in json_obj:
            sources.append(DocumentsSource(**item))
    return sources
