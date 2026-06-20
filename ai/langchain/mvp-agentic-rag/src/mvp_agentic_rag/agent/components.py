from typing import Literal, Protocol

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from mvp_agentic_rag.retrieval.types import RetrievedChunk


# ---- 结构化输出 schema ----
class RouteDecision(BaseModel):
    # Literal 而非裸 str:with_structured_output 会把它编成枚举,模型只能从这三个里选,
    # 不会再吐出描述性字符串被 supervisor 静默兜底。
    next: Literal["kb_rag", "web", "FINISH"] = Field(description="下一步交给谁")


class GradeDecision(BaseModel):
    relevant: bool = Field(description="检索片段是否与问题相关")


class GroundingDecision(BaseModel):
    grounded: bool = Field(description="答案是否被检索片段支持(无幻觉)")


# ---- 决策接口(便于测试注入)----
class Router(Protocol):
    def route(self, messages: list) -> str: ...


class DocGrader(Protocol):
    def grade(self, query: str, chunks: list[RetrievedChunk]) -> bool: ...


class QueryRewriter(Protocol):
    def rewrite(self, query: str) -> str: ...


class AnswerGenerator(Protocol):
    def generate(self, query: str, chunks: list[RetrievedChunk]) -> str: ...


class GroundingChecker(Protocol):
    def check(self, answer: str, chunks: list[RetrievedChunk]) -> bool: ...


def _format(chunks: list[RetrievedChunk]) -> str:
    return "\n\n".join(f"[{i + 1}] {c.content}" for i, c in enumerate(chunks))


# ---- LLM 实现 ----
_ROUTER_SYS = (
    "你是一个多 Agent 调度器。根据当前对话,决定下一步交给谁:\n"
    "- kb_rag:需要查企业知识库才能回答的问题(技术/产品/文档类问题默认走这里)\n"
    "- web:知识库覆盖不到、需要外部实时信息的问题\n"
    "- FINISH:对话里【已经存在】助手给出的最终答案,无需再处理\n"
    "重要:只要对话里还【没有】助手的答案,就绝不能输出 FINISH——"
    "必须先路由到 kb_rag 或 web。\n"
    "只输出路由决策。"
)


class LLMRouter:
    def __init__(self, llm):
        self._llm = llm.with_structured_output(RouteDecision)

    def route(self, messages: list) -> str:
        out = self._llm.invoke([SystemMessage(content=_ROUTER_SYS), *messages])
        return out.next


_GRADER_SYS = "你判断检索到的片段是否与用户问题相关。只输出布尔判断。"


class LLMDocGrader:
    def __init__(self, llm):
        self._llm = llm.with_structured_output(GradeDecision)

    def grade(self, query: str, chunks: list[RetrievedChunk]) -> bool:
        prompt = f"问题:{query}\n\n检索片段:\n{_format(chunks)}\n\n这些片段相关吗?"
        return self._llm.invoke([SystemMessage(content=_GRADER_SYS), HumanMessage(content=prompt)]).relevant


_REWRITER_SYS = "你把用户问题改写得更利于检索(澄清意图、补全关键词)。只输出改写后的问题。"


class LLMQueryRewriter:
    def __init__(self, llm):
        self._llm = llm

    def rewrite(self, query: str) -> str:
        out = self._llm.invoke([SystemMessage(content=_REWRITER_SYS), HumanMessage(content=query)])
        return out.content


_GEN_SYS = (
    "你是企业知识库助手。只依据给定片段回答,并用 [n] 标注引用的片段编号。"
    "若片段不足以回答,明确说明依据不足。"
)


class LLMAnswerGenerator:
    def __init__(self, llm):
        self._llm = llm

    def generate(self, query: str, chunks: list[RetrievedChunk]) -> str:
        prompt = f"问题:{query}\n\n可用片段:\n{_format(chunks)}\n\n请作答并标注引用。"
        return self._llm.invoke([SystemMessage(content=_GEN_SYS), HumanMessage(content=prompt)]).content


_GROUND_SYS = "你判断答案是否完全被给定片段支持(无编造)。只输出布尔判断。"


class LLMGroundingChecker:
    def __init__(self, llm):
        self._llm = llm.with_structured_output(GroundingDecision)

    def check(self, answer: str, chunks: list[RetrievedChunk]) -> bool:
        prompt = f"答案:{answer}\n\n片段:\n{_format(chunks)}\n\n答案是否被片段支持?"
        return self._llm.invoke([SystemMessage(content=_GROUND_SYS), HumanMessage(content=prompt)]).grounded
