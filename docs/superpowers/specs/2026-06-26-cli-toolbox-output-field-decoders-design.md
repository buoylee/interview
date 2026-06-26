# cli-toolbox Output Field Decoders Design

## Goal

Add small "output decoder" blocks across `cli-toolbox` so common commands are not only listed, but readable when their output contains dense abbreviations, status codes, counters, IDs, timing fields, or resource percentages.

This continues the `vmstat` style added in `cli-toolbox/02-performance-and-resource-triage.md`: show representative output, explain fields, then add one practical caveat.

## Scope

Cover all existing `cli-toolbox` chapters `01` through `10`. Each chapter gets 1-3 high-value decoder blocks only when the command output is worth decoding.

In scope:

- Process/resource/status outputs: `ps`, `top`, `iostat`, `free`, `ss`, `dig`, `curl -w`, `tcpdump`, `strace`, `lsof`, `/proc/<pid>/status`
- Text/file/system outputs: `awk` field variables, `sort | uniq -c`, `ls -l`, `df -h`, `df -i`, `stat`, `lsblk`, `systemctl status`, `journalctl`
- Container/git/remote outputs: `docker ps`, `docker stats`, `kubectl get`, `kubectl describe`, `kubectl get events`, `git status -sb`, `git diff`, `git log --oneline --graph`, `ssh -v`, `ssh -G`, `rsync --progress`

Out of scope:

- Turning chapters into full man pages
- Adding rare flags that are not part of daily troubleshooting
- Rewriting chapter structure
- Changing existing command recommendations unless a decoder reveals a clear wording issue

## Selection Rule

Add a decoder only if at least one is true:

- Output has abbreviated columns such as `STAT`, `TTY`, `Recv-Q`, `%wa`, `await`, `RSS`, `AGE`
- Output has status codes or symbolic markers such as `R/S/D/Z`, `M/A/D`, `+/-`, `CrashLoopBackOff`
- Output has latency, queue, saturation, or usage fields that require judgment
- Output has multiple IDs whose relationship matters, such as `PID/PPID/PGID/SID`
- Output is often pasted in interviews or incident response and needs fast reading

Skip commands whose output is self-explanatory or whose main challenge is syntax rather than reading output.

## Content Pattern

Each decoder should be compact and use the existing `cli-toolbox` voice:

````md
如果看到這種輸出,按區塊這樣讀:

```text
COMMAND OUTPUT HERE
```

| 欄位/符號 | 意思 | 怎麼判讀 |
|---|---|---|
| `FIELD` | field meaning | practical judgment |

> 小坑:common misread and how to avoid it.
````

Rules:

- Keep each decoder roughly 8-15 lines unless the command is especially dense.
- Prefer "how to judge" over dictionary-style definitions.
- Include one small pitfall when it prevents common misreads.
- Preserve existing chapter flow: add decoder blocks inside each command's current "主力命令深講 + 速驗" section.
- Keep Traditional Chinese style already used by `cli-toolbox`.

## Chapter Plan

### 01 Process and Job Control

- `ps`: decode `PID/PPID/PGID/SID/TTY/STAT/COMM`
- `STAT`: expand `R/S/D/T/Z`, plus suffixes `+`, `s`, `<`, `N`, `l`

### 02 Performance and Resource Triage

- `top`: decode load, tasks, CPU line, memory line
- `iostat`: decode `r/s`, `w/s`, `await`, `%util`, and why `await` often matters more than `%util`
- `free`: decode `total/used/free/shared/buff/cache/available`
- `vmstat`: already has first decoder; keep it and only refine if needed

### 03 Network Triage

- `ss`: decode `State`, `Recv-Q`, `Send-Q`, `Local Address:Port`, `Peer Address:Port`, `users:(...)`
- `dig`: decode `ANSWER SECTION`, `A/CNAME`, `TTL`, `SERVER`, `Query time`
- `curl -w`: decode `time_namelookup`, `time_connect`, `time_appconnect`, `time_starttransfer`, `time_total`
- `tcpdump`: decode timestamp, direction, protocol, flags, seq/ack, length

### 04 Observability Internals

- `strace`: decode syscall line shape, return value, `errno`, and time fields from `-T/-tt`
- `lsof`: decode `COMMAND/PID/USER/FD/TYPE/DEVICE/SIZE/OFF/NODE/NAME`
- `/proc/<pid>/status`: decode `State`, `VmRSS`, `Threads`, `voluntary_ctxt_switches`

### 05 Text Processing and Pipes

- `awk`: decode `$0`, `$1`, `$NF`, `NF`, `NR`, `FS`, `OFS`
- `sort | uniq -c`: decode count-first output and why `uniq` needs sorted input
- `jq`: skip for this pass unless an existing `jq` block already has room for one short object/array traversal note

### 06 Files, Disk, Permissions

- `ls -l`: decode file type, permission triplets, link count, owner, group, size, timestamp
- `df -h` / `df -i`: decode blocks vs inode exhaustion
- `stat`: decode access/modify/change time
- `lsblk`: decode `NAME`, `MAJ:MIN`, `RM`, `SIZE`, `RO`, `TYPE`, `MOUNTPOINTS`

### 07 systemd and Services

- `systemctl status`: decode `Loaded`, `Active`, `Main PID`, `code`, `status`, recent logs
- `journalctl`: decode timestamp, host, unit/process, PID, priority/filtering cues

### 08 Containers and k8s

- `docker ps`: decode `CONTAINER ID`, `IMAGE`, `COMMAND`, `STATUS`, `PORTS`, `NAMES`
- `docker stats`: decode CPU%, memory usage/limit, network/block IO, PIDs
- `kubectl get pods`: decode `READY`, `STATUS`, `RESTARTS`, `AGE`
- `kubectl describe` / events: decode event type, reason, age, source, message

### 09 Git Lifesaver

- `git status -sb`: decode branch tracking, ahead/behind, two-column file status
- `git diff`: decode file headers, hunks, `+/-`, index lines
- `git log --oneline --graph`: decode graph symbols, refs, commit order

### 10 Remote and Transfer

- `ssh -v`: decode connection phases: config, DNS/connect, key exchange, auth, session
- `ssh -G`: decode "effective config" output
- `rsync --progress`: decode bytes, percent, transfer rate, ETA, `xfr#`, `to-chk`

## Verification

Because this is documentation, verification is text-focused:

- Run `git diff --check -- cli-toolbox docs/superpowers/specs/2026-06-26-cli-toolbox-output-field-decoders-design.md`
- Use `rg -n` to confirm added decoder headers/phrases appear across chapters
- Review diff manually for Markdown table breaks and overlong blocks
- Keep unrelated dirty files untouched

## Risks

- Over-expansion can make chapters harder to scan. Mitigation: cap each chapter at 1-3 decoder blocks.
- Field meanings vary slightly by distro/tool version. Mitigation: explain stable concepts and avoid version-specific trivia.
- Some sample outputs can be too large. Mitigation: use minimal representative snippets.
