#!/usr/bin/env sh
# 在 redis-node-1 容器内执行:用 6 个节点建 3主3从
redis-cli --cluster create \
  redis-node-1:6379 redis-node-2:6379 redis-node-3:6379 \
  redis-node-4:6379 redis-node-5:6379 redis-node-6:6379 \
  --cluster-replicas 1 --cluster-yes
