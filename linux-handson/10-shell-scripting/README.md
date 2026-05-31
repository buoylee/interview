# 10 · Shell 脚本 + 文本三件套

> 🧪 **环境**:VM shell(`multipass shell linux-lab`)
> 工具收尾章。把前面学的排查命令组合成**可复用、不坑人**的脚本,并掌握日志分析主力 `grep`/`sed`/`awk`。目标是「够用」——能写健壮的运维脚本、能从日志里捞出想要的东西,不追求成为 bash 专家。

---

## 一、开篇盲点

- 你的脚本是不是**出错了还继续往下跑**?是不是 `rm -rf "$DIR/"` 在 `$DIR` 恰好为空时变成了 `rm -rf /`?
- `cat f | while read line; do COUNT=$((COUNT+1)); done`——循环跑完 `COUNT` 还是 0,为什么?(`01` 埋的子 shell 伏笔)
- 分析日志你是不是只会 `grep` 关键字,统计 top IP / 状态码分布全靠肉眼数?

---

## 二、正文 · 原理

### 2.1 每个脚本开头都该有:`set -euo pipefail`

bash 的默认行为对运维很危险,这三个开关纠正它:

```bash
#!/usr/bin/env bash
set -euo pipefail
```

| 开关 | 作用 | 不开的危险 |
|------|------|-----------|
| `-e` | 命令出错(非 0 退出)立即终止脚本 | 出错继续往下跑,错上加错 |
| `-u` | 用未定义变量直接报错 | `rm -rf "$DIR/"` 里 `$DIR` 拼错/未设 → 删错地方 |
| `-o pipefail` | 管道里**任一环**失败,整条管道算失败 | `curl ... | grep` 中 curl 挂了也被判成功 |

### 2.2 变量与引号:90% 的脚本 bug 在这

- **永远给变量加引号**:`"$var"`。不加,值里有空格会被拆成多个参数、空值会消失。
- `"${VAR:?必须设置}"`:未设就报错退出(配合 `-u`,防灾)。
- `"${VAR:-默认值}"`:未设时用默认值。

```bash
DIR="${1:?用法: $0 <目录>}"     # 没传参数直接报错,不会误删
rm -rf "${DIR:?}"/*             # DIR 为空时 :? 会阻止,避免 rm -rf /*
```

### 2.3 条件、退出码、短路

- 每条命令都有**退出码** `$?`:0 成功,非 0 失败。
- `&&`(前者成功才执行后者)、`||`(前者失败才执行后者)。
- 测试用 `[[ ... ]]`(bash 增强版,比老 `[ ]` 安全):`[[ -f $f ]]`(文件存在)、`[[ $a == foo* ]]`(模式匹配)、`[[ $n -gt 10 ]]`。

### 2.4 循环 + 那个经典坑(接 01 子 shell)

```bash
# ❌ 坑:管道右侧在子 shell 里跑,COUNT 改在子进程,循环外读不到
COUNT=0
cat access.log | while read -r line; do COUNT=$((COUNT+1)); done
echo "$COUNT"        # 还是 0!

# ✅ 解法:用进程替换 < <(...) 或重定向 < file,循环在当前 shell 跑
COUNT=0
while read -r line; do COUNT=$((COUNT+1)); done < <(cat access.log)
echo "$COUNT"        # 正确
```

回顾 `01`:管道 `a | b` 的两端是**两个独立进程**,右侧的 `while` 在子 shell,变量改动不影响父 shell。

### 2.5 函数 + `trap`(接 03 信号)

`trap` 注册信号/退出时的处理函数——脚本版的「优雅关闭」:

```bash
cleanup() { rm -f "$TMPFILE"; echo "已清理"; }
trap cleanup EXIT          # 脚本无论怎么退出都执行清理
trap 'echo "被中断"; exit 130' INT TERM   # 捕获 Ctrl-C / SIGTERM(接 03)
```

### 2.6 文本三件套(够用就好)

| 工具 | 擅长 | 常用 |
|------|------|------|
| **grep** | 找行 | `-E` 正则、`-i` 忽略大小写、`-v` 取反、`-c` 计数、`-r` 递归、`-A/-B/-C N` 上下文 |
| **sed** | 改行 | `s/old/new/g` 替换、`-i` 原地改、`/pat/d` 删行、`-n '5,10p'` 打印指定行 |
| **awk** | **按列处理 + 统计**(日志分析主力) | `-F: '{print $1}'` 按分隔取列、`$NF` 最后一列、`{sum+=$1} END{print sum}` 求和 |

### 2.7 排查常用 one-liner(组合拳)

「排序 + 去重计数 + 倒序 + 取头部」是日志统计的万能套路:

```bash
# access.log 里访问量 top 10 的 IP(假设 IP 在第 1 列)
awk '{print $1}' access.log | sort | uniq -c | sort -rn | head

# 各 HTTP 状态码的分布(假设状态码在第 9 列)
awk '{print $9}' access.log | sort | uniq -c | sort -rn

# 平均响应时间(假设耗时在最后一列)
awk '{sum+=$NF; n++} END{printf "avg=%.3f, n=%d\n", sum/n, n}' access.log
```

---

## 三、动手实验(沙箱)

> 🧪 在 `multipass shell linux-lab` 里跑。

