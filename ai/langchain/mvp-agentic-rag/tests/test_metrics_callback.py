from langchain_core.outputs import LLMResult, ChatGeneration
from langchain_core.messages import AIMessage


def _llm_result_with_tokens(total):
    msg = AIMessage(content="hi", usage_metadata={
        "input_tokens": total // 2, "output_tokens": total - total // 2, "total_tokens": total})
    return LLMResult(generations=[[ChatGeneration(message=msg)]])


def test_monitoring_callback_counts_tokens_and_calls():
    from mvp_agentic_rag.obs.callbacks import MonitoringCallback
    from mvp_agentic_rag.obs import metrics

    before_calls = metrics.LLM_CALLS._value.get()
    before_tokens = metrics.LLM_TOKENS._value.get()

    cb = MonitoringCallback()
    cb.on_llm_start({}, ["prompt"], run_id="r1")
    cb.on_llm_end(_llm_result_with_tokens(10), run_id="r1")

    assert metrics.LLM_CALLS._value.get() == before_calls + 1
    assert metrics.LLM_TOKENS._value.get() == before_tokens + 10


def test_monitoring_callback_counts_tool_errors():
    from mvp_agentic_rag.obs.callbacks import MonitoringCallback
    from mvp_agentic_rag.obs import metrics

    before = metrics.TOOL_ERRORS._value.get()
    cb = MonitoringCallback()
    cb.on_tool_error(ValueError("boom"), run_id="r2")
    assert metrics.TOOL_ERRORS._value.get() == before + 1
