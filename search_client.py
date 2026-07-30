import asyncio
import json
import threading
import config
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError as e:
    raise SystemExit(
        "The 'mcp' package is required. Install with: pip install -U mcp"
    ) from e


def _run_async(coro):
    """
    Runs an async coroutine from sync code safely, even when called from
    inside a framework (FastAPI/uvicorn) that already owns an event loop.
    asyncio.run() raises RuntimeError in those cases; running in a fresh
    daemon thread with its own loop avoids that.
    """
    result_box: list = []
    error_box: list = []

    def _runner():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result_box.append(loop.run_until_complete(coro))
        except Exception as exc:
            error_box.append(exc)
        finally:
            loop.close()

    t = threading.Thread(target=_runner, daemon=True)
    t.start()
    t.join()

    if error_box:
        raise error_box[0]
    return result_box[0] if result_box else None


def _parse_mcp_tool_result(tool_result) -> list[dict]:
    """Extracts the JSON list of {title, url, content} the server's `search`
    tool returns, from the MCP content blocks wrapping it."""
    hits: list[dict] = []
    if tool_result is None:
        return hits

    for block in getattr(tool_result, "content", []) or []:
        text = getattr(block, "text", None)
        if text is None:
            continue
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, list):
            for item in data:
                if not isinstance(item, dict):
                    continue
                hits.append(
                    {
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "content": item.get("content", ""),
                    }
                )
    return hits


async def _mcp_search_async(
    query: str,
    allowed_domains: list[str] | None,
    blocked_domains: list[str] | None,
    max_results: int,
) -> list[dict]:
    server_params = StdioServerParameters(
        command=config.MCP_SERVER_COMMAND,
        args=config.MCP_SERVER_ARGS,
        env=config.MCP_SERVER_ENV,
    )
    tool_args = {"query": query, "max_results": max_results}
    if allowed_domains:
        tool_args["allowed_domains"] = allowed_domains
    if blocked_domains:
        tool_args["blocked_domains"] = blocked_domains

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await asyncio.wait_for(session.initialize(), timeout=config.MCP_TIMEOUT_SECONDS)
            result = await asyncio.wait_for(
                session.call_tool(config.MCP_SEARCH_TOOL_NAME, arguments=tool_args),
                timeout=config.MCP_TIMEOUT_SECONDS,
            )
            return _parse_mcp_tool_result(result)


def search_mcp(
    query: str,
    allowed_domains: list[str] | None = None,
    blocked_domains: list[str] | None = None,
    max_results: int = 5,
) -> list[dict]:
    """
    Runs a search via the MCP server. Pass allowed_domains=None (or [])
    for an open, unrestricted web search — the toggle in the API layer
    controls this. blocked_domains is always applied regardless.
    """
    if not config.MCP_ENABLED:
        raise RuntimeError("MCP_ENABLED is not set to 'true' — check your .env")
    if not config.MCP_SERVER_COMMAND:
        raise RuntimeError("MCP_SERVER_COMMAND is not configured — check your .env")

    try:
        return _run_async(
            _mcp_search_async(query, allowed_domains, blocked_domains, max_results)
        )
    except asyncio.TimeoutError:
        raise RuntimeError(f"MCP search timed out after {config.MCP_TIMEOUT_SECONDS}s")
