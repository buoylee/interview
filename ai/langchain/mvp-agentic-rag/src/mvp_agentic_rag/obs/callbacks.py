import time

from langchain_core.callbacks import BaseCallbackHandler

from mvp_agentic_rag.obs import metrics


class MonitoringCallback(BaseCallbackHandler):
    """把 LLM/工具的关键指标打到 Prometheus(与 trace 互补:metrics 看聚合)。"""

    def __init__(self) -> None:
        self._starts: dict = {}

    def on_llm_start(self, serialized, prompts, *, run_id=None, **kwargs) -> None:
        self._starts[run_id] = time.monotonic()

    def on_llm_end(self, response, *, run_id=None, **kwargs) -> None:
        metrics.LLM_CALLS.inc()
        start = self._starts.pop(run_id, None)
        if start is not None:
            metrics.LLM_LATENCY.observe(time.monotonic() - start)
        total = 0
        for gens in getattr(response, "generations", []) or []:
            for gen in gens:
                msg = getattr(gen, "message", None)
                usage = getattr(msg, "usage_metadata", None) if msg else None
                if usage:
                    total += usage.get("total_tokens", 0)
        if total:
            metrics.LLM_TOKENS.inc(total)

    def on_tool_error(self, error, *, run_id=None, **kwargs) -> None:
        metrics.TOOL_ERRORS.inc()
