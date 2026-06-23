#!/usr/bin/env bash
# 對應 ch05 §2。證明:limit=10 是「全域」的——交替打兩個節點,
# 合計到第 11 次就被擋,計數跨節點連續遞增(共享 Redis)。
set -u

echo "=== 重置計數(清掉上一輪殘留)==="
docker compose exec -T redis redis-cli FLUSHALL >/dev/null

echo "=== 交替打 node1(:8001)/ node2(:8002),同一 client,共 12 次(limit=10)==="
for i in $(seq 1 12); do
  if [ $((i % 2)) -eq 0 ]; then port=8001; else port=8002; fi
  printf "第%2d次 → " "$i"
  curl -s "http://localhost:$port/ping?client=alice"
done
