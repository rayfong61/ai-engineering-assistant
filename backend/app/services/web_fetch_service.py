import asyncio

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# The only tool in this project that talks to a genuine third-party MCP
# server: modelcontextprotocol/servers' official "fetch" reference
# implementation, spawned as a subprocess per call and driven over the real
# stdio MCP protocol (initialize -> call_tool). Contrast with every other
# app/tools/* function, which is a plain in-repo call with no protocol layer
# -- see CLAUDE.md's "Tools" section for why that split is deliberate: a
# protocol layer only earns its keep when there's a real second party on the
# other end, and here there is (a server this repo doesn't own or deploy).
_SERVER_PARAMS = StdioServerParameters(command="python", args=["-m", "mcp_server_fetch"])
_TIMEOUT_SECONDS = 20


async def _call_fetch_tool(url: str, max_length: int) -> str:
    async with stdio_client(_SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("fetch", {"url": url, "max_length": max_length})
            return "\n".join(block.text for block in result.content if block.type == "text")


def fetch_url(url: str, max_length: int = 5000) -> dict:
    content = asyncio.run(asyncio.wait_for(_call_fetch_tool(url, max_length), timeout=_TIMEOUT_SECONDS))
    return {"url": url, "content": content}
