#!/usr/bin/env bash
# 對應 ch10。用 bash 跑(陣列需要 bash)。展示:語義快取命中 + token 預算 429。
set -u
GW=http://localhost:9000/chat
H='content-type: application/json'

echo "=== 重置 ==="
docker compose exec -T redis redis-cli FLUSHALL >/dev/null

echo
echo "=== (a) 語義快取:近義兩問,第二次應命中(cached=true,不計費)==="
echo -n "Q1 「什麼是 API 網關」     → "; curl -s -X POST "$GW" -H "$H" -d '{"client":"u1","prompt":"什麼是 API 網關"}'; echo
echo -n "Q2 「API 網關是什麼」      → "; curl -s -X POST "$GW" -H "$H" -d '{"client":"u1","prompt":"API 網關是什麼"}'; echo

echo
echo "=== (b) token 預算:client=u2 連打不同主題(都 miss、都計費),累計超 BUDGET 後 429 ==="
prompts=("什麼是負載均衡" "解釋資料庫索引原理" "TCP 三次握手是什麼" "什麼是垃圾回收機制" "解釋 CAP 定理" "訊息佇列有什麼用")
i=0
for p in "${prompts[@]}"; do
  i=$((i + 1))
  printf "第%d問「%s」 → " "$i" "$p"
  curl -s -w " [HTTP %{http_code}]" -X POST "$GW" -H "$H" -d "{\"client\":\"u2\",\"prompt\":\"$p\"}"; echo
done
