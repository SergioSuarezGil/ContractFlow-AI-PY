from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_server.api import compare_contracts, get_comparison_job

mcp = FastMCP("contractflow")


@mcp.tool(name="compare_contracts")
async def compare_contracts_tool(contractId: str) -> str:
    """Request an async contract comparison for a contract id."""
    return await compare_contracts(contractId)


@mcp.tool(name="get_comparison_job")
async def get_comparison_job_tool(jobId: str) -> str:
    """Fetch comparison job status by jobId."""
    return await get_comparison_job(jobId)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
