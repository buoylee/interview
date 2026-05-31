#!/usr/bin/env bash
#
# quick-diag.sh — 一键「第一分钟」体检脚本
# 把 07-troubleshooting-playbook 的 USE/分层排查思路固化成脚本。
# 用法:bash quick-diag.sh        (部分项需 root 才完整,如 dmesg)
#
set -euo pipefail

section() { printf '\n\033[1;36m==== %s ====\033[0m\n' "$1"; }
have()    { command -v "$1" >/dev/null 2>&1; }

trap 'echo; echo "诊断结束。"' EXIT

section "① 全局负载 (uptime)"
uptime
echo "提示:load 是 R+D 任务数的平均,不只是 CPU(见 07)。和 CPU 核数比:$(nproc) 核。"

section "② 内核最近报错 (dmesg tail)"
if dmesg -T >/dev/null 2>&1; then
  dmesg -T 2>/dev/null | tail -n 8 || true
else
  echo "(需 root 才能看 dmesg)"
fi

section "③ CPU / 运行队列 / swap (vmstat)"
if have vmstat; then
  vmstat 1 3
  echo "看:r=运行队列, b=阻塞(等IO), si/so=swap(>0危险), wa=等IO%, us/sy=CPU"
else echo "(未安装 procps)"; fi

section "④ 每核 CPU (mpstat)"
if have mpstat; then mpstat -P ALL 1 1 | tail -n +4
  echo "看:是否只有单核打满(单线程瓶颈)"
else echo "(未安装 sysstat)"; fi

section "⑤ 内存 (free)"
free -h
echo "看:available 才是真正可用(不是 free);Swap used 增长要警惕(见 04)。"

section "⑥ 磁盘 I/O (iostat)"
if have iostat; then iostat -xz 1 2 | tail -n +4
  echo "看:%util 高 + await 飙升 = IO 瓶颈;SSD 别只看 util(见 05)。"
else echo "(未安装 sysstat)"; fi

section "⑦ 吃 CPU/内存 的进程 (top N)"
ps -eo pid,ppid,stat,%cpu,%mem,rss,comm --sort=-%cpu | head -n 6
echo "看:STAT 有 D(等IO,见03) 或 Z(僵尸) 吗?RSS 大户是谁(见04)?"

section "⑧ 网络连接概况 (ss)"
if have ss; then
  ss -s | head -n 4
  echo "各状态计数:"
  ss -tan 2>/dev/null | awk 'NR>1{print $1}' | sort | uniq -c | sort -rn | head
  echo "看:CLOSE-WAIT 多=代码漏 close(见06);TIME-WAIT 多通常无害。"
else echo "(未安装 iproute2)"; fi

section "⑨ 监听端口与全连接队列 (ss -lnt)"
if have ss; then ss -lnt | head
  echo "看:Recv-Q 持续接近 Send-Q = 全连接队列将满(见06)。"
fi
