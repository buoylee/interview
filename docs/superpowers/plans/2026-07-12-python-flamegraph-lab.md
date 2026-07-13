# PerfShop Python Flame Graph Lab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a runnable, opt-in `py-spy` lab that profiles PerfShop's existing Python CPU hotspot, records hotspot/reset flame graphs, and guides learners through QPS/P99 and top-three-hotspot comparison.

**Architecture:** Install a pinned `py-spy` binary in the existing App image, while granting `SYS_PTRACE` and mounting the output directory only through a separate Compose override. Keep application behavior unchanged. Put the complete two-terminal exercise in one focused lab document and add discoverable links from the PerfShop and Python profiling guides.

**Tech Stack:** Docker Compose, Python 3.12 slim, `py-spy==0.4.2`, `wrk`, Markdown, SVG flame graphs

## Global Constraints

- Implementation scope is `performance-tuning-roadmap/labs/perfshop-p0` plus one cross-link in `performance-tuning-roadmap/06a-python-profiling/01-python-profiling-tools.md`.
- Pin profiler exactly as `py-spy==0.4.2`.
- Keep `performance-tuning-roadmap/labs/perfshop-p0/docker-compose.yml` unchanged.
- Grant only `SYS_PTRACE`; never add `privileged` or `seccomp=unconfined`.
- Keep `performance-tuning-roadmap/labs/perfshop-p0/app/src/server.py` unchanged.
- Generate `cpu-hotspot.svg` and `cpu-reset.svg` locally; never commit generated SVG files.
- Describe the comparison as hotspot on/reset diagnostic validation, not a code optimization.
- Do not add helper scripts, profiler sidecars, multi-stage profiler images, Java/Go changes, or bundled FlameGraph Perl scripts.
- Match the performance roadmap's existing Simplified Chinese prose; keep commands and technical names in English.
- Treat `performance-tuning-roadmap/labs/perfshop-p0` as the working directory for every command in the learner guide.

---

### Task 1: Add opt-in profiling infrastructure

**Files:**

- Modify: `performance-tuning-roadmap/labs/perfshop-p0/app/requirements.txt:1-2`
- Create: `performance-tuning-roadmap/labs/perfshop-p0/docker-compose.profiling.yml`
- Create: `performance-tuning-roadmap/labs/perfshop-p0/artifacts/profiling/.gitignore`

**Interfaces:**

- Consumes: existing Compose `app` service named `app`, container name `perfshop-p0-app`, Python process at container PID 1
- Produces: App image command `py-spy`, opt-in `SYS_PTRACE`, host output path `artifacts/profiling`, container output path `/artifacts/profiling`

- [ ] **Step 1: Verify the required infrastructure is absent**

Run from `performance-tuning-roadmap/labs/perfshop-p0`:

```bash
rg -n '^py-spy==0\.4\.2$' app/requirements.txt
```

Expected: exit 1 with no matches.

```bash
test -f docker-compose.profiling.yml
```

Expected: exit 1 because the override does not exist.

- [ ] **Step 2: Pin `py-spy` in the App image**

Append this exact line to `app/requirements.txt`:

```text
py-spy==0.4.2
```

Resulting file:

```text
mysql-connector-python==9.0.0
redis==7.4.0
py-spy==0.4.2
```

- [ ] **Step 3: Create the opt-in Compose override**

Create `docker-compose.profiling.yml` with this exact content:

```yaml
services:
  app:
    cap_add:
      - SYS_PTRACE
    volumes:
      - ./artifacts/profiling:/artifacts/profiling
```

- [ ] **Step 4: Keep generated artifacts out of Git**

Create `artifacts/profiling/.gitignore` with this exact content:

```gitignore
*
!.gitignore
```

- [ ] **Step 5: Validate the merged Compose model**

Run:

```bash
docker compose -f docker-compose.yml -f docker-compose.profiling.yml config
```

Expected: exit 0; rendered `app` service contains `SYS_PTRACE` and `/artifacts/profiling` mount. It must not contain `privileged: true`.

Run:

```bash
docker compose -f docker-compose.yml config
```

