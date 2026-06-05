import json
import sys
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.messages import AIMessage, HumanMessage

from mvp_agentic_rag.agent.factory import build_production_agent_graph
from mvp_agentic_rag.core.config import get_settings
from mvp_agentic_rag.core.db import get_database
from mvp_agentic_rag.eval.dataset import load_golden
from mvp_agentic_rag.eval.report import to_json, to_markdown
from mvp_agentic_rag.eval.runner import run_eval

GOLDEN = "eval/golden/cases.jsonl"
OUT_DIR = Path("eval/reports")


def _make_agent_runner(graph):
    def runner(question: str) -> dict:
        config = {"configurable": {"thread_id": f"eval-{abs(hash(question))}"}}
        # 用 stream 观测实际走到的专家节点(kb_rag / web)
        route = ""
        for update in graph.stream(
            {"messages": [HumanMessage(content=question)], "next": "",
             "citations": [], "step_budget": 6},
            config, stream_mode="updates",
        ):
            for node in update:
                if node in ("kb_rag", "web"):
                    route = node
        state = graph.get_state(config).values
        answer = ""
        for m in reversed(state.get("messages", [])):
            if isinstance(m, AIMessage):
                answer = str(m.content)
                break
        return {"answer": answer, "route": route, "citations": state.get("citations", [])}

    return runner


def main() -> int:
    s = get_settings()
    db = get_database()
    db.init_schema()
    graph = build_production_agent_graph(db, InMemorySaver(), s)
    cases = load_golden(GOLDEN)
    report = run_eval(_make_agent_runner(graph), cases)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "report.json").write_text(
        json.dumps(to_json(report), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUT_DIR / "report.md").write_text(to_markdown(report), encoding="utf-8")
    print(f"eval done: pass_rate={report.pass_rate:.2%} ({report.passed_count}/{len(cases)})")
    print(f"reports written to {OUT_DIR}/report.json|md")
    db.close()
    return 0 if report.pass_rate >= 0.5 else 1  # 灰度门:低于阈值退出码非 0


if __name__ == "__main__":
    raise SystemExit(main())
