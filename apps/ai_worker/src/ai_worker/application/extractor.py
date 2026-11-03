from __future__ import annotations

import asyncio
import io
import os
from typing import Literal

from ai_worker.application.types import ExtractedDocument, ExtractedPage
from pypdf import PdfReader

DEFAULT_MAX_BYTES = 15 * 1024 * 1024
DEFAULT_MAX_PAGES = 50
DEFAULT_MAX_CHARS = 200_000
DEFAULT_TIMEOUT_MS = 30_000


class UnprocessableDocumentError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(f"UNPROCESSABLE: {message}")


class DocumentExtractor:
    def __init__(
        self,
        *,
        max_bytes: int | None = None,
        max_pages: int | None = None,
        max_chars: int | None = None,
        timeout_ms: int | None = None,
    ) -> None:
        self.max_bytes = max_bytes or int(os.getenv("MAX_DOCUMENT_BYTES", DEFAULT_MAX_BYTES))
        self.max_pages = max_pages or int(os.getenv("MAX_PDF_PAGES", DEFAULT_MAX_PAGES))
        self.max_chars = max_chars or int(os.getenv("MAX_EXTRACT_CHARS", DEFAULT_MAX_CHARS))
        self.timeout_ms = timeout_ms or int(
            os.getenv("EXTRACTION_TIMEOUT_MS", DEFAULT_TIMEOUT_MS)
        )

    async def extract(
        self,
        *,
        document_id: str,
        file_name: str,
        role: Literal["current", "proposal"],
        content_type: str,
        body: bytes,
    ) -> ExtractedDocument:
        if len(body) > self.max_bytes:
            raise UnprocessableDocumentError(f"document exceeds {self.max_bytes} bytes")

        ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
        is_pdf = ext == "pdf" or "pdf" in content_type.lower()
        is_txt = ext == "txt" or content_type.lower().startswith("text/plain")
        if not is_pdf and not is_txt:
            raise UnprocessableDocumentError(
                f"only PDF and plain text extraction supported (got {ext or content_type})"
            )

        work = (
            self._extract_pdf(body)
            if is_pdf
            else asyncio.to_thread(self._extract_txt, body)
        )
        pages = await self._with_timeout(work)
        if not pages:
            raise UnprocessableDocumentError(
                "scanned PDF or empty document (no extractable text)"
            )
        full_text = "\n\n".join(
            f"[doc:{document_id} p:{page.page_number}]\n{page.text}" for page in pages
        )
        if not full_text.strip():
            raise UnprocessableDocumentError(
                "scanned PDF or empty document (no extractable text)"
            )
        return ExtractedDocument(
            document_id=document_id,
            file_name=file_name,
            role=role,
            content_type=content_type,
            pages=pages,
            full_text=full_text,
        )

    async def _extract_pdf(self, body: bytes) -> list[ExtractedPage]:
        return await asyncio.to_thread(self._extract_pdf_sync, body)

    def _extract_pdf_sync(self, body: bytes) -> list[ExtractedPage]:
        reader = PdfReader(io.BytesIO(body))
        pages: list[ExtractedPage] = []
        total_chars = 0
        for index, page in enumerate(reader.pages[: self.max_pages], start=1):
            text = (page.extract_text() or "").strip()
            if not text:
                continue
            remaining = self.max_chars - total_chars
            if remaining <= 0:
                break
            clipped = text[:remaining]
            total_chars += len(clipped)
            pages.append(ExtractedPage(page_number=index, text=clipped))
        return pages

    def _extract_txt(self, body: bytes) -> list[ExtractedPage]:
        raw = body.decode("utf-8", errors="replace")[: self.max_chars].strip()
        if not raw:
            return []
        return [ExtractedPage(page_number=1, text=raw)]

    async def _with_timeout(
        self, work: asyncio.Future | asyncio.Task | object
    ) -> list[ExtractedPage]:
        return await asyncio.wait_for(
            work, timeout=self.timeout_ms / 1000
        )  # type: ignore[arg-type]
