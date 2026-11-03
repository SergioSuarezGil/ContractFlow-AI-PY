from __future__ import annotations

from contracts_api.domain.report import Report


class InMemoryReportRepository:
    def __init__(self) -> None:
        self._items: dict[str, Report] = {}

    async def find_by_id(self, report_id: str) -> Report | None:
        return self._items.get(report_id)

    async def save(self, report: Report) -> None:
        self._items[report.id] = report

    def clear(self) -> None:
        self._items.clear()