Expected: exit 0; rendered base `app` service contains neither `SYS_PTRACE` nor `/artifacts/profiling`.

- [ ] **Step 6: Build and smoke-test the profiler image**

Run:

```bash
docker compose -f docker-compose.yml -f docker-compose.profiling.yml up --build -d
```

Expected: MySQL, Redis, and downstream become healthy; App reaches running state after those dependencies are ready.

Run:

```bash
docker exec perfshop-p0-app py-spy --version
```

Expected:

```text
py-spy 0.4.2
```

Run:

```bash
curl http://127.0.0.1:8080/health
```

Expected: HTTP 200 JSON health response.

Run:

```bash
curl http://127.0.0.1:8080/api/products/1
```

Expected: HTTP 200 product JSON.

Run:

```bash
curl http://127.0.0.1:8080/metrics
```

Expected: Prometheus text containing `http_requests_total`.

- [ ] **Step 7: Commit the profiling infrastructure**

```bash
git add performance-tuning-roadmap/labs/perfshop-p0/app/requirements.txt performance-tuning-roadmap/labs/perfshop-p0/docker-compose.profiling.yml performance-tuning-roadmap/labs/perfshop-p0/artifacts/profiling/.gitignore
git commit -m "build(perfshop): add opt-in Python profiler"
```

---

### Task 2: Write the runnable Python flame graph guide

**Files:**

- Create: `performance-tuning-roadmap/labs/perfshop-p0/PYTHON-FLAMEGRAPH-LAB.md`

**Interfaces:**

- Consumes: `py-spy 0.4.2`, `docker-compose.profiling.yml`, `/chaos/cpu`, `/chaos/reset`, `/api/products/1`, host `wrk`
- Produces: learner workflow for `artifacts/profiling/cpu-hotspot.svg`, `artifacts/profiling/cpu-reset.svg`, QPS/P99 comparison, top-three-hotspot notes

- [ ] **Step 1: Verify the guide does not exist**

Run from the repository root:

```bash
test -f performance-tuning-roadmap/labs/perfshop-p0/PYTHON-FLAMEGRAPH-LAB.md
```

Expected: exit 1.

- [ ] **Step 2: Create the complete guide**

Create `performance-tuning-roadmap/labs/perfshop-p0/PYTHON-FLAMEGRAPH-LAB.md` with this content:

````markdown
# Python `py-spy` 火焰图实验

> 目标：在同一个 PerfShop Python 服务上制造 CPU hotspot，用 `py-spy` 生成 hotspot/reset 两张火焰图，并用相同负载比较 QPS、P99 与 top 3 热点。

本实验是**故障 on/off 的诊断验证**。Reset 只是关闭故障注入，不代表完成了真实代码优化。

## 1. 前置条件

- Docker 与 Docker Compose
- `curl`
- host 已安装 `wrk`
- 当前目录为 `performance-tuning-roadmap/labs/perfshop-p0`

确认 `wrk`：

```bash
wrk --version
```

`py-spy` 会读取目标进程内存。实验通过独立 Compose override 仅为 App 增加 `SYS_PTRACE`；不要改成 `privileged`，不要把这份 override 用于生产环境。

## 2. 启动 profiling 环境

```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.profiling.yml \
  up --build -d
```

检查 App 与 profiler：

```bash
curl http://127.0.0.1:8080/health
docker exec perfshop-p0-app py-spy --version
```

预期版本：

```text
py-spy 0.4.2
```

## 3. 第一轮：CPU hotspot

### 3.1 开启故障

90 秒窗口为切换两个 Terminal 留出余量：

```bash
curl -X POST 'http://127.0.0.1:8080/chaos/cpu?duration=90'
```

预期响应包含：

```json
{"cpu_hotspot_enabled_seconds": 90}
```

### 3.2 Terminal A：执行固定负载

```bash
wrk --latency -t2 -c20 -d30s http://127.0.0.1:8080/api/products/1
```

记录输出中的 `Requests/sec` 与 99% latency。

### 3.3 Terminal B：同时采样 30 秒

