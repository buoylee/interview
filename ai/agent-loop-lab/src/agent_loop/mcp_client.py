"""MCP stdio 客户端的同步封装。

为简单起见每次调用都重新拉起 server 子进程并走 initialize 握手——
生产实现会保持长连接复用 session(这是 lab 的刻意取舍,对比笔记里要提)。
"""
import asyncio
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from agent_loop.tools import ToolSpec

SERVER_PARAMS = StdioServerParameters(
    command=sys.executable, args=["-m", "agent_loop.mcp_server"]
)


def call_mcp_tool(tool_name: str, arguments: dict) -> str:
    async def _call() -> str:
        async with stdio_client(SERVER_PARAMS) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
                return "\n".join(
                    block.text for block in result.content if getattr(block, "text", None)
                )

    return asyncio.run(_call())


READ_DOC = ToolSpec(
    name="read_doc",
    description="通过 MCP 读取知识库指定 .md 文件全文。先用 search_docs 定位文件名,需要完整上下文时再用本工具。",
    parameters={
        "type": "object",
        "properties": {"filename": {"type": "string", "description": "如 postgres.md"}},
        "required": ["filename"],
    },
    handler=lambda filename: call_mcp_tool("read_doc", {"filename": filename}),
)
