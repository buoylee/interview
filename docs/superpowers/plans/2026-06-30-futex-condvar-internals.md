# Futex Condvar Internals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand `linux/04-concurrency-primitives/README.md` so futex and condition-variable internals explain queues, wakeups, lost-wakeup prevention, and Java Monitor/AQS mapping clearly.

**Architecture:** Keep `linux/04` as the OS primitive explanation. Add bounded kernel-level concepts (`futex key`, hash bucket, waiter queue, requeue) without source call chains. Link outward to Java and CLI notes instead of duplicating their deep dives.

**Tech Stack:** Markdown documentation, Linux futex concepts, POSIX condition-variable semantics, Java Monitor/AQS terminology.

---

## File Structure

- Modify: `linux/04-concurrency-primitives/README.md`
  - Expand `原语二：锁底层（futex）` under `② 黑盒内部`.
  - Expand `原语四：条件变量 / 唤醒（condition variable）` under `② 黑盒内部`.
  - Update back-links/cross-links in the same sections.
- Read-only reference: `docs/superpowers/specs/2026-06-30-futex-condvar-internals-design.md`
- Read-only reference: `java/concurrent/synchronized.md`
- Read-only reference: `java/concurrent/AQS.md`
- Read-only reference: `cli-toolbox/01-process-and-job-control.md`

Execution note: the working tree may already contain unrelated changes. Stage and commit only `linux/04-concurrency-primitives/README.md` when following this plan.

---

### Task 1: Expand Futex Wait-Queue Internals

**Files:**
- Modify: `linux/04-concurrency-primitives/README.md:78-98`

- [ ] **Step 1: Re-read the current futex section**

Run:

```bash
sed -n '60,105p' linux/04-concurrency-primitives/README.md
```

Expected: output shows `## 原语二：锁底层（futex）`, the two-layer CAS/syscall explanation, pseudocode, and `**架构取舍**`.

- [ ] **Step 2: Insert the futex internal queue explanation**

Edit `linux/04-concurrency-primitives/README.md` after the pseudocode block ending with `futex(FUTEX_WAKE)  ← 唤醒等待者` and before `**架构取舍**`.

Insert exactly this Markdown:

```markdown

**内核里到底排在哪里：futex key → hash bucket → waiter queue**

futex 不是「先创建一个内核锁对象，再让线程去抢」。用户态能看到的主体仍然只是一个整数地址 `uaddr`，例如 `lock_word`。内核只在 `futex(...)` syscall 发生时短暂介入：

```text
用户态 lock_word 地址 uaddr
  └─ futex(FUTEX_WAIT / FUTEX_WAKE, uaddr, ...)
       └─ 内核根据 uaddr 算出 futex key
            └─ key hash 到某个 bucket
                 └─ bucket 里挂着睡在这个 key 上的 waiter 队列
```

- **private futex**：只在同一进程内使用，key 大致由「当前进程的地址空间 + `uaddr`」标识。
- **shared futex**：跨进程共享内存使用，key 必须能指向同一个共享映射背后的对象，否则两个进程看见的虚拟地址可能不同。
- **waiter**：睡眠线程会作为一个等待节点挂进对应 bucket 的队列；它不在 run queue 上抢 CPU。
- **wake**：`FUTEX_WAKE(uaddr, n)` 用同一个 key 找到 bucket，取出最多 `n` 个 waiter，把它们唤醒为「可运行候选」。被唤醒不等于已经拿到锁；醒来的线程还要回用户态重新 CAS 竞争 `lock_word`。

**为什么 `FUTEX_WAIT` 必须带 expected value**

`FUTEX_WAIT(uaddr, expected)` 进内核后第一件事不是睡，而是重新检查：

```text
if (*uaddr != expected):
    return EAGAIN   # 值已经变了，不睡
else:
    enqueue waiter and sleep
```

这个检查是防 **lost wakeup（错过唤醒）** 的关键。否则会出现这样的竞态：

```text
T2: CAS(lock_word, 0, 1) 失败，准备睡眠
T1: unlock，把 lock_word 改成 0，并 futex_wake(addr)
T2: 如果不检查 expected，可能在 wake 已经发生后才睡进去，然后再也没人叫醒它
```

有 expected 检查后，T2 进入内核时会看到 `lock_word != 1`，直接返回用户态重试 CAS，而不是睡过头。
```

- [ ] **Step 3: Read the expanded futex section**

Run:

```bash
sed -n '68,135p' linux/04-concurrency-primitives/README.md
```

Expected: output contains `futex key → hash bucket → waiter queue`, `FUTEX_WAIT(uaddr, expected)`, and `lost wakeup`.

- [ ] **Step 4: Commit Task 1**

Run:

```bash
git diff --check -- linux/04-concurrency-primitives/README.md
git add linux/04-concurrency-primitives/README.md
git commit -m "docs(linux/04): explain futex wait queues"
```

Expected: `git diff --check` exits 0; commit includes only `linux/04-concurrency-primitives/README.md`.

---

### Task 2: Expand Condition Variable Queue and Requeue Semantics

**Files:**
- Modify: `linux/04-concurrency-primitives/README.md:204-209`

