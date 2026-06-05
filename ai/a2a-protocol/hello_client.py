"""
最小 A2A 客户端 —— a2a-sdk v1.0 精简骨架。

先启动 hello_server.py,再另开终端:
    python hello_client.py

⚠️ v1.0 客户端 API 仍在演进:send_message 返回的是 StreamResponse 流,
   每个 chunk 只含一种字段(用 HasField 判断)。若签名对不上,以官方 sample 的
   test_client.py 为准。
"""

import asyncio

from a2a.client import create_client
from a2a.helpers import get_message_text, new_text_message
from a2a.types import Role


async def main() -> None:
    # ① 只给 base url:client 会自动去 /.well-known/agent-card.json 拉名片、挑传输
    client = await create_client("http://127.0.0.1:41241")

    # ② 构造一条用户消息
    msg = new_text_message("你好 A2A", role=Role.ROLE_USER)

    # ③ v1.0:返回 StreamResponse 流,每个 chunk 只含 message / artifact_update /
    #    status_update / task 其中一种字段
    async for chunk in client.send_message(msg):
        if chunk.HasField("message"):
            print("Agent 回复:", get_message_text(chunk.message))
        elif chunk.HasField("artifact_update"):
            print("产出物 :", chunk.artifact_update)
        elif chunk.HasField("status_update"):
            print("状态   :", chunk.status_update.status.state)


if __name__ == "__main__":
    asyncio.run(main())
