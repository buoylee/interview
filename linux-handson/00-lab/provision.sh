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
  strace        # 跟踪系统调用
  ltrace        # 跟踪库调用
  lsof          # 进程打开的文件与 fd
  iproute2      # ss / ip(现代网络工具)
  net-tools     # netstat / ifconfig(旧式,对照学)
  tcpdump       # 抓包
  stress-ng     # 制造 CPU/内存/IO 压力,用来"造现象"
  dstat         # 一屏看 CPU/磁盘/网络
  dnsutils      # dig / nslookup
  file          # 看文件类型
  tree          # 看目录树
  vim           # 编辑器
  curl          # HTTP 排查
  netcat-openbsd # nc,连通性排查
)

echo ">>> apt update"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq

echo ">>> 安装工具箱:${PKGS[*]}"
apt-get install -y -qq "${PKGS[@]}"

echo
echo ">>> 冒烟测试"
MISS=0
for t in ps top htop vmstat iostat pidstat ss ip strace ltrace lsof tcpdump stress-ng dstat dig; do
  if command -v "$t" >/dev/null 2>&1; then
    printf "OK   %s\n" "$t"
  else
    printf "MISS %s\n" "$t"
    MISS=1
  fi
done

echo
if [[ "$MISS" -eq 0 ]]; then
  echo "✅ 全部就绪。内核:$(uname -r)"
else
  echo "⚠️  有工具缺失,检查上面的 MISS 项。" >&2
  exit 1
fi
