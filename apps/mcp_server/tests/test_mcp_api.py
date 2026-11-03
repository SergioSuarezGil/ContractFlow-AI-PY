import asyncio

import httpx
from mcp_server.api import compare_contracts, get_comparison_job
from mcp_server.main import mcp


def test_compare_and_get_job() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path.endswith("/comparisons"):
            return httpx.Response(202, json={"jobId": "job-1", "status": "PENDING"})
        if request.method == "GET" and request.url.path.endswith("/jobs/job-1"):
            return httpx.Response(200, json={"id": "job-1", "status": "COMPLETED"})
        return httpx.Response(404, text="missing")

    transport = httpx.MockTransport(handler)

    async def _run() -> tuple[str, str]:
        async with httpx.AsyncClient(transport=transport, base_url="http://api.test") as client:
            created = await compare_contracts("contract-1", client)
            fetched = await get_comparison_job("job-1", client)
            return created, fetched

    created, fetched = asyncio.run(_run())
    assert "job-1" in created
    assert "COMPLETED" in fetched


def test_mcp_registers_parity_tools() -> None:
    tools = mcp._tool_manager.list_tools()
    names = {tool.name for tool in tools}
    assert names == {"compare_contracts", "get_comparison_job"}
