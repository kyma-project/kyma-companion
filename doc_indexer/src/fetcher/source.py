import json
from enum import StrEnum

from pydantic import BaseModel, field_validator


class SourceType(StrEnum):
    """Enum for the documents source type."""

    GITHUB = "Github"


class DocumentsSource(BaseModel):
    """Model for the documents source."""

    name: str
    source_type: SourceType
    url: str
    include_files: list[str] | None = None
    exclude_files: list[str] | None = None
    filter_file_types: list[str] = ["md"]

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if ".." in v or "/" in v or "\\" in v:
            raise ValueError(f"Invalid source name {v!r}: must not contain path separators or '..'")
        return v


def get_documents_sources(path: str) -> list[DocumentsSource]:
    """Reads the documents sources from the json file."""
    sources = []
    with open(path) as f:
        json_obj = json.load(f)
        for item in json_obj:
            sources.append(DocumentsSource(**item))
    return sources
