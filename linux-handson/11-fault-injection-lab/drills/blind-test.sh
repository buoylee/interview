#!/usr/bin/env bash
#
# 盲测演练(blind test):随机注入一个故障,但不告诉你是哪个。
# 你扮演 on-call,按 07 的「第一分钟清单 + 分层路径」自己诊断;
# 查完回来按 Enter,看正确答案和用时。
#
# 前置:先在 VM 里跑过 00-lab/provision.sh。
# 建议:另开一个终端做诊断,这个终端留着按 Enter 揭晓。
#
set -uo pipefail

BG_PIDS=()
TMPFILES=()
ANSWER=""

cleanup() {
  for p in "${BG_PIDS[@]:-}"; do kill "$p" 2>/dev/null || true; done
  pkill stress-ng 2>/dev/null || true
  pkill -f .bt_fd.py 2>/dev/null || true
  for f in "${TMPFILES[@]:-}"; do rm -f "$f" 2>/dev/null || true; done
}
trap cleanup EXIT

inject_cpu() {
  stress-ng --cpu 2 --timeout 900s >/dev/null 2>&1 &
  BG_PIDS+=($!)
  ANSWER="01 CPU 饱和 → scenarios/01-cpu-saturation.md  (线索:%us 高、load 高、wa 低)"
}

inject_io() {
  fio --name=bt --rw=randwrite --bs=4k --size=256M --numjobs=2 --iodepth=16 \
      --time_based --runtime=900 --direct=1 --filename=/tmp/.bt_fio >/dev/null 2>&1 &
  BG_PIDS+=($!); TMPFILES+=(/tmp/.bt_fio)
  ANSWER="02 I/O 过载 → scenarios/02-io-overload.md  (线索:%wa 高、D 进程、iostat %util/await 飙)"
}

inject_fd() {
  cat > /tmp/.bt_fd.py <<'EOF'
import time
held = []
try:
    while True:
        held.append(open("/etc/hostname")); time.sleep(0.001)
except OSError:
    pass
while True:          # 撞上限后保持打开,维持现场
    time.sleep(1)
EOF
  ( ulimit -n 256; exec python3 /tmp/.bt_fd.py ) >/dev/null 2>&1 &
  BG_PIDS+=($!); TMPFILES+=(/tmp/.bt_fd.py)
  ANSWER="03 fd 耗尽 → scenarios/03-fd-exhaustion.md  (线索:某进程 ls /proc/PID/fd 数量顶在上限)"
}

inject_mem() {
  stress-ng --vm 1 --vm-bytes 60% --timeout 900s >/dev/null 2>&1 &
  BG_PIDS+=($!)
  ANSWER="06 内存压力 → scenarios/06-oom-vs-pagecache.md  (线索:free available 掉、ps --sort=-rss 有大 RSS 进程)"
}

CASES=(cpu io fd mem)
PICK=${CASES[$((RANDOM % ${#CASES[@]}))]}

echo "🎲 正在注入一个随机故障……(不会告诉你是哪个)"
inject_"$PICK"
sleep 2
START=$SECONDS

cat <<'MSG'

✅ 故障已注入。现在你是 on-call。
   另开一个终端,按 07 的路径自己诊断:
     uptime → top(%us / %wa / 有没有 D 进程?)→ vmstat / iostat
            → pidstat 锁进程 → lsof / ss / strace / free 收口
   先写下你的结论(哪类资源?哪个进程?根因?),再回这里按 Enter 揭晓。
MSG

read -r _
ELAPSED=$((SECONDS - START))

echo
echo "⏱  用时 ${ELAPSED}s"
echo "📖 正确答案:场景 ${ANSWER}"
echo "   对照该场景的「破案点」看你漏了哪一步。再来一局?重新运行本脚本。"
