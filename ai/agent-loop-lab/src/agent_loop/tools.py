"""工具定义。ToolSpec 是「工具 = JSON Schema + 本地函数」的最小表达——
框架里的 @tool 装饰器底下就是这点东西。"""
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

# 复用 MVP 的语料,保证 lab 和 LangGraph 版回答同样的问题可对比
DOCS_DIR = Path(
    os.environ.get(
        "LAB_DOCS_DIR",
        Path(__file__).resolve().parents[3] / "langchain" / "mvp-agentic-rag" / "sample_docs",
    )
)


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema
    handler: Callable[..., str]

    def to_openai(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


def search_docs(query: str, top_k: int = 3) -> str:
    """按关键词给段落打分,返回得分最高的 top_k 段。MVP hybrid 检索的极简对照物。"""
    keywords = [w.lower() for w in query.split() if len(w) > 1]
    scored: list[tuple[int, str]] = []
    for path in sorted(DOCS_DIR.glob("*.md")):
        for para in path.read_text(encoding="utf-8").split("\n\n"):
            text = para.lower()
            score = sum(text.count(k) for k in keywords)
            if score > 0:
                scored.append((score, f"[{path.name}] {para.strip()}"))
    if not scored:
        return "NO_MATCH: 知识库中没有相关内容"
    scored.sort(key=lambda item: -item[0])
    return "\n\n".join(snippet for _, snippet in scored[:top_k])


SEARCH_DOCS = ToolSpec(
    name="search_docs",
    description="在本地知识库(markdown)中按关键词检索,返回最相关段落(带 [文件名] 前缀)。查不到返回 NO_MATCH。",
    parameters={
        "type": "object",
        "properties": {"query": {"type": "string", "description": "检索关键词,空格分隔"}},
        "required": ["query"],
    },
    handler=search_docs,
)