**实验 1:`set -e` 救命**
```bash
bash -c 'cd /nonexistent; rm -rf *'                 # 没 set -e:cd 失败仍执行 rm(在原目录!)
bash -c 'set -e; cd /nonexistent; rm -rf *'         # set -e:cd 失败立即停,rm 不执行
echo "对比两者:第一个危险,第二个安全"
```

**实验 2:子 shell 变量丢失 + 修复(接 01)**
```bash
printf 'a\nb\nc\n' > /tmp/lines
echo "== 坑:管道 while =="; N=0; cat /tmp/lines | while read -r x; do N=$((N+1)); done; echo "N=$N"
echo "== 修:进程替换 =="; N=0; while read -r x; do N=$((N+1)); done < <(cat /tmp/lines); echo "N=$N"
rm -f /tmp/lines
```

**实验 3:awk 分析「访问日志」**
```bash
# 造一个迷你 access log:IP 状态码 耗时
cat > /tmp/access.log <<'EOF'
1.1.1.1 200 0.012
2.2.2.2 500 0.300
1.1.1.1 200 0.020
1.1.1.1 404 0.005
2.2.2.2 200 0.150
EOF
echo "== top IP =="; awk '{print $1}' /tmp/access.log | sort | uniq -c | sort -rn
echo "== 状态码分布 =="; awk '{print $2}' /tmp/access.log | sort | uniq -c | sort -rn
echo "== 平均耗时 =="; awk '{s+=$3;n++} END{printf "%.3f (%d 条)\n", s/n, n}' /tmp/access.log
rm -f /tmp/access.log
```

**实验 4:跑本章配套的一键排查脚本**
```bash
bash /path/to/linux-handson/10-shell-scripting/quick-diag.sh
# 它把 07 的"第一分钟体检"固化成一个脚本(见本目录 quick-diag.sh)
```

---

## 四、生产踩坑框 ⚠️

> **`rm -rf "$DIR/"` 灾难**:`$DIR` 未设或为空时,`set -u` + `"${DIR:?}"` 能在执行前拦下;否则可能 `rm -rf /`。涉及删除的脚本务必加这两道保险。

> **CI/cron 里脚本「静默失败」**:没 `set -e` 时,中间步骤失败但脚本返回 0,CI 显示绿、问题流到生产。所有自动化脚本第一行就该 `set -euo pipefail`。

> **变量不加引号**:`cp $src $dst`,`$src` 含空格就崩;路径、文件名一律 `"$var"`。

> **文本处理别堆砌**:`grep | cut | sed | grep` 一长串难维护,很多时候一个 `awk` 就搞定且更清晰。

---

## 五、本章面试速记

- **`set -euo pipefail` 各是什么?** `-e` 出错即停、`-u` 未定义变量报错、`-o pipefail` 管道任一环失败即失败。
- **`cmd | while read` 改的变量为什么丢?怎么解?** 管道右侧在子 shell(独立进程),变量改动不回传;用 `while ... done < <(cmd)` 进程替换或 `< file`。
- **grep / sed / awk 各擅长什么?** grep 找行、sed 改行、awk 按列处理与统计。
- **怎么从日志统计 top N IP?** `awk '{print $1}' | sort | uniq -c | sort -rn | head`。
- **`trap` 干嘛?** 注册信号/退出处理(接 `03`),做清理或脚本级优雅关闭。

---

## 六、小结 + 桥接 + 全课收尾

**一句话记忆点**:
> 脚本第一行 `set -euo pipefail`,变量永远加引号、删除用 `"${DIR:?}"` 保险;管道 `while` 在子 shell 会丢变量(用 `< <()`);`trap` 做收尾;日志统计=`awk 取列 | sort | uniq -c | sort -rn`。

**桥接**:Dockerfile 的 `RUN`、容器 `entrypoint.sh`(接 `09`,常在这里 `exec "$@"` 做 PID 1 信号转发)、CI/CD 流水线、systemd 的 `ExecStartPre`(接 `08`)——全是 shell。一个写好 `trap`/`set -e` 的 entrypoint,正是 `09` 优雅关闭的落地。

---

### 🎓 全课收尾:你现在掌握的主线

```
01 命令的本质(syscall/fd/fork+exec)
02 文件系统 + 权限(一切皆文件的组织与访问)
        │
   内核作为资源管理者,每种资源一章:
03 进程  ──┐
04 内存  ──┤
05 I/O   ──┼──►  07 排查方法论(把四资源串成系统化排查)
06 网络  ──┘
        │
08 systemd(让服务开机自启/自愈/限资源)
09 容器(namespace+cgroup+overlayfs = 受限的进程)
10 shell(把排查固化成脚本)
99 面试卡(速答表 + 深题卡,随章积累)
```

面对一台真实 Linux 机器的常见问题(CPU 100%、内存涨/OOM、磁盘满、fd 耗尽、连接爆、僵尸、服务起不来、容器 OOMKilled),你现在能**理解原理 → 用工具定位 → 讲清排查链路**——这正是当初定的「够用且能答」。

**接下来怎么用**:
- 按 `00-lab` 把沙箱搭起来,**每章动手实验亲手跑一遍**(读不等于会)。
- 用 `99-interview-cards` 自测,重点练深题卡的「追问预案」。
- 想再深入性能/SRE,顺各章末尾的指针进 [`performance-tuning-roadmap/`](../../performance-tuning-roadmap/)。

**延伸指针**:
- 更多排查脚本与实验 → `performance-tuning-roadmap/labs/`
- 压测脚本 → `performance-tuning-roadmap/07-load-testing/`
