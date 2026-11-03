from ai_worker.application.types import SourceDocument


class InMemoryDocumentSource:
    def __init__(self) -> None:
        self._items: dict[str, SourceDocument] = {}

    def put(self, document: SourceDocument) -> None:
        self._items[document.document_id] = document

    async def load_many(self, document_ids: list[str]) -> list[SourceDocument]:
        return [self._items[doc_id] for doc_id in document_ids if doc_id in self._items]

    def clear(self) -> None:
        self._items.clear()
