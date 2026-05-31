# 00 · lab 沙箱:在 Mac 上起一个真 Linux

> 这门课是「读练结合」。你需要一个**能反复折腾、弄坏了就重置**的真 Linux 环境。本章一次性把它搭好,后面每章的动手实验都在里面跑。

---

## 为什么是「真 VM」而不是 Docker

容器最轻,但**共享宿主机内核**——这门课后面几章恰恰要碰内核:

| 实验 | 容器里的问题 |
|------|-------------|
| `08` systemd 服务管理 | 容器默认不跑 systemd(PID 1 是你的进程) |
| `04` 改 swap / 看真实 OOM | swap 是宿主机全局的,容器改不了 |
| `03` 复现 `D`(不可中断睡眠) | 依赖真实块设备 I/O,容器里难造 |
| 改 `sysctl`(vm.*、部分 net.*) | 多数 host 全局参数容器改不了 |

所以**主环境用一个真 Ubuntu VM**。它跑真 systemd、能改 `sysctl`、能造 OOM/swap/`D` 状态——这才是你面试里描述的「一台真实 Linux 机器」。

> `09` 容器章会**单独用 Docker**,演示「容器只是受限的进程」(为什么容器里 `free` 看到宿主机内存)。到那一章再装,这里先不管。

---

## 工具:multipass(最低摩擦的真 VM)

[multipass](https://multipass.run/) 是 Canonical 出的「一条命令起一个 Ubuntu VM」工具,在 Mac 上体验最顺。也可换 [Lima](https://lima-vm.io/) / [Colima](https://github.com/abiosoft/colima),命令略不同,本课以 multipass 为准。

### 1. 安装(在你的 Mac 上,不是 VM 里)

```bash
brew install --cask multipass
multipass version          # 验证装好
```

### 2. 起一个 VM

```bash
# 名字 linux-lab,2 核 / 4G 内存 / 20G 磁盘,Ubuntu 24.04 LTS
multipass launch 24.04 --name linux-lab --cpus 2 --memory 4G --disk 20G

multipass list             # 看到 linux-lab 处于 Running
```

> 内存吃紧的话 `--memory 2G` 也够用;但做 `04` 内存章的 OOM 实验时,小内存反而更容易触发,挺好。

### 3. 进 VM

```bash
multipass shell linux-lab
# 现在你在 VM 里了,提示符变成 ubuntu@linux-lab:~$
```

之后每章「动手实验」默认就是在这个 shell 里敲命令。

### 4. 装工具箱(provision)

把本目录的 [`provision.sh`](./provision.sh) 推进去跑一次,装齐全课要用的排查工具:

```bash
# 在你的 Mac 上(注意是 Mac,不是 VM 里):
multipass transfer linux-handson/00-lab/provision.sh linux-lab:/tmp/provision.sh
multipass exec linux-lab -- sudo bash /tmp/provision.sh
```

> 也可以进 VM 后手动 `sudo apt update && sudo apt install -y <清单>`,清单见脚本。

### 5. 冒烟测试

进 VM 后跑一遍,确认工具都在、内核版本能看到:

```bash
uname -a                              # 内核版本、架构
cat /etc/os-release | head -2         # 发行版
for t in ps top htop vmstat iostat pidstat ss strace lsof tcpdump stress-ng dstat; do \
  command -v $t >/dev/null && echo "OK  $t" || echo "MISS $t"; done
```

全是 `OK` 就绪了。

---

## 日常操作速查

| 想做 | 命令(在 Mac 上跑) |
|------|------|
| 进 VM | `multipass shell linux-lab` |
| 不进 VM 直接跑一条命令 | `multipass exec linux-lab -- <cmd>` |
| 看 VM 状态 | `multipass list` / `multipass info linux-lab` |
| 暂停 / 启动 | `multipass stop linux-lab` / `multipass start linux-lab` |
| **弄坏了,推倒重来** | `multipass delete linux-lab && multipass purge && multipass launch ...` |
| 从 Mac 拷文件进去 | `multipass transfer <本地文件> linux-lab:<路径>` |

「弄坏了重来」是这门课鼓励的——大胆在 VM 里试危险命令(`kill -9 1`、填满磁盘、打爆 fd),坏了 30 秒重建一个。

---

## 工具箱清单(provision 会装这些)

| 工具 | 用途 | 主要在哪章用 |
|------|------|------|
| `procps`(ps/top/vmstat/free) | 进程、内存、负载基础观测 | 03 / 04 / 07 |
| `htop` | 交互式进程查看 | 03 / 07 |
| `sysstat`(iostat/pidstat/sar) | I/O 与每进程资源 | 05 / 07 |
| `strace` / `ltrace` | 跟踪系统调用 / 库调用 | 01 / 03 / 07 |
| `lsof` | 看进程打开的文件与 fd | 05 / 06 / 07 |
| `iproute2`(ss/ip) | socket 与网络状态 | 06 / 07 |
| `tcpdump` | 抓包 | 06 |
| `net-tools`(netstat 等) | 旧式网络工具(对照学) | 06 |
| `stress-ng` | 制造 CPU/内存/IO 压力(造现象) | 04 / 05 / 07 |
| `dstat` | 一屏看 CPU/磁盘/网络 | 07 |
| `dnsutils`(dig/nslookup) | DNS 解析排查 | 06 |

---

## 每章环境标注约定

从 `01` 起,每章「动手实验」开头会标注所需环境,例如:

> 🧪 **环境**:VM shell(`multipass shell linux-lab`)
> 🧪 **环境**:VM,需 `sudo`
> 🧪 **环境**:Docker(`09` 章,演示容器视角)

照着标注准备即可。

---

✅ 沙箱就绪后,去 [**01 · 世界观 + shell 原理**](../01-mental-model-and-shell/) 开始正式学习。
