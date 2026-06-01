#!/usr/bin/env sh
# 在容器内跑。N=要造的普通 string key 数量(默认 100000)
N="${N:-100000}"
echo "generating $N string keys via pipe..."
{
  i=0
  while [ "$i" -lt "$N" ]; do
    printf 'SET key:%s val:%s\n' "$i" "$i"
    i=$((i+1))
  done
} | redis-cli --pipe
# 造一个大 hash(给 12 章 bigkeys)
redis-cli del bighash >/dev/null
{ i=0; while [ "$i" -lt 50000 ]; do printf 'HSET bighash f%s v%s\n' "$i" "$i"; i=$((i+1)); done; } | redis-cli --pipe
echo "done. dbsize=$(redis-cli dbsize)"