Terminal A 开始后立即执行：

```bash
docker exec perfshop-p0-app py-spy record \
  --pid 1 \
  --duration 30 \
  --rate 100 \
  --format flamegraph \
  -o /artifacts/profiling/cpu-hotspot.svg
```

检查产物：

```bash
test -s artifacts/profiling/cpu-hotspot.svg
rg -n 'burn_cpu_if_enabled' artifacts/profiling/cpu-hotspot.svg
```

预期：SVG 非空，并包含 `burn_cpu_if_enabled`。

## 4. 第二轮：CPU reset

先关闭所有 chaos：

```bash
curl -X POST http://127.0.0.1:8080/chaos/reset
```

预期响应包含：

```json
{"status": "reset"}
```

Terminal A 使用**完全相同**的负载：

```bash
wrk --latency -t2 -c20 -d30s http://127.0.0.1:8080/api/products/1
```

Terminal B 同时采样，只有输出文件名不同：

```bash
docker exec perfshop-p0-app py-spy record \
  --pid 1 \
  --duration 30 \
  --rate 100 \
  --format flamegraph \
  -o /artifacts/profiling/cpu-reset.svg
```

检查产物：

```bash
test -s artifacts/profiling/cpu-reset.svg
```

`burn_cpu_if_enabled` 仍可能因为快速 guard return 出现在 reset 样本中；正确预期是 frame 明显缩窄，不是必须完全消失。

## 5. 阅读与比较

- X 轴宽度：函数出现在样本中的比例，不是时间轴。
- Y 轴：调用栈深度。
- 顶部宽 frame：直接消耗 CPU 的热点。
- 搜索 `burn_cpu_if_enabled`，沿下方 frame 还原调用路径。

填写结果：

| 轮次 | QPS | P99 | top 1 | top 2 | top 3 |
|---|---:|---:|---|---|---|
| CPU hotspot |  |  |  |  |  |
| CPU reset |  |  |  |  |  |

回答：

1. 哪条 stack path 直接支持 CPU hotspot 假设？
2. Reset 后，`burn_cpu_if_enabled` frame、QPS、P99 如何变化？
3. 这组证据能证明什么？不能证明什么？

预期结论：hotspot 图中 `burn_cpu_if_enabled` 与 busy loop 占据明显宽度；reset 后该路径缩窄，QPS 上升、P99 下降。具体数值依硬件而异，不设固定通过门槛。

## 6. 常见问题

### `Permission denied`

确认启动时同时使用两份 Compose file，并 recreate App：

```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.profiling.yml \
  up -d --force-recreate app
```

不要用 `privileged` 绕过问题。

### PID 或 executable 错误

确认 App 正常，target 使用 container 内 PID 1：

```bash
curl http://127.0.0.1:8080/health
docker exec perfshop-p0-app py-spy dump --pid 1
```

### SVG 没有预期 hotspot

确认：

- chaos API 返回成功；
- 90 秒窗口尚未结束；
- `wrk` 与 `py-spy record` 同时运行；
- 压测 endpoint 是 `GET /api/products/1`。

### 两轮数据不可比

两轮必须保持相同 endpoint、threads、connections、duration、sample rate 与测试环境。不要一轮执行其他高负载任务。

## 7. 清理

停止本实验启动的服务：

```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.profiling.yml \
  down
```

SVG 保留在：

```text
artifacts/profiling/cpu-hotspot.svg
artifacts/profiling/cpu-reset.svg
```

这些文件已被 Git ignore，不应提交。
````

- [ ] **Step 3: Run static guide checks**

Run from the repository root:

```bash
rg -n 'py-spy 0\.4\.2|SYS_PTRACE|cpu-hotspot\.svg|cpu-reset\.svg|burn_cpu_if_enabled|不是必须完全消失|不要用 `privileged`' performance-tuning-roadmap/labs/perfshop-p0/PYTHON-FLAMEGRAPH-LAB.md
```

Expected: every required concept has at least one match.

Run:

```bash
rg -n '真实代码优化|故障 on/off 的诊断验证' performance-tuning-roadmap/labs/perfshop-p0/PYTHON-FLAMEGRAPH-LAB.md
```

