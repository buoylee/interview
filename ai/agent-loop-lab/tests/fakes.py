import json
from types import SimpleNamespace


def _usage(prompt=10, completion=5):
    return SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion)


def tool_call_response(name: str, arguments: dict, call_id: str = "call_1"):
    tc = SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=json.dumps(arguments)),
    )
    msg = SimpleNamespace(content=None, tool_calls=[tc])
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=_usage())


def final_response(text: str):
    msg = SimpleNamespace(content=text, tool_calls=None)
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=_usage())


class FakeChatClient:
    """按脚本依次吐响应;记录每次收到的 kwargs 供断言。鸭子类型兼容 openai.OpenAI。"""

    def __init__(self, scripted):
        self._scripted = list(scripted)
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create)
        )

    def _create(self, **kwargs):
        # messages 列表会被 run_agent 持续 mutate,这里按调用时刻快照
        self.calls.append({**kwargs, "messages": [dict(m) for m in kwargs["messages"]]})
        return self._scripted.pop(0)
