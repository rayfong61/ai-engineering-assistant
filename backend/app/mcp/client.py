import anyio
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from app.core.config import MCP_SERVER_URL


async def _call_tool_async(tool_name: str, arguments: dict):
    async with streamable_http_client(MCP_SERVER_URL) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await session.call_tool(tool_name, arguments)


def call_tool(tool_name: str, arguments: dict) -> dict | list:
    """Sync wrapper -- agent_service.py runs inside a sync FastAPI route.

    Escape hatch (spec2.md section 37's risk note: don't over-polish MCP
    protocol details): if the MCP SDK/network hop ever becomes seriously
    blocking, this function's body can be swapped for a direct in-process
    call to app.mcp.tools.<tool_name>.run(**arguments) without changing any
    call site -- agent_service.py only depends on this signature.
    """
    result = anyio.run(_call_tool_async, tool_name, arguments)
    if result.is_error:
        text = "; ".join(block.text for block in result.content if hasattr(block, "text"))
        raise RuntimeError(f"MCP tool '{tool_name}' failed: {text}")

    if result.structured_content is not None:
        data = result.structured_content
    else:
        # Fallback: no structured_content (e.g. an older client/server
        # mismatch) -- parse the first text content block as JSON.
        import json

        text = next(block.text for block in result.content if hasattr(block, "text"))
        data = json.loads(text)

    # A tool whose Python return type annotation is a list (e.g.
    # search_documents -> list[dict]) gets auto-wrapped by the MCP SDK as
    # {"result": [...]} because structured content must be a JSON object --
    # unwrap it back to the plain list the tool actually returned. Tools
    # that already return a dict (e.g. send_email) pass through unchanged.
    if isinstance(data, dict) and set(data.keys()) == {"result"}:
        return data["result"]
    return data
