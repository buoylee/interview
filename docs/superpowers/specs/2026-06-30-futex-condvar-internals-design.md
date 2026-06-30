# Futex and Condition Variable Internals Design

## Goal

Clarify the internals behind `linux/04-concurrency-primitives/README.md` sections "锁底层（futex）" and "条件变量 / 唤醒（condition variable）" without turning the chapter into a Linux kernel source-code walkthrough or a Java AQS chapter.

The reader should finish the update able to explain:

- why uncontended locks stay in user space;
- how a contended futex wait maps a user-space address to a kernel wait queue;
- why `FUTEX_WAIT` compares an expected value before sleeping;
- how `FUTEX_WAKE` moves waiters back toward runnable state;
- why a condition variable has a condition wait queue distinct from the mutex wait queue;
- how Java Monitor/AQS concepts correspond to the OS-level wait/park mechanism.

## Existing Content and Boundaries

Primary destination:

- `linux/04-concurrency-primitives/README.md`

Existing related notes should be linked or briefly referenced, not duplicated:

- `java/concurrent/synchronized.md`: Monitor, EntryList/WaitSet, `wait/notify`.
- `java/concurrent/AQS.md`: AQS sync queue, Condition queue, `LockSupport.park/unpark`.
- `cli-toolbox/01-process-and-job-control.md`: `wchan=futex_wait` troubleshooting perspective.
- `python-concurrency/00-execution-model/README.md`: generic run queue / wait queue mental model.

The `linux/04` chapter remains the canonical OS primitive explanation. Java notes remain language-level implementation notes.

## Approach

Use a bounded "A plus light B plus C bridge" depth:

- **A: required** - queue/state-machine explanation, lost wakeup prevention, spurious wakeup, wake/recheck flow.
- **Light B: included** - mention `futex key`, hash bucket, waiter queue, and requeue at concept level.
- **C: included** - short Java bridge for `synchronized`, `Object.wait`, `ReentrantLock`, `Condition`, AQS, and `LockSupport`.

Avoid:

- kernel function call chains;
- futex priority-inheritance variants except as a one-line boundary if needed;
- detailed HotSpot source internals;
- new runnable lab unless a clean, stable reproduction is already available.

## Documentation Changes

### 1. Expand Futex Black-Box Internals

Insert after the current "第二层：内核 futex syscall" explanation and before the architecture tradeoff paragraph.

Content shape:

```text
用户态 lock_word 地址
  -> futex syscall(uaddr, expected)
  -> kernel derives futex key
  -> hash bucket
  -> waiter queue
```

Key points:

- A futex is not a persistent kernel object. The visible state is still a user-space integer.
- The kernel only becomes involved when a syscall asks it to wait or wake on an address.
- For private futexes, the key is effectively derived from process memory identity plus `uaddr`; for shared mappings, it must identify the shared backing object.
- The key hashes to a bucket that contains waiters sleeping on matching futex keys.
- `FUTEX_WAIT(uaddr, expected)` must first check whether `*uaddr == expected`.
- If the value already changed, the syscall returns immediately, so a thread does not sleep after the wakeup has already happened.
- `FUTEX_WAKE(uaddr, n)` finds waiters by the same key and wakes up to `n` of them. Woken threads are runnable candidates, not guaranteed immediate owners of the lock.

### 2. Add Lost-Wakeup Timeline

Add a compact timeline under the futex section:

```text
T1 unlocks: lock_word = 0; futex_wake(addr)
T2 is about to wait
```

Explain that the expected-value check closes this race:

- If T2 enters the kernel after T1 already changed the word to `0`, `FUTEX_WAIT(addr, 1)` sees mismatch and refuses to sleep.
- Without that check, T2 could sleep forever waiting for a wakeup that already happened.

### 3. Expand Condition Variable Internals

Replace or expand the current short "条件变量底层 = futex 等待队列" paragraph.

Core model:

```text
mutex wait queue:       threads waiting to own the lock
condition wait queue:   threads that already gave up the lock and are waiting for a predicate
```

`wait()` flow:

1. Caller holds the mutex.
2. Caller checks predicate and finds it false.
3. Runtime/libc links the waiter to the condition wait queue.
4. It atomically releases the mutex and parks the thread.
5. After wakeup, the thread must re-acquire the mutex.
6. After re-acquiring, it must re-check the predicate in a `while` loop.

`signal()` flow:

1. Producer changes shared state while holding the mutex.
2. Producer signals one waiter.
3. The waiter becomes eligible to run, but still must compete for the mutex before returning from `wait`.

`broadcast()` flow:

1. All condition waiters are made eligible.
2. Only one can own the mutex at a time.
3. Others may wake, fail to acquire the mutex, and sleep again, which is the thundering-herd cost.

### 4. Explain Requeue Without Over-Deep Kernel Detail

Add a short note:

- Implementations such as glibc can use futex requeue operations to move waiters from the condition-variable futex to the mutex futex instead of waking all of them into a lock stampede.
- This preserves the semantic model: `signal/broadcast` does not mean "run immediately"; it means "leave the condition wait and eventually re-contend for the mutex."
- Priority-inheritance futex operations are outside this chapter's scope.

### 5. Add Java Bridge Box

Add a short "Java 对照" callout near the condition-variable section.

Include:

- `synchronized` and `Object.wait/notify` are JVM Monitor semantics. Conceptually there is an entry queue for lock acquisition and a wait set for `wait`.
- `Object.wait()` releases the monitor and parks the Java thread; after notification it has to re-acquire the monitor before continuing.
- `ReentrantLock` and `Condition` are AQS-based. AQS has a sync queue for lock acquisition; each `ConditionObject` has a condition queue.
- `await()` moves the thread to the condition queue and parks via `LockSupport.park`.
- `signal()` transfers a condition waiter back to the AQS sync queue; unlock eventually unparks a successor.
- On Linux, blocking a platform thread ultimately reaches JVM/native parking primitives backed by OS synchronization such as pthread/futex, but Java code should reason in Monitor/AQS terms.

## Cross-Links

Add or update links:

- From futex section to `cli-toolbox/01-process-and-job-control.md` for `wchan=futex_wait` interpretation.
- From Java bridge to `java/concurrent/synchronized.md` and `java/concurrent/AQS.md`.
- Keep existing `linux-handson/03-process-model` back-links.

## Testing and Review

This is a documentation-only change. Verification should include:

- read the modified sections end-to-end for flow;
- check that the summary diagram still matches the expanded explanation;
- run a focused grep for duplicated or contradictory claims around `FUTEX_WAIT_BITSET`, `FUTEX_CMP_REQUEUE`, and Java lock implementation wording;
- optionally inspect rendered Markdown if the editor supports it.

No container lab is required for this change. The current futex `strace` evidence remains valid and should stay scoped to "uncontended locks mostly avoid syscalls."

## Risks

- Overstating Java implementation details: avoid saying Java directly calls futex for every lock path.
- Overstating condition-variable implementation details: POSIX/glibc and JVM monitors are not identical, so describe shared semantics first and implementation choices second.
- Making the section too kernel-specific: keep `futex key/hash bucket/waiter queue/requeue` conceptual and skip source-level paths.

## Acceptance Criteria

- `linux/04-concurrency-primitives/README.md` clearly distinguishes user-space CAS state from kernel futex wait queues.
- The futex section explicitly explains expected-value checking and lost-wakeup prevention.
- The condition-variable section explicitly distinguishes condition wait queue from mutex wait queue.
- The Java bridge explains Monitor and AQS mapping without duplicating the existing Java notes.
- Existing cross-track boundaries remain intact: `linux/04` explains OS primitives; Java files remain Java-specific deep dives; CLI toolbox remains troubleshooting-oriented.