Expected: both boundary statements appear in the introduction.

- [ ] **Step 4: Commit the guide**

```bash
git add performance-tuning-roadmap/labs/perfshop-p0/PYTHON-FLAMEGRAPH-LAB.md
git commit -m "docs(perfshop): add Python flame graph lab"
```

---

### Task 3: Link the runnable lab from existing learning paths

**Files:**

- Modify: `performance-tuning-roadmap/labs/perfshop-p0/README.md:169-189`
- Modify: `performance-tuning-roadmap/06a-python-profiling/01-python-profiling-tools.md:210-221`

**Interfaces:**

- Consumes: committed `performance-tuning-roadmap/labs/perfshop-p0/PYTHON-FLAMEGRAPH-LAB.md`
- Produces: relative links from the PerfShop CPU hotspot scenario and Python `py-spy` tutorial

- [ ] **Step 1: Verify no runnable-lab links exist**

Run from the repository root:

```bash
rg -n 'PYTHON-FLAMEGRAPH-LAB\.md' performance-tuning-roadmap/labs/perfshop-p0/README.md performance-tuning-roadmap/06a-python-profiling/01-python-profiling-tools.md
```

Expected: exit 1 with no matches.

- [ ] **Step 2: Update the PerfShop CPU hotspot scenario**

In `performance-tuning-roadmap/labs/perfshop-p0/README.md`, replace:

```markdown
- 优化前后 QPS / P99
```

with:

```markdown
- CPU hotspot on / reset 后的 QPS / P99

可运行步骤见：[Python `py-spy` 火焰图实验](./PYTHON-FLAMEGRAPH-LAB.md)。该实验使用现有 CPU hotspot 完成双份 SVG、top 3 热点与 QPS/P99 对比。
```

This removes the false implication that reset is a code optimization.

- [ ] **Step 3: Link the lab from the Python profiling tutorial**

In `performance-tuning-roadmap/06a-python-profiling/01-python-profiling-tools.md`, insert immediately after the paragraph ending with “低效的序列化。” and before `## 小结`:

```markdown

> **可运行实验**：使用 PerfShop 的 CPU hotspot 完成 `py-spy` attach、hotspot/reset 双火焰图和 QPS/P99 对比，见 [Python `py-spy` 火焰图实验](../labs/perfshop-p0/PYTHON-FLAMEGRAPH-LAB.md)。
```

- [ ] **Step 4: Validate both relative links**

Run:

```bash
rg -n 'PYTHON-FLAMEGRAPH-LAB\.md' performance-tuning-roadmap/labs/perfshop-p0/README.md performance-tuning-roadmap/06a-python-profiling/01-python-profiling-tools.md
```

Expected: exactly two matches, one in each source document.

Run:

```bash
test -f performance-tuning-roadmap/labs/perfshop-p0/PYTHON-FLAMEGRAPH-LAB.md
```

Expected: exit 0.

- [ ] **Step 5: Commit the learning-path links**

```bash
git add performance-tuning-roadmap/labs/perfshop-p0/README.md performance-tuning-roadmap/06a-python-profiling/01-python-profiling-tools.md
git commit -m "docs(profiling): link runnable Python lab"
```

---

### Task 4: Run full acceptance verification

**Files:**

- Verify: `performance-tuning-roadmap/labs/perfshop-p0/docker-compose.profiling.yml`
- Verify: `performance-tuning-roadmap/labs/perfshop-p0/PYTHON-FLAMEGRAPH-LAB.md`
- Generated and ignored: `performance-tuning-roadmap/labs/perfshop-p0/artifacts/profiling/cpu-hotspot.svg`
- Generated and ignored: `performance-tuning-roadmap/labs/perfshop-p0/artifacts/profiling/cpu-reset.svg`

**Interfaces:**

- Consumes: all outputs from Tasks 1-3
- Produces: evidence that the documented workflow runs end-to-end without changing App behavior or tracking generated artifacts

- [ ] **Step 1: Confirm Docker configuration and base-permission isolation**

