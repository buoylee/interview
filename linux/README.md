# Linux 学习 → 已迁移到 `linux-handson/`

> 这个目录早期是一些零散笔记 + 几个空文件。系统化的 Linux 学习/面试课程已重建在 **[`../linux-handson/`](../linux-handson/)**。

## 去哪学

➡️ **[`linux-handson/`](../linux-handson/)** —— 资深全栈「够用且能答」定位的动手课:

- 主线:**内核是资源管理者,每种资源一章**(进程 / 内存 / I/O / 网络)。
- 形态:每章七段式(原理 → 动手 → 面试速记)+ 真 VM 沙箱 + 99 面试卡。
- 设计 spec:[`docs/superpowers/specs/2026-05-31-linux-learning-path-design.md`](../docs/superpowers/specs/2026-05-31-linux-learning-path-design.md)

## 旧笔记

原来的 `basic.md`、`memory.md`、`好用命令.md` 已移到 [`_archive/`](./_archive/) 保留。
它们的内容(`top`/`free`/`VIRT`/`VSZ`/`RES`/`RSS` 等)已被新课更完整地覆盖:

| 旧笔记 | 现在看 |
|--------|--------|
| `basic.md`(top、VIRT/VSZ、文件映射) | [`linux-handson/04-memory-model`](../linux-handson/04-memory-model/) + [`07-troubleshooting-playbook`](../linux-handson/07-troubleshooting-playbook/) |
| `memory.md`(free、RES/RSS、查内存大户) | [`linux-handson/04-memory-model`](../linux-handson/04-memory-model/) |
| `好用命令.md`(个人命令片段) | 保留在 `_archive/`(非课程内容) |
