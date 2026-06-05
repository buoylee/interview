from prometheus_client import Counter, Histogram

LLM_TOKENS = Counter("rag_llm_tokens_total", "LLM total tokens consumed")
LLM_CALLS = Counter("rag_llm_calls_total", "Number of LLM calls")
TOOL_ERRORS = Counter("rag_tool_errors_total", "Number of tool errors")
LLM_LATENCY = Histogram("rag_llm_latency_seconds", "LLM call latency seconds")
