import asyncio

from ai_worker.infrastructure.comparison_store import InMemoryComparisonStore, lookup_view
from ai_worker.infrastructure.grpc_server import ComparisonLookupServicer, WorkerHealthServicer
from ai_worker.infrastructure.mongo_document_source import MongoDocumentSource
from contractflow_grpc import worker_health_pb2


class _Docs:
    def __init__(self, doc: dict) -> None:
        self._doc = doc

    async def find_one(self, filt: dict) -> dict | None:
        if filt.get("id") == self._doc["id"]:
            return self._doc
        return None


class _DB(dict):
    def __getitem__(self, name: str) -> _Docs:
        return super().__getitem__(name)


class _Storage:
    async def get_object(self, bucket: str, key: str) -> bytes | None:
        if bucket == "documents" and key == "hh/c/d":
            return b"Price: 40 monthly"
        return None


def test_mongo_document_source_loads_body() -> None:
    db = _DB(documents=_Docs(
        {
            "id": "d1",
            "role": "proposal",
            "fileName": "proposal.txt",
            "contentType": "text/plain",
            "storageKey": "hh/c/d",
        }
    ))
    source = MongoDocumentSource(db, _Storage(), bucket="documents")
    loaded = asyncio.run(source.load_many(["d1", "missing"]))
    assert len(loaded) == 1
    assert loaded[0].body == b"Price: 40 monthly"
    assert loaded[0].role == "proposal"


def test_grpc_servicers_read_memory_store() -> None:
    store = InMemoryComparisonStore()

    async def _run() -> None:
        health = await WorkerHealthServicer().Check(
            worker_health_pb2.HealthCheckRequest(service="ai-worker"),
            None,
        )
        assert health.status == "SERVING"
        saved = await store.insert(
            {
                "id": "cmp",
                "jobId": "job-1",
                "contractId": "c1",
                "verdict": "better",
                "summary": "cheaper",
                "createdAt": "2026-11-03T00:00:00Z",
            }
        )
        assert saved
        request = type("Req", (), {"job_id": "job-1"})()
        response = await ComparisonLookupServicer(store).GetByJobId(request, None)
        assert response.found is True
        assert response.verdict == "better"
        missing = lookup_view("nope", None)
        assert missing["found"] is False

    asyncio.run(_run())
