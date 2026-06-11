# src/agent_loop/main.py
"""CLI:uv run python -m agent_loop.main "你的问题" """
import argparse
import time

from openai import OpenAI

from agent_loop.config import load_settings
from agent_loop.loop import run_agent
from agent_loop.mcp_client import READ_DOC
from agent_loop.otel import init_tracing
from agent_loop.tools import SEARCH_DOCS


def main() -> None:
    parser = argparse.ArgumentParser(description="裸循环 agent:本地知识库问答")
    parser.add_argument("question")
    parser.add_argument("--max-turns", type=int, default=8)
    args = parser.parse_args()

    settings = load_settings()
    tracer, provider = init_tracing(settings)
    client = OpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key)

    start = time.perf_counter()
    result = run_agent(
        client, settings.llm_model, [SEARCH_DOCS, READ_DOC], args.question, tracer,
        max_turns=args.max_turns,
    )
    elapsed = time.perf_counter() - start

    print(result.final_text)
    print(
        f"\n--- turns={result.turns} tools={result.tool_calls} "
        f"tokens={result.input_tokens}+{result.output_tokens} latency={elapsed:.2f}s"
    )
    provider.shutdown()  # 刷 BatchSpanProcessor,不调用会丢 trace


if __name__ == "__main__":
    main()