Run from `performance-tuning-roadmap/labs/perfshop-p0`:

```bash
docker compose -f docker-compose.yml -f docker-compose.profiling.yml config
```

Expected: exit 0; merged App has `SYS_PTRACE` and artifact mount.

Run:

```bash
docker compose -f docker-compose.yml config
```

Expected: exit 0; base App has neither profiling setting.

- [ ] **Step 2: Start a clean profiling environment**

Run:

```bash
docker compose -f docker-compose.yml -f docker-compose.profiling.yml up --build -d --force-recreate
```

Expected: MySQL, Redis, and downstream reach healthy state; App, Prometheus, and Grafana reach running state.

Run:

```bash
docker exec perfshop-p0-app py-spy --version
```

Expected: `py-spy 0.4.2`.

- [ ] **Step 3: Verify existing App behavior**

Run each command and require HTTP success:

```bash
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8080/api/products/1
curl http://127.0.0.1:8080/metrics
```

Expected: health JSON, product JSON, and Prometheus text respectively.

- [ ] **Step 4: Capture the hotspot profile under load**

Enable the hotspot:

```bash
curl -X POST 'http://127.0.0.1:8080/chaos/cpu?duration=90'
```

Start this in execution session A:

```bash
wrk --latency -t2 -c20 -d30s http://127.0.0.1:8080/api/products/1
```

Immediately run this in execution session B:

```bash
docker exec perfshop-p0-app py-spy record --pid 1 --duration 30 --rate 100 --format flamegraph -o /artifacts/profiling/cpu-hotspot.svg
```

Expected: both commands exit 0; preserve `wrk` output for QPS/P99 review.

- [ ] **Step 5: Validate hotspot evidence**

Run:

```bash
test -s artifacts/profiling/cpu-hotspot.svg
```

Expected: exit 0.

Run:

```bash
rg -n 'burn_cpu_if_enabled' artifacts/profiling/cpu-hotspot.svg
```

Expected: at least one match.

- [ ] **Step 6: Capture the reset profile under identical load**

Reset chaos:

```bash
curl -X POST http://127.0.0.1:8080/chaos/reset
```

Start the same command in execution session A:

```bash
wrk --latency -t2 -c20 -d30s http://127.0.0.1:8080/api/products/1
```

Immediately run this in execution session B:

```bash
docker exec perfshop-p0-app py-spy record --pid 1 --duration 30 --rate 100 --format flamegraph -o /artifacts/profiling/cpu-reset.svg
```

Expected: both commands exit 0; preserve the second `wrk` output.

- [ ] **Step 7: Validate reset evidence and perform visual comparison**

Run:

```bash
test -s artifacts/profiling/cpu-reset.svg
```

Expected: exit 0.

Open both SVG files and confirm manually:

- `burn_cpu_if_enabled` is a wide hotspot path in `cpu-hotspot.svg`.
- The same path is absent or visibly narrower in `cpu-reset.svg`.
- Hotspot QPS is lower and P99 higher than reset under the same parameters. Do not enforce hardware-specific numeric thresholds.

- [ ] **Step 8: Verify generated artifacts remain untracked**

Run from the repository root:

```bash
git status --short -- performance-tuning-roadmap/labs/perfshop-p0/artifacts/profiling
```

Expected: no output.

Run:

```bash
git diff --check
```

Expected: exit 0 with no whitespace errors.

- [ ] **Step 9: Stop the lab environment**

Run from `performance-tuning-roadmap/labs/perfshop-p0`:

```bash
docker compose -f docker-compose.yml -f docker-compose.profiling.yml down
```

Expected: profiling App and dependency containers stop cleanly. Leave ignored SVG files in place as local learner artifacts.

- [ ] **Step 10: Review final commit set**

Run from the repository root:

```bash
git log -3 --oneline
```

Expected three focused implementation commits:

```text
docs(profiling): link runnable Python lab
docs(perfshop): add Python flame graph lab
build(perfshop): add opt-in Python profiler
```

No new commit is required for Task 4 because it produces only ignored local verification artifacts.
