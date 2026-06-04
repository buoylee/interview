#!/usr/bin/env bash
#
# linux-handson 沙箱 provision 脚本
# 在 Ubuntu (22.04/24.04) VM 里以 root 运行,装齐全课要用的排查工具箱。
#
# 用法(在 Mac 上):
#   multipass transfer linux-handson/00-lab/provision.sh linux-lab:/tmp/provision.sh
#   multipass exec linux-lab -- sudo bash /tmp/provision.sh
#
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "请用 root 运行:sudo bash $0" >&2
  exit 1
fi

PKGS=(
  procps        # ps / top / vmstat / free / kill
  htop          # 交互式进程查看
  sysstat       # iostat / pidstat / sar / mpstat
  strace        # 跟踪系统调用(也能注入故障:strace --inject=)
  ltrace        # 跟踪库调用
  lsof          # 进程打开的文件与 fd
  iproute2      # ss / ip / tc(tc 给 11 章做 netem 网络故障注入)
  net-tools     # netstat / ifconfig(旧式,对照学)
  tcpdump       # 抓包
  stress-ng     # 制造 CPU/内存/IO 压力,用来"造现象"
  fio           # 精确磁盘 I/O 压测/造现象(11 故障注入实验室)
  dstat         # 一屏看 CPU/磁盘/网络
  dnsutils      # dig / nslookup
  file          # 看文件类型
  tree          # 看目录树
  vim           # 编辑器
  curl          # HTTP 排查 / 下载 toxiproxy
  netcat-openbsd # nc,连通性排查
)

echo ">>> apt update"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq

echo ">>> 安装工具箱:${PKGS[*]}"
apt-get install -y -qq "${PKGS[@]}"

# ---- Toxiproxy:应用层故障注入(在 app 与下游之间注延迟/断连/限速)----
# 不在 apt 源里,从 GitHub release 装二进制。版本可改;arch 自动识别(amd64/arm64)。
# 用法见 11-fault-injection-lab/。
TOXIPROXY_VER="2.12.0"
install_toxiproxy() {
  if command -v toxiproxy-server >/dev/null 2>&1; then
    echo ">>> toxiproxy 已装,跳过"; return 0
  fi
  local arch base
  arch="$(dpkg --print-architecture)"   # amd64 / arm64
  base="https://github.com/Shopify/toxiproxy/releases/download/v${TOXIPROXY_VER}"
  echo ">>> 安装 toxiproxy v${TOXIPROXY_VER} (${arch})"
  curl -fsSL "${base}/toxiproxy-server-linux-${arch}" -o /usr/local/bin/toxiproxy-server
  curl -fsSL "${base}/toxiproxy-cli-linux-${arch}"    -o /usr/local/bin/toxiproxy-cli
  chmod +x /usr/local/bin/toxiproxy-server /usr/local/bin/toxiproxy-cli
}
install_toxiproxy || echo "⚠️  toxiproxy 安装失败(查网络),手动装法见 11-fault-injection-lab/README.md" >&2

echo
echo ">>> 冒烟测试(核心工具,缺了算失败)"
MISS=0
for t in ps top htop vmstat iostat pidstat ss ip tc strace ltrace lsof tcpdump stress-ng fio dstat dig; do
  if command -v "$t" >/dev/null 2>&1; then
    printf "OK   %s\n" "$t"
  else
    printf "MISS %s\n" "$t"
    MISS=1
  fi
done

# 软检查(缺了只告警,不让整脚本失败):netem 与 toxiproxy 是 11 章故障注入才用
if tc qdisc add dev lo root netem delay 1ms 2>/dev/null; then
  tc qdisc del dev lo root 2>/dev/null || true
  echo "OK   netem(tc + sch_netem 可用)"
else
  echo "WARN netem 不可用:试 sudo modprobe sch_netem,或装 linux-modules-extra-\$(uname -r)"
fi
if command -v toxiproxy-server >/dev/null 2>&1; then
  echo "OK   toxiproxy-server"
else
  echo "WARN toxiproxy 未装(11 慢依赖场景要用),手动装法见 11-fault-injection-lab/README.md"
fi

echo
if [[ "$MISS" -eq 0 ]]; then
  echo "✅ 核心工具就绪。内核:$(uname -r)"
else
  echo "⚠️  有核心工具缺失,检查上面的 MISS 项。" >&2
  exit 1
fi
