from langchain_core.messages import AIMessage


class _FakeStructured:
    """模拟 llm.with_structured_output(Schema) 返回的 runnable。"""

    def __init__(self, value):
        self._value = value

    def invoke(self, messages):
        return self._value


class FakeLLM:
    """Chat 模型测试替身。
    - with_structured_output(Schema).invoke(...) 返回预置 structured_value
    - invoke(...) 返回 AIMessage(content=text)
    """

    def __init__(self, *, structured_value=None, text=""):
        self._structured_value = structured_value
        self._text = text

    def with_structured_output(self, schema):
        return _FakeStructured(self._structured_value)

    def invoke(self, messages):
        return AIMessage(content=self._text)
