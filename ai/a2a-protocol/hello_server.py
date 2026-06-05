"""
最小 A2A 服务端 —— a2a-sdk v1.0 精简骨架。

只暴露 JSON-RPC 传输 + Agent Card,刻意去掉官方 sample 里的 gRPC/REST/v0.3
兼容代码,方便对着读、理解每个零件。

跑法:
    uv add a2a-sdk            # 或 pip install a2a-sdk
    python hello_server.py
然后浏览器开 http://127.0.0.1:41241/.well-known/agent-card.json 看名片。

⚠️ 本文件按 a2a-sdk v1.0 官方 sample + 迁移指南整理,作者未在本机实跑。
   v1.0 API 仍在演进;若 import/签名对不上,以官方 helloworld sample 的
   `uv run .` + `test_client.py` 为准:
   https://github.com/a2aproject/a2a-samples/tree/main/samples/python/agents/helloworld
"""

import uvicorn
from starlette.applications import Starlette

from a2a.server.agent_execution.agent_executor import AgentExecutor
from a2a.server.agent_execution.context import RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks.inmemory_task_store import InMemoryTaskStore
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.helpers import new_text_message
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
    Role,
)

HOST, PORT = "127.0.0.1", 41241


class HelloExecutor(AgentExecutor):
    """你的 agent 业务逻辑就写在这。≈ Java 的一个 Servlet / gRPC service impl。"""

    async def execute(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        query = context.get_user_input()  # 取出对方发来的文本
        reply = f"Hello World! 你说的是: {query!r}"
        # ——「消息直返」模式:enqueue 一条 Message 就结束,适合一问一答。
        #   (长任务用另一种「Task 生命周期」模式:先 enqueue Task,再推
        #    status_update / artifact_update —— Task 必须第一个发。)
        await event_queue.enqueue_event(
            new_text_message(reply, role=Role.ROLE_AGENT)
        )

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        raise Exception("这个最小 agent 不支持取消")


def build_app() -> Starlette:
    # ① Agent Card = agent 的「能力名片」,自动挂在 /.well-known/agent-card.json
    agent_card = AgentCard(
        name="Hello Agent",
        description="一个最小的 A2A agent,只会打招呼。",
        version="1.0.0",
        capabilities=AgentCapabilities(streaming=False, push_notifications=False),
        default_input_modes=["text"],
        default_output_modes=["text"],
        skills=[
            AgentSkill(
                id="hello",
                name="Hello",
                description="跟调用方打招呼。",
                tags=["greeting"],
                examples=["hi", "hello", "你好"],
            )
        ],
        # ② v1.0 用 supported_interfaces 声明传输(取代旧版顶层 url 字段)
        supported_interfaces=[
            AgentInterface(
                protocol_binding="JSONRPC",
                protocol_version="1.0",
                url=f"http://{HOST}:{PORT}/a2a/jsonrpc",
            ),
        ],
    )

    # ③ RequestHandler 把协议层和你的 executor 接起来;v1.0 起 agent_card 必传
    handler = DefaultRequestHandler(
        agent_executor=HelloExecutor(),
        task_store=InMemoryTaskStore(),
        agent_card=agent_card,
    )

    # ④ v1.0 去掉了 A2AStarletteApplication 包装类,改用 route 工厂函数拼 ASGI app
    routes = [
        *create_agent_card_routes(agent_card),
        *create_jsonrpc_routes(handler, rpc_url="/a2a/jsonrpc"),
    ]
    return Starlette(routes=routes)


if __name__ == "__main__":
    uvicorn.run(build_app(), host=HOST, port=PORT)
