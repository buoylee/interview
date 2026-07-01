# CLI Survival Kit Design

## Context

`cli-toolbox/CORE-SET.md` already covers the main engineering triage categories:
process/job control, performance, network, text pipelines, files/disk,
services, containers, Kubernetes, Git, and remote workflows.

The missing layer is the daily operating layer: commands that a senior software
engineer or architect repeatedly uses before, during, and around investigation
work, but that do not naturally belong to one single triage chapter.

## Goal

Add `cli-toolbox/00-cli-survival-kit.md` as a practical daily CLI survival
chapter for senior engineers and architects.

The chapter should be compact, opinionated, and usable. It should teach the
minimum command set that keeps a terminal workflow productive without turning
into a Linux beginner encyclopedia or a full shell manual.

## Non-Goals

- Do not duplicate the existing deep-dive chapters in `cli-toolbox/01` through
  `cli-toolbox/10`.
- Do not explain every option of every command.
- Do not make the chapter Ubuntu-only, even though `apt` and `dpkg` should be
  included because the current practice environment is an Ubuntu container.
- Do not cover advanced `tmux` pane/window layouts, plugin managers, or shell
  customization.
- Do not recommend `tmux` as a replacement for real service managers such as
  systemd, Docker Compose, or Kubernetes.

## Recommended Approach

Create a new chapter before the current numbered chapters:

```text
cli-toolbox/00-cli-survival-kit.md
```

Also add a small entry point from `cli-toolbox/CORE-SET.md` so the reading path
becomes:

```text
00 survival kit: daily terminal operating layer
01-10 core set: engineering triage and production-style workflows
```

## Chapter Structure

The new chapter should use the same compact style as the existing toolbox:

```text
command / what it does / muscle memory / common pitfall / quick verification
```

It should contain seven sections.

### 1. Packages and Tool Installation

Commands:

- `apt update`
- `apt install [-y] pkg`
- `apt search pkg`
- `apt show pkg`
- `apt policy pkg`
- `apt list --installed`
- `apt remove pkg`
- `apt purge pkg`
- `apt autoremove`
- `dpkg -L pkg`
- `dpkg -S path`

Key teaching points:

- `apt update` updates package indexes, not installed packages.
- `apt upgrade` changes installed packages and should not be treated as a
  reflex command on production machines.
- `-y` is useful in containers and scripts, but manual installs can omit it.
- `dpkg -L` answers "what did this package install?"
- `dpkg -S` answers "which package owns this file?"

### 2. Command Existence and Execution Source

Commands:

- `type cmd`
- `command -v cmd`
- `which cmd`
- `whereis cmd`

Key teaching points:

- Prefer `type` when using an interactive shell because it can identify aliases,
  shell functions, builtins, and binaries.
- Use `command -v` in scripts when checking whether a command exists.
- `which` is familiar but can miss shell aliases/functions depending on shell
  behavior.

### 3. Terminal Worksite

Commands and keys:

- `tmux new -s name`
- `tmux ls`
- `tmux attach -t name`
- `Ctrl+b d`
- `history`
- `Ctrl+r`
- `!!`

Key teaching points:

- `tmux` preserves a terminal worksite that can be detached and attached later.
- `tmux` is appropriate for SSH sessions, containers, long commands, and
  investigation workflows that should survive terminal disconnects.
- Without `tmux` or `screen`, a disconnected foreground interactive job usually
  cannot be cleanly reattached.
- `history`, `Ctrl+r`, and `!!` are daily command recall tools.

### 4. Viewing Output and Watching Changes

Commands:

- `less file`
- `head -n N file`
- `tail -n N file`
- `tail -f file`
- `watch -n 1 cmd`
- `tee file`

Key teaching points:

- Use `less` for paged reading and search.
- Use `tail -f` for following logs.
- Use `watch` to repeat a command while observing changing state.
- Use `tee` when output must be visible and saved at the same time.

### 5. Shell Primitives

Concepts and forms:

- `$?`
- `>`
- `>>`
- `2>`
- `2>&1`
- `|`
- `VAR=value cmd`
- `export VAR=value`

Key teaching points:

- Every command returns an exit code.
- Standard output and standard error are different streams.
- Redirection controls where streams go.
- A pipe connects stdout of the left command to stdin of the right command.
- `VAR=value cmd` sets an environment variable only for that command.
- `export VAR=value` sets it for the current shell and child processes.

### 6. Compression and Transfer-Friendly Bundles

Commands:

- `tar -czf archive.tgz dir`
- `tar -xzf archive.tgz`
- `tar -tzf archive.tgz`
- `gzip file`
- `gunzip file.gz`
- `zip -r archive.zip dir`
- `unzip archive.zip`

Key teaching points:

- `tar` makes an archive; `gzip` compresses bytes.
- `.tgz` and `.tar.gz` usually mean tar archive compressed with gzip.
- Use `tar -tzf` to inspect before extracting.

### 7. System, Identity, and Location Snapshot

Commands:

- `date`
- `uptime`
- `uname -a`
- `hostname`
- `whoami`
- `id`
- `pwd`
- `env`

Key teaching points:

- These commands answer the first operational questions: what machine, what
  user, what system, what directory, what time, and what environment.
- They are especially useful inside containers, SSH sessions, CI runners, and
  unfamiliar production hosts.

## CORE-SET Integration

Add a short pointer near the top of `cli-toolbox/CORE-SET.md`, before the six
triage categories:

```text
開始前: 日常 CLI survival kit -> [00](00-cli-survival-kit.md)
```

This keeps `CORE-SET.md` focused while making the new chapter discoverable.

## Acceptance Criteria

- `cli-toolbox/00-cli-survival-kit.md` exists.
- `cli-toolbox/CORE-SET.md` links to the new chapter.
- The new chapter is compact and senior-engineer oriented.
- The new chapter includes quick verification examples where they materially
  improve understanding.
- The new chapter clearly distinguishes:
  - `apt update` vs `apt upgrade`
  - `tmux` vs `nohup`/background jobs
  - `type` vs `which` vs `command -v`
  - stdout vs stderr redirection
  - `tar` archive creation vs compression
- The new chapter does not expand into advanced shell scripting, advanced tmux
  usage, or service-management guidance.

## Implementation Notes

Keep the first implementation focused:

- Add one new Markdown chapter.
- Add one link from `CORE-SET.md`.
- Do not restructure the existing chapter numbering.
- Do not rewrite existing chapters unless a short cross-reference is necessary.
