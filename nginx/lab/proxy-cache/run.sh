#!/usr/bin/env bash
# proxy-cache lab 驗證腳本
# 預期：首請求 MISS、次請求 HIT、命中期間 body/count 不變
set -euo pipefail

B=http://localhost:18081

# s() 印出 X-Cache-Status header；body 暫存 /tmp/body
s () {
    curl -s -D - "$1" -o /tmp/body
}

echo "=== proxy-cache lab ==="

# 第一次請求 — 應 MISS（後端計數 +1，sleep 1 秒）
echo -n "first  -> "
STATUS1=$(s "$B/cached/x" | grep -i '^X-Cache-Status' | tr -d '\r' | awk '{print $2}')
echo "X-Cache-Status: $STATUS1"

if [[ "$STATUS1" != "MISS" ]]; then
    echo "FAIL: expected MISS on first request, got $STATUS1"
    exit 1
fi
echo "PASS: first request MISS"

# 第二次請求 — 應 HIT（從快取回，不碰後端）
echo -n "second -> "
STATUS2=$(s "$B/cached/x" | grep -i '^X-Cache-Status' | tr -d '\r' | awk '{print $2}')
echo "X-Cache-Status: $STATUS2"

if [[ "$STATUS2" != "HIT" ]]; then
    echo "FAIL: expected HIT on second request, got $STATUS2"
    exit 1
fi
echo "PASS: second request HIT"

# body 不變斷言
b1=$(curl -s "$B/cached/x")
b2=$(curl -s "$B/cached/x")
if [[ "$b1" == "$b2" ]]; then
    echo "PASS: body unchanged while cached ($b1)"
else
    echo "FAIL: body changed between requests ($b1 vs $b2)"
    exit 1
fi

echo "=== ALL PASS ==="
