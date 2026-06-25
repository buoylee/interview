#!/usr/bin/env bash
set -euo pipefail

B=http://localhost:18083
OUTFILE=/tmp/zdt.out

# 清除上次結果
rm -f "$OUTFILE"

# 背景壓測:300 個請求,每次間隔 0.02s,失敗計數寫到檔案
(
  fail=0
  total=0
  for i in $(seq 1 300); do
    code=$(curl -s -o /dev/null -w "%{http_code}" "$B/")
    if [ "$code" != "200" ]; then
      fail=$((fail + 1))
    fi
    total=$((total + 1))
    sleep 0.02
  done
  echo "TOTAL=$total FAIL=$fail" > "$OUTFILE"
) &
LOAD_PID=$!

# 等壓測跑一秒再 reload
sleep 1

echo ">>> 執行 nginx -s reload ..."
docker exec nginx-zdt nginx -s reload

echo ">>> 執行 nginx -t (設定校驗) ..."
docker exec nginx-zdt nginx -t

echo ">>> 等待壓測完成 ..."
wait $LOAD_PID

echo ""
cat "$OUTFILE"

if grep -q "FAIL=0" "$OUTFILE"; then
  echo "PASS: reload 期間零失敗"
else
  echo "FAIL: 有請求失敗"
  exit 1
fi
