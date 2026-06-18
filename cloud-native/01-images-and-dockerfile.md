# 第 1 章 · 镜像与容器:Dockerfile 最佳实践

> 🔬 容器「为什么是个被特殊安排的普通进程」,`linux-handson/09` 已经讲透(namespace/cgroup/overlayfs)。这章讲**应用层**——你天天写的 Dockerfile 怎么写对、镜像怎么瘦、怎么安全。面试问「你们镜像怎么优化的」「多阶段构建是干嘛的」「为什么不能用 latest」考的就是这。底层原理要复习就回 `linux-handson/09`,这里只讲「在它之上你该怎么做」。

---

## Part A · 镜像的本质:分层 + 写时复制(承接 linux/09)

```
镜像 = 一摞【只读层】叠起来(overlayfs)
容器 = 镜像 + 最上面一个【可写层】(写时复制 CoW)

Dockerfile:                         镜像层:
  FROM ubuntu          ──►  [层1: ubuntu 基础]      ← 只读,可被多镜像共享
  RUN apt install ...  ──►  [层2: 装的包]           ← 只读,可缓存
  COPY . /app          ──►  [层3: 你的代码]         ← 只读
  CMD ...                   [可写层]                ← 容器运行时才有
```

**一个事实推出全部最佳实践** 🔬:**每条指令 = 一层,层可缓存、可共享、有顺序。** 所以——把不变的放前面(利用缓存)、合并清理(减小层)、多阶段(丢掉构建层),全是从这一条推出来的。

---

## Part B · Dockerfile 最佳实践 🔬

### ① 善用层缓存:不变的放前面,常变的放后面
```dockerfile
# ❌ 错:代码一改,依赖每次重装
COPY . /app
RUN npm install

# ✅ 对:先拷依赖清单装依赖(不常变,命中缓存),再拷代码(常变)
COPY package.json package-lock.json /app/
RUN npm install            # ← 只要 package.json 没变,这层就走缓存
COPY . /app                # ← 改代码只重建这层及之后
```
> 原理:Docker 从上往下,**一层的输入没变就复用缓存**;一旦某层变了,**它和它之后所有层都要重建**。所以顺序 = 性能。

### ② 减少层 / 合并 RUN + 同层清理
```dockerfile
# ✅ && 串联,且在同一层清理缓存(分层后再删,删不掉前层的体积)
RUN apt-get update && apt-get install -y curl \
    && rm -rf /var/lib/apt/lists/*
```

### ③ 其他关键
- **`.dockerignore`**:别把 `.git` / `node_modules` / 日志塞进构建上下文(拖慢构建、撑大镜像)。
- **固定版本**:`FROM node:20.11`,**别用 `latest`**(不可复现,回扣 L6 可回滚)。
- **非 root 运行**:`USER appuser`(回扣 L7 最小权限——容器逃逸时少一层风险)。
- **PID1 信号**:用 `tini`/`--init` 当 PID1,否则 `docker stop` 要等满 10s 强杀(回扣 `linux-handson/09`)。

---

## Part C · 多阶段构建 multi-stage 🔬

**问题**:编译型语言(Go/Java/前端)构建需要**整套工具链**(几百 MB),但**运行根本不需要**。把工具链打进最终镜像 = 又大又多攻击面。

**解法**:分阶段——前一阶段编译,最后只**拷产物**到一个干净的瘦镜像:

```dockerfile
# 阶段1:build —— 用全套工具链编译
FROM golang:1.22 AS build
WORKDIR /src
COPY . .
RUN go build -o /app/server

# 阶段2:runtime —— 只要一个能跑的瘦底座
FROM gcr.io/distroless/static
COPY --from=build /app/server /server   # ← 只拷产物,工具链全丢掉
USER nonroot
ENTRYPOINT ["/server"]
```
> 效果:Go 服务最终镜像从 **800MB+ 降到几 MB**。镜像瘦身三件套:**多阶段 + 小底座(alpine/distroless/scratch)+ 同层清缓存**。

---

## Part D · 镜像安全与仓库

- **镜像安全清单**(回扣 L7):
  - 用**最小基础镜像**(distroless/alpine)→ 攻击面小、没 shell 更难被利用。
  - **非 root** 运行。
  - **扫描漏洞**(Trivy / Grype)接进 CI。
  - **别把密钥打进镜像**(镜像层是可扒的;用运行时注入 Secret,回扣 L7)。
- **镜像仓库 registry**:Docker Hub(公有)、**Harbor**(私有、**可自托管**——契合你「逃生票」偏好)、云厂商 registry。
- **标签策略** 🔬:**别用 `latest`**(指向会变、不可复现、回滚时不知道回到哪)。用**语义版本 + commit sha**(`v1.2.3` / `app:a1b2c3d`),保证「这个镜像永远是这堆字节」——回扣 L6 发布可回滚。

---

## debug 预告 + 交叉引用

- **镜像拉不到(ImagePullBackOff)/ 起来就崩** → 第 8 章排查 playbook
- **容器底层 / cgroup / overlayfs / PID1** → `linux-handson/09`(深挖)
- **非 root / 最小权限 / 不打密钥** → L7 `system-design/10-安全`
- **镜像 sha 不可变 → 可回滚** → L6 `system-design/09-发布`

---

## 本章小结

- **镜像 = 只读层叠加(overlayfs),容器 = 镜像 + 可写层**;每条指令一层、可缓存有顺序——这一条推出全部最佳实践。
- **Dockerfile**:不变的放前面(吃缓存)、合并 RUN 同层清理、`.dockerignore`、固定版本不用 latest、非 root、tini 当 PID1。
- **多阶段构建**:编译阶段用工具链,运行阶段只拷产物到瘦底座(distroless)→ 镜像从几百 MB 到几 MB。
- **安全**:最小底座 + 非 root + 扫描 + 别打密钥;仓库用可自托管的 Harbor;**标签用 sha/语义版本不用 latest**(可复现可回滚)。
- 下一章:`02` 从 docker-compose 到 k8s——**单机编排为什么不够,k8s 解决什么**。

---

## 章末问答(复习自检,答案要点都在前面正文)

1. 镜像和容器的关系是什么?用 overlayfs + 写时复制解释。
2. 为什么 Dockerfile 里「COPY 依赖清单 + 装依赖」要放在「COPY 全部代码」之前?
3. 为什么 `apt clean` 必须和 `apt install` 写在**同一个 RUN**里?
4. 多阶段构建解决什么问题?最终镜像为什么能小那么多?
5. distroless / alpine / scratch 各是什么?为什么对安全有帮助?
6. 为什么生产镜像标签不该用 `latest`?该用什么?(回扣可回滚)
7. 容器为什么建议用 tini/--init 当 PID1?不用会怎样?
8. **综合题**:「你们一个 Go 服务镜像 900MB、构建很慢、还被扫出漏洞,你怎么优化」——从多阶段、缓存顺序、瘦底座、非 root、扫描几方面答。
```
