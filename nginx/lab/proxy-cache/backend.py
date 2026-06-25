#!/usr/bin/env python3
"""最小慢回源後端 — 每次回應遞增計數 + sleep 模擬慢 I/O。
快取命中時 count 不遞增，是「body 不變」斷言的可觀測點。
"""
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

counter = 0


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        global counter
        counter += 1
        body = f"count={counter}\n".encode()
        time.sleep(1)  # 模擬慢回源
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        # 告訴 nginx 可快取 60 秒（nginx.conf 會覆蓋成 10s）
        self.send_header("Cache-Control", "max-age=60")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        print(f"[backend] {self.address_string()} {format % args}", flush=True)


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 5000), Handler)
    print("[backend] listening on :5000", flush=True)
    server.serve_forever()
