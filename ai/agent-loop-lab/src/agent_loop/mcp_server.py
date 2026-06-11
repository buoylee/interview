"""最小 MCP server:暴露一个 read_doc 工具。`python -m agent_loop.mcp_server` 以 stdio 运行。"""
from mcp.server.fastmcp import FastMCP

from agent_loop.tools import DOCS_DIR

mcp = FastMCP("doc-reader")


@mcp.tool()
def read_doc(filename: str) -> str:
    """读取知识库中指定 markdown 文件的完整内容。"""
    base = DOCS_DIR.resolve()
    path = (base / filename).resolve()
    if path.parent != base or path.suffix != ".md":
        return "ERROR: 只允许读取知识库目录下的 .md 文件"
    if not path.exists():
        available = ", ".join(sorted(p.name for p in base.glob("*.md")))
        return f"ERROR: 文件不存在。可用文件: {available}"
    return path.read_text(encoding="utf-8")


if __name__ == "__main__":
    mcp.run()  # 默认 stdio transport
