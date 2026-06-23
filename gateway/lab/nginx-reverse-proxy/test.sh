#!/usr/bin/env bash
# 對應 ch01。先暖機(等兩個後端都就緒),再展示「乾淨輪詢」+「L7 path 路由」。
# 為什麼要暖機:啟動瞬間 echo2 可能還沒就緒,nginx 被動健康檢查會把它標記 down
# 約 10s(fail_timeout 默認值)。這 10s 內請求全打 echo1 —— 這正是 ch03 健康檢查的伏筆。
set -u
BASE=http://localhost:8080

echo "=== 暖機:輪詢 / 直到 echo1、echo2 都回應(最多 20s)==="
seen1=0; seen2=0
for i in $(seq 1 20); do
  r=$(curl -s "$BASE/" 2>/dev/null)
  case "$r" in *echo1*) seen1=1;; *echo2*) seen2=1;; esac
  [ $seen1 -eq 1 ] && [ $seen2 -eq 1 ] && { echo "兩後端就緒(${i}s)"; break; }
  sleep 1
done

echo
echo "=== / 連打 6 次:預期 echo1/echo2 交替(輪詢)==="
for i in $(seq 1 6); do curl -s "$BASE/"; done

echo
echo "=== /a 連打 3 次:預期全 echo1(L7 按 path 定向)==="
for i in $(seq 1 3); do curl -s "$BASE/a"; done

echo
echo "=== nginx 進程數:1 master + N worker(= CPU 核)==="
docker compose exec -T nginx sh -c 'ps -eo comm | grep -c nginx'