- [ ] **Step 1: Re-read the current condition-variable section**

Run:

```bash
sed -n '196,240p' linux/04-concurrency-primitives/README.md
```

Expected: output shows `**条件变量底层 = futex 等待队列。**`, the three-item `wait/signal/broadcast` list, the `while` example, spurious wakeup, and thundering herd.

- [ ] **Step 2: Replace the short condition-variable internals block**

In `linux/04-concurrency-primitives/README.md`, replace the block from:

```markdown
**条件变量底层 = futex 等待队列。**

条件变量的语义：
1. `wait`：原子地「释放持有的互斥锁 + 把自己睡在等待队列上」（两步必须原子，否则会错过唤醒）。内核实现为 `futex(FUTEX_WAIT_BITSET, ...)` 睡在条件变量内部计数器上，唤醒时用 `FUTEX_CMP_REQUEUE` 把等待者原子迁移到互斥锁的等待队列（这是非 PI 锁的标准路径；`FUTEX_WAIT_REQUEUE_PI` 是优先级继承锁才走的变体）。
2. `signal`：从等待队列唤醒一个线程，该线程被唤醒后需要重新竞争互斥锁才能继续。
3. `broadcast`（`notifyAll`）：唤醒所有等待线程，但同一时刻只有一个能拿到锁继续执行。
```

with exactly this Markdown:

```markdown
**条件变量底层不是「另一把锁」，而是「条件等待队列 + 互斥锁队列」的联动。**

条件变量要解决的问题不是保护临界区；保护临界区仍然靠 mutex。condition variable 负责表达「现在条件不满足，我先睡；等别人改变条件后再叫我回来检查」。

```text
mutex wait queue
  └─ 想进入临界区、但还没拿到 mutex 的线程

condition wait queue
  └─ 曾经拿到 mutex、发现谓词不成立、主动释放 mutex 后等待条件变化的线程
```

`wait()` 的完整语义是：

1. 调用者已经持有 mutex。
2. 调用者检查共享状态，发现谓词不成立，例如 `queue.isEmpty()`。
3. runtime/libc 把当前线程登记到 condition wait queue。
4. runtime/libc **原子地释放 mutex 并 park 当前线程**。这一步必须和入队绑定，否则会出现「刚释放锁，还没睡进去，signal 已经发完」的 lost wakeup。
5. 线程被 `signal/broadcast` 叫醒后，还不能直接继续执行；它必须重新竞争 mutex。
6. 重新拿到 mutex 后，再回到用户代码检查谓词。

`signal()` 的语义是：生产者在持有 mutex 时改变共享状态，然后通知一个 condition waiter。被通知者只是离开 condition wait queue，后面仍要重新抢 mutex，所以 signal 不等于「马上运行」。

`broadcast()`（Java `notifyAll` / Go `Broadcast`）会让所有 condition waiters 都离开条件等待，但同一时刻只有一个线程能拿到 mutex。其他线程即使醒了，也可能抢锁失败或发现条件又被消费掉，于是继续等待。这就是条件变量上的惊群成本。

**requeue 为什么存在**

POSIX/glibc 这类实现常用 futex 计数器表示 condition 的状态。为了减少 `broadcast` 把所有线程都叫醒后又一起抢同一把 mutex 的浪费，非 PI mutex 路径可以用 `FUTEX_CMP_REQUEUE`：把一部分 waiter 从 condition futex 的等待队列迁移到 mutex futex 的等待队列。这样语义仍然是「条件已通知，接下来排队抢 mutex」，但避免所有线程同时被调度醒来。`FUTEX_WAIT_REQUEUE_PI` 是优先级继承锁的变体，本章只需要知道它属于更特殊的 PI 路径。
```

- [ ] **Step 3: Read the expanded condition-variable section**

Run:

```bash
sed -n '196,270p' linux/04-concurrency-primitives/README.md
```

Expected: output contains `mutex wait queue`, `condition wait queue`, `原子地释放 mutex 并 park`, `signal 不等于「马上运行」`, and `FUTEX_CMP_REQUEUE`.

- [ ] **Step 4: Commit Task 2**

Run:

```bash
git diff --check -- linux/04-concurrency-primitives/README.md
git add linux/04-concurrency-primitives/README.md
git commit -m "docs(linux/04): explain condvar queues"
```

Expected: `git diff --check` exits 0; commit includes only `linux/04-concurrency-primitives/README.md`.

---

### Task 3: Add Java Bridge, Cross-Links, and Final Verification

**Files:**
- Modify: `linux/04-concurrency-primitives/README.md:127-129`
- Modify: `linux/04-concurrency-primitives/README.md:229-239`
- Modify: `linux/04-concurrency-primitives/README.md:298-310`

- [ ] **Step 1: Add the Java bridge callout**

In `linux/04-concurrency-primitives/README.md`, insert this callout after the requeue paragraph from Task 2 and before `**为什么必须用 \`while\` 而不是 \`if\` 检查条件**`:

```markdown

**Java 对照：Monitor / AQS 如何落到 park**

- `synchronized` + `Object.wait()/notify()` 是 JVM Monitor 语义。可以把它理解成：对象关联一个 Monitor，Monitor 里有竞争锁的入口队列，也有 `wait()` 进入的 WaitSet。
- `Object.wait()` 会释放 monitor，把当前 Java 线程放进 WaitSet 并 park；被 `notify/notifyAll` 选中后，它还要重新进入 monitor 的入口队列竞争锁，拿到锁后才从 `wait()` 返回。
- `ReentrantLock` / `Condition` 是 AQS 语义。AQS 有一个 sync queue 管锁竞争；每个 `ConditionObject` 又有自己的 condition queue。`await()` 进入 condition queue 并 `LockSupport.park()`；`signal()` 把节点转回 AQS sync queue；`unlock()` 后续再 `unpark` 合适的 successor。
- Linux 上，HotSpot park 一个平台线程时，最终会走 JVM/native parking 原语，底层通常由 pthread/futex 这类 OS 同步机制支撑。但 Java 代码层应该先用 Monitor/AQS 的队列语义思考，不要假设每次加锁都直接等于一次 futex syscall。

→ **Java 深挖**：`java/concurrent/synchronized.md`（Monitor / WaitSet）；`java/concurrent/AQS.md`（sync queue / condition queue / `LockSupport.park`）
```

- [ ] **Step 2: Update the futex back-link**

Replace the current futex back-link:

```markdown
→ **回链**：`linux-handson/03-process-model`（`/proc/<pid>/status` 看 `voluntary_ctxt_switches` 验证锁争用的上下文切换次数）
```

with:

```markdown
→ **回链**：`linux-handson/03-process-model`（`/proc/<pid>/status` 看 `voluntary_ctxt_switches` 验证锁争用的上下文切换次数）；`cli-toolbox/01-process-and-job-control.md`（用 `wchan=futex_wait` 判断线程是否睡在锁/条件变量上）
```

- [ ] **Step 3: Update the condition-variable back-link**

Replace the current condition-variable back-link:

```markdown
→ **回链**：`linux-handson/03-process-model`（生产者消费者模型实测）
```

with:

```markdown
→ **回链**：`linux-handson/03-process-model`（生产者消费者模型实测）；`java/concurrent/synchronized.md`（Java Monitor / WaitSet）；`java/concurrent/AQS.md`（ConditionObject 队列迁移）
```

- [ ] **Step 4: Verify required concepts are present**

Run:

```bash
rg -n "futex key|hash bucket|lost wakeup|mutex wait queue|condition wait queue|FUTEX_CMP_REQUEUE|Java 对照|ConditionObject|wchan=futex_wait" linux/04-concurrency-primitives/README.md
```

Expected: command exits 0 and prints matches for every listed concept.

- [ ] **Step 5: Check focused sections for narrative flow**

Run:

```bash
sed -n '68,150p' linux/04-concurrency-primitives/README.md
sed -n '196,295p' linux/04-concurrency-primitives/README.md
sed -n '292,314p' linux/04-concurrency-primitives/README.md
```

Expected:

- futex section reads in this order: CAS fast path, futex syscall, key/hash/waiter queue, expected-value lost-wakeup check, architecture tradeoff, evidence;
- condition section reads in this order: user view, condition/mutex queue distinction, wait/signal/broadcast flow, requeue note, Java bridge, `while` rule, spurious wakeup, thundering herd;
- summary still says futex feeds condition variables and remains consistent with the expanded explanation.

- [ ] **Step 6: Check for contradictions and whitespace issues**

Run:

```bash
rg -n "直接调用 futex|每次加锁.*futex|条件变量底层 = futex 等待队列|占位|待补|未完成" linux/04-concurrency-primitives/README.md
git diff --check -- linux/04-concurrency-primitives/README.md
```

Expected:

- `rg` may print no matches and exit 1, or only print intentional old wording if it was deliberately kept outside the replaced block;
- `git diff --check` exits 0.

- [ ] **Step 7: Commit Task 3**

Run:

```bash
git add linux/04-concurrency-primitives/README.md
git commit -m "docs(linux/04): bridge condvar internals to java"
```

Expected: commit includes only `linux/04-concurrency-primitives/README.md`.

---

## Final Verification

After all tasks:

- [ ] **Step 1: Confirm no unintended files were staged**

Run:

```bash
git status --short
```

Expected: unrelated pre-existing files may still appear modified/untracked, but `linux/04-concurrency-primitives/README.md` should be clean after the final commit.

- [ ] **Step 2: Review final commits**

Run:

```bash
git log --oneline -4 -- linux/04-concurrency-primitives/README.md
```

Expected: output includes the three task commits:

```text
docs(linux/04): bridge condvar internals to java
docs(linux/04): explain condvar queues
docs(linux/04): explain futex wait queues
```

- [ ] **Step 3: Report result**

Final response should mention:

- futex internals now include key/hash bucket/waiter queue and lost-wakeup prevention;
- condition-variable internals now distinguish condition queue from mutex queue and explain requeue;
- Java bridge now maps Monitor/AQS to park/unpark and OS-backed parking;
- verification commands run and any unrelated working-tree changes left untouched.
