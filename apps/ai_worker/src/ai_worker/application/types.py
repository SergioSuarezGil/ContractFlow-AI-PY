from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class ExtractedPage:
    page_number: int
    text: str


@dataclass
class ExtractedDocument:
    document_id: str
    file_name: str
    role: Literal["current", "proposal"]
    content_type: str
    pages: list[ExtractedPage]
    full_text: str


@dataclass
class RedactedExtractedBundle:
    job_id: str
    contract_id: str
    title: str
    provider_name: str
    service_type: str
    documents: list[ExtractedDocument] = field(default_factory=list)


@dataclass
class SourceDocument:
    document_id: str
    file_name: str
    role: Literal["current", "proposal"]
    content_type: str
    body: bytes
