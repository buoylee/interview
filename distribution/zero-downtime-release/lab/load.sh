#!/usr/bin/env bash
# 持续并发打 /work,统计 2xx / 非2xx / 连接失败,用来观测"下线一个后端时掉不掉请求"。
#
# 用法(务必用 bash,别用 zsh 直接跑——见 lab/README 的坑):
#   bash load.sh [持续秒数]
# 可调环境变量:
#   URL=http://localhost:8080/work  CONC=12  bash load.sh 30
set -u

URL="${URL:-http://localhost:8080/work}"
DUR="${1:-30}"
CONC="${CONC:-12}"
TMP="$(mktemp -d)"
end=$(( $(date +%s) + DUR ))

worker() {
  local id="$1" ok=0 bad=0 err=0 code rc
  while [ "$(date +%s)" -lt "$end" ]; do
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$URL" 2>/dev/null); rc=$?
    if   [ "$rc" -ne 0 ];      then err=$((err+1))   # 连接层失败:reset / refused / timeout
    elif [ "$code" = "200" ];  then ok=$((ok+1))
    else                            bad=$((bad+1))   # 5xx 等
    fi
  done
  echo "$ok $bad $err" > "$TMP/$id"
}

echo "打 $URL  并发=$CONC  持续=${DUR}s"
echo ">>> 现在另开一个终端,跑下面 README 里的【场景A】或【场景B】去 stop / kill 一个后端 <<<"
for i in $(seq 1 "$CONC"); do worker "$i" & done
wait

ok=0; bad=0; err=0
for f in "$TMP"/*; do read -r a b c < "$f"; ok=$((ok+a)); bad=$((bad+b)); err=$((err+c)); done
rm -rf "$TMP"

echo "────────────────────────────"
echo "2xx 成功                       = $ok"
echo "非2xx(5xx 等)                 = $bad"
echo "连接失败(reset/refused/timeout)= $err"
echo "★ 掉请求合计                   = $((bad + err))"
