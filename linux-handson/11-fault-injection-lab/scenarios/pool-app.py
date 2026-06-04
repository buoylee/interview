#!/usr/bin/env python3
# pool-app.py —— 一个最小但「真实」的带连接池的服务(只用 Python 标准库,免 pip)
#
# 角色:
#   - 它就是「你的服务」:收到 HTTP 请求 → 从连接池借一个连接 → 调下游(Redis)→ 还连接。
#   - 下游 = Redis,但请求是发给 Toxiproxy(26379),由它转发到真 Redis(6379)。
#     这样我们能在中间「把下游调慢」,模拟慢依赖。
#
# 为什么不用 redis-py?
#   - 想让你「看得见」连接池:它就是下面这个 queue.Queue,借/还/借不到就排队等,全摊开。
#   - 真实框架(HikariCP / redis-py / database/sql)的池本质一模一样,只是藏起来了。
#
# 可调参数(用环境变量):
#   POOL_SIZE  连接池大小(故意设小,方便打爆)            默认 4
#   POOL_WAIT  借不到连接最多等几秒(借鉴 HikariCP connectionTimeout)  默认 3
#   READ_TO    持有连接后、读下游的超时秒数;0 = 不设(=最初的 bug)  默认 0
#
# 跑法:  python3 pool-app.py
# 指标:  curl http://127.0.0.1:8080/stats

import os
import queue
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DOWNSTREAM = ("127.0.0.1", 26379)                      # → Toxiproxy 代理 → 真 Redis 6379
POOL_SIZE = int(os.environ.get("POOL_SIZE", "4"))
POOL_WAIT = float(os.environ.get("POOL_WAIT", "3"))
READ_TO = float(os.environ.get("READ_TO", "0"))        # 0 表示不设读超时(最初的 bug)

# ---- 连接池:就是一个装着 POOL_SIZE 个已连接 socket 的队列 ----
pool: "queue.Queue[socket.socket]" = queue.Queue(maxsize=POOL_SIZE)


def make_conn() -> socket.socket:
    s = socket.create_connection(DOWNSTREAM)
    if READ_TO > 0:
        s.settimeout(READ_TO)                          # 修复版才会给「读下游」设超时
    return s


for _ in range(POOL_SIZE):
    pool.put(make_conn())

# ---- 连接池监控指标(真实世界里这就是 Micrometer / HikariCP 暴露的那几个数)----
_lock = threading.Lock()
stats = {"inflight": 0, "waiting": 0, "pool_timeout": 0, "down_error": 0}


def redis_get(key: str) -> bytes:
    # RESP 协议手搓一条 GET 命令:  *2 $3 GET $len key
    cmd = f"*2\r\n$3\r\nGET\r\n${len(key)}\r\n{key}\r\n".encode()

    # —— ① 借连接:池空了,就在这里阻塞排队(这一步就是「连接池耗尽」的现场)——
    with _lock:
        stats["waiting"] += 1
    try:
        conn = pool.get(timeout=POOL_WAIT)
    except queue.Empty:
        with _lock:
            stats["waiting"] -= 1
            stats["pool_timeout"] += 1
        raise TimeoutError("borrow connection from pool timed out")
    with _lock:
        stats["waiting"] -= 1
        stats["inflight"] += 1

    # —— ② 持有连接,调下游:卡在 recv 等下游响应(就是你 strace 看到的 read 不返回)——
    try:
        conn.sendall(cmd)
        return conn.recv(4096)
    finally:
        with _lock:
            stats["inflight"] -= 1
        pool.put(conn)                                 # 还连接(demo 版不校验连接是否还健康)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/stats":
            with _lock:
                body = (
                    f"pool_size={POOL_SIZE} inflight={stats['inflight']} "
                    f"waiting={stats['waiting']} pool_timeout={stats['pool_timeout']} "
                    f"down_error={stats['down_error']}\n"
                ).encode()
            self.send_response(200)
            self.end_headers()
            self.wfile.write(body)
            return
        try:
            redis_get("k")
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok\n")
        except TimeoutError:
            self.send_response(503)                    # 借不到连接 → 快速失败
            self.end_headers()
            self.wfile.write(b"pool timeout\n")
        except (socket.timeout, OSError):
            with _lock:
                stats["down_error"] += 1
            self.send_response(504)                    # 下游读超时(只有 READ_TO>0 才会发生)
            self.end_headers()
            self.wfile.write(b"downstream timeout\n")

    def log_message(self, format, *args):              # 别刷屏(签名对齐基类)
        pass


if __name__ == "__main__":
    print(
        f"poolapp on http://127.0.0.1:8080  "
        f"POOL_SIZE={POOL_SIZE} POOL_WAIT={POOL_WAIT}s READ_TO={READ_TO}s "
        f"downstream={DOWNSTREAM[0]}:{DOWNSTREAM[1]}"
    )
    ThreadingHTTPServer(("127.0.0.1", 8080), Handler).serve_forever()
