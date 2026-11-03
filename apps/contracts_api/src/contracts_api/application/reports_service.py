from __future__ import annotations

from contracts_api.application.actor import ActorContext
from contracts_api.application.object_body import read_object
from contracts_api.application.ports import JobRepository, ObjectStoragePort, ReportRepository
from contracts_api.domain.errors import ForbiddenError, NotFoundError
from contracts_api.domain.report import Report


class ReportsService:
    def __init__(
        self,
        jobs: JobRepository,
        reports: ReportRepository,
        storage: ObjectStoragePort,
        *,
        reports_bucket: str = "reports",
    ) -> None:
        self._jobs = jobs
        self._reports = reports
        self._storage = storage
        self._bucket = reports_bucket

    async def store_from_worker(
        self,
        *,
        report_id: str,
        job_id: str,
        contract_id: str,
        owner_id: str,
        household_id: str,
        comparison_id: str,
        file_name: str,
        content_type: str,
        body: bytes,
        storage_key: str | None = None,
    ) -> Report:
        if not body:
            raise NotFoundError("Empty report body")
        key = storage_key or f"reports/{job_id}/{report_id}.pdf"
        await self._storage.put_object(
            bucket=self._bucket,
            key=key,
            body=body,
            content_type=content_type or "application/pdf",
        )
        report = Report.create(
            id=report_id,
            job_id=job_id,
            contract_id=contract_id,
            owner_id=owner_id,
            household_id=household_id,
            comparison_id=comparison_id,
            storage_key=key,
            file_name=file_name or f"{report_id}.pdf",
            content_type=content_type or "application/pdf",
            size_bytes=len(body),
        )
        await self._reports.save(report)
        return report

    async def get_for_actor(self, actor: ActorContext, report_id: str) -> Report:
        report = await self._reports.find_by_id(report_id)
        if report is None:
            raise NotFoundError(f"Report not found: {report_id}")
        if report.owner_id != actor.owner_id or report.household_id != actor.household_id:
            raise ForbiddenError("Access denied to this report")
        return report

    async def download_for_actor(self, actor: ActorContext, report_id: str) -> tuple[Report, bytes]:
        report = await self.get_for_actor(actor, report_id)
        body = await read_object(self._storage, self._bucket, report.storage_key)
        if body is None:
            raise NotFoundError(f"Report body missing: {report.id}")
        return report, body

    async def get_pdf_for_job(self, actor: ActorContext, job_id: str) -> tuple[Report, bytes]:
        job = await self._jobs.find_by_id(job_id)
        if job is None or not job.belongs_to(actor.owner_id, actor.household_id):
            raise NotFoundError(f"Job not found: {job_id}")
        if not job.report_id:
            raise NotFoundError(f"Report not ready for job: {job_id}")
        report = await self._reports.find_by_id(job.report_id)
        if report is None:
            raise NotFoundError(f"Report not found: {job.report_id}")
        if report.owner_id != actor.owner_id or report.household_id != actor.household_id:
            raise ForbiddenError("Access denied to this report")
        body = await read_object(self._storage, self._bucket, report.storage_key)
        if body is None:
            raise NotFoundError(f"Report body missing: {report.id}")
        return report, body
