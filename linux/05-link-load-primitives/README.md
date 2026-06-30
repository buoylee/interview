# 05 链接装载原语

> **这章解决什么问题**
>
> 你在 `strace echo hi` 里看到 `/etc/ld.so.cache`、`libc.so.6`、`ld-linux`，在 `/proc/<pid>/maps` 里看到一堆 `.so` 被映射进进程地址空间。现象已经出现了，但「二进制到底怎么被装进内存」「为什么找不到 `.so`」「undefined symbol 是谁没解析出来」还没展开。本章补齐编译、链接、装载、符号解析这条链。

**依赖**：

- 虚拟地址空间、`mmap`、`/proc/<pid>/maps` → [`linux/01-memory-primitives`](../01-memory-primitives/README.md)
- `execve`、syscall、进程如何开始执行 → [`linux/02-execution-primitives`](../02-execution-primitives/README.md)
- fd、`openat`、文件映射 → [`linux/03-io-primitives`](../03-io-primitives/README.md)

**三层怎么读：**

- **① 你视角** — 先用 Java/Go/Python 加载 native library 的经验搭桥。
- **② 黑盒内部** — ELF、loader、符号表、重定位真正做了什么。
- **③ 砸实** — 用 `file` / `readelf` / `ldd` / `nm` / `strace` / `/proc/<pid>/maps` 看证据。

---

## 原语一：ELF 文件格式

### ① 你视角

你运行一个 Linux 可执行文件时，不是把整个文件原样读进内存然后从第一字节开始跑。可执行文件里有一张「装载说明书」：哪些字节是机器码，哪些是只读数据，哪些要映射成可写内存，入口地址在哪里，要不要动态链接器先接管。这种格式就是 **ELF**。

### ② 黑盒内部

ELF 有两套常见视角：

| 视角 | 面向谁 | 回答什么 |
|---|---|---|
| Section | 链接器 / 调试工具 | `.text`、`.data`、`.bss`、`.symtab`、`.rela.*` 分别是什么 |
| Segment | 内核装载器 | 哪些字节要映射到进程地址空间,权限是什么,入口从哪开始 |

常见 section：

| section | 含义 |
|---|---|
| `.text` | 机器码,通常只读+可执行 |
| `.rodata` | 字符串常量、只读表 |
| `.data` | 已初始化全局变量 |
| `.bss` | 未初始化全局变量,文件里不占真实内容,装载时清零 |
| `.symtab` / `.dynsym` | 符号表,记录函数/变量名与地址关系 |
| `.rela.*` / `.rel.*` | 重定位表,记录哪些地址等链接/装载时再补 |

内核真正装程序时主要看 **program header** 里的 `PT_LOAD` 段。每个段会被映射成进程虚拟地址空间的一段:

```text
ELF PT_LOAD segment
  offset in file
  virtual address
  size in file / size in memory
  permission: R / W / X

→ mmap 到进程地址空间
```

### ③ 砸实

```bash
file /bin/ls
readelf -h /bin/ls
readelf -l /bin/ls     # program headers: loader 真正关心的装载段
readelf -S /bin/ls     # sections: 链接/调试视角
```

看点:

- `Type: DYN` 不一定是共享库,现代 PIE 可执行文件也常是 DYN。
- `Entry point address` 是程序入口,但动态链接程序通常先让 loader 做初始化。
- `LOAD` 段的 `R E` / `RW` 权限最后会反映到 `/proc/<pid>/maps`。

---

## 原语二：编译 vs 链接

### ① 你视角

你写 `gcc main.c -o app` 一步完成,但内部至少分两段:先把每个 `.c` 编成 `.o` 目标文件,再把多个目标文件和库链接成最终可执行文件。

### ② 黑盒内部

目标文件里有两类东西:

1. **已定义符号**:这个 `.o` 自己提供的函数/变量,例如 `main`、`helper`。
2. **未定义符号**:这个 `.o` 要用但自己没有的符号,例如 `printf`。

链接器的工作就是把「引用」接到「定义」上:

```text
main.o:
  defines: main
  undefined: printf, helper

helper.o:
  defines: helper

libc.so:
  defines: printf

链接:
  main.o 的 helper 引用 → helper.o 的 helper
  main.o 的 printf 引用 → libc.so 的 printf(动态链接时运行期解析)
```

如果链接器找不到定义,就出现:

```text
undefined reference to `foo`
```

如果编译期允许未解析、运行期动态装载时才发现找不到,就可能出现:

```text
undefined symbol: foo
```

### ③ 砸实

```bash
gcc -c main.c -o main.o
nm main.o          # U printf = undefined; T main = text symbol
gcc main.o -o app  # 链接
```

看 `nm` 输出时:

| 标记 | 意思 |
|---|---|
| `T` | text 段里定义的函数符号 |
| `D` / `B` | data / bss 里的全局变量 |
| `U` | undefined,当前文件引用但没有定义 |

---

## 原语三：静态链接 vs 动态链接

### ① 你视角

Go 常见「一个二进制丢到机器上就跑」,C/Java native library 常见「缺一个 `.so` 就起不来」。核心差别就是:依赖代码是打进可执行文件,还是运行时再找共享库。

### ② 黑盒内部

| 模式 | 机制 | 优点 | 代价 |
|---|---|---|---|
| 静态链接 | 把库代码复制进最终可执行文件 | 部署简单,少依赖 | 文件大,库升级要重新链接 |
| 动态链接 | 可执行文件记录需要哪些 `.so`,运行时由 loader 映射 | 多进程共享库代码页,升级灵活 | 启动依赖环境,可能找不到库/符号 |

动态链接的可执行文件里不会包含完整 libc 代码,而是记录:

```text
NEEDED libc.so.6
INTERP /lib64/ld-linux-x86-64.so.2
```

`INTERP` 指定动态装载器。内核 `execve` 看到这个字段后,不是直接跳到你的 `main`,而是先把控制权交给 `ld-linux`。

### ③ 砸实

```bash
readelf -l /bin/ls | grep 'interpreter'
readelf -d /bin/ls | grep NEEDED
ldd /bin/ls
```

看点:

- `interpreter` 行就是动态装载器路径。
- `NEEDED` 是声明依赖,不是实际搜索结果。
- `ldd` 展示 loader 最终会把这些依赖解析到哪些真实路径。

---

## 原语四：动态装载器 ld-linux

### ① 你视角

你的程序明明只是 `printf("hi")`,为什么 `strace` 里启动时打开了 `/etc/ld.so.cache`、`libc.so.6`？因为动态链接程序启动前,loader 要先把依赖库找齐、映射进地址空间、修补符号引用。

### ② 黑盒内部

动态程序启动链路:

```text
shell fork/execve("./app")
  → 内核读取 ELF header
  → 发现 PT_INTERP = ld-linux
  → mmap app 的 LOAD 段
  → mmap ld-linux
  → 跳到 ld-linux 入口
  → ld-linux 读取 app 的 dynamic section
  → 找 NEEDED 的 .so
  → mmap 每个 .so
  → 做 relocation / symbol binding
  → 调用 libc / constructors
  → 跳到 app 的 main
```

`.so` 本质上也是 ELF 文件,被 loader 通过 `mmap` 映射进进程地址空间。多个进程加载同一个 `.so` 时,只读代码页可共享;每个进程自己的可写 data/bss 页是私有 copy-on-write。

### ③ 砸实

```bash
strace -e trace=openat,mmap,execve /bin/echo hi
cat /proc/$$/maps | grep -E 'libc|ld-linux'
```

看点:

- `openat("/etc/ld.so.cache")` 是查库路径缓存。
- `openat(... "libc.so.6")` 是打开共享库文件。
- `mmap(... PROT_READ|PROT_EXEC ...)` 是把库代码段映射进地址空间。

---

## 原语五：库搜索路径

### ① 你视角

线上报:

```text
error while loading shared libraries: libfoo.so: cannot open shared object file
```

这不是「文件一定不存在」,而是 loader 按规则搜索时没找到它。

### ② 黑盒内部

动态库搜索大致按这几类来源:

| 来源 | 说明 |
|---|---|
| `RPATH` / `RUNPATH` | 编译链接时写进 ELF 的搜索路径 |
| `LD_LIBRARY_PATH` | 运行时环境变量,临时加搜索目录 |
| `/etc/ld.so.cache` | `ldconfig` 生成的系统库路径缓存 |
| 默认目录 | `/lib`、`/usr/lib`、架构相关目录 |

`LD_LIBRARY_PATH` 很方便,但生产上要谨慎:它会影响整个进程的库解析,容易因为同名库覆盖系统库导致难排查的问题。服务部署更推荐明确 rpath/runpath 或固定包内路径。

### ③ 砸实

```bash
readelf -d ./app | grep -E 'RPATH|RUNPATH|NEEDED'
LD_DEBUG=libs ./app 2>&1 | head -50
ldconfig -p | grep libc
```

看点:

- `LD_DEBUG=libs` 会打印 loader 实际搜索了哪些目录。
- `ldconfig -p` 查的是系统缓存,不等于当前进程最终一定用它。

---

## 原语六：符号解析与 LD_PRELOAD

### ① 你视角

同样叫 `malloc` 的函数,可能来自 libc,也可能被某个 allocator 或 profiler 替换。`LD_PRELOAD` 能「抢先」加载一个 `.so`,让里面的符号优先被解析到。

### ② 黑盒内部

动态符号解析是按作用域和顺序查找符号名。简化模型:

```text
app 调用 malloc
  → loader 查全局符号表
  → 先看可执行文件/预加载库/依赖库的导出符号
  → 找到第一个匹配的 malloc
  → 把调用位置绑定到该地址
```

`LD_PRELOAD=./libhook.so ./app` 会让 `libhook.so` 提前进入解析顺序,从而覆盖后续库中的同名符号。malloc hook、性能 profiler、故障注入工具常用这个机制。

常见错误:

| 错误 | 根因 |
|---|---|
| `undefined symbol: foo` | 运行期没有任何已加载对象导出 `foo` |
| `version 'GLIBC_2.xx' not found` | 目标机器 libc 版本低于构建机器要求 |
| 加载了错误 `.so` | 搜索路径顺序导致同名库被抢先命中 |

### ③ 砸实

```bash
nm -D /lib/x86_64-linux-gnu/libc.so.6 | grep ' malloc@@'
readelf --dyn-syms ./libfoo.so
LD_DEBUG=symbols ./app 2>&1 | grep foo
```

不同发行版库路径不同,先用 `ldd ./app` 找到真实 libc 路径。

---

## 原语七：运行时加载 dlopen

### ① 你视角

插件系统、JNI、Python `ctypes` / `cffi`、Go cgo 都可能在程序已经启动后再加载 `.so`。这不是 `execve` 时的依赖装载,而是进程运行中主动调用 loader API。

### ② 黑盒内部

`dlopen(path, flags)` 做的事:

```text
打开 .so
  → 检查 ELF
  → 解析它的 NEEDED 依赖
  → mmap .so 和依赖
  → 处理 relocation
  → 执行 constructor
  → 返回 handle

dlsym(handle, "name")
  → 在该对象符号表里找 name
  → 返回函数/变量地址
```

`dlclose` 只是减少引用计数。是否立刻卸载要看是否还有其他引用、是否有 TLS / constructor/destructor / runtime 约束。实际生产里不要假设 `dlclose` 后 RSS 必然下降。

### ③ 砸实

```bash
ldd ./plugin.so
readelf -d ./plugin.so | grep NEEDED
strace -e trace=openat,mmap ./app-that-dlopen-plugin
```

看点:运行到插件路径时才会出现对应 `.so` 的 `openat` / `mmap`。

---

## 本章速查

| 原语 | 一句话 | 工具 |
|---|---|---|
| ELF | 二进制的装载说明书 | `file`、`readelf -h/-l/-S` |
| 链接 | 把符号引用接到定义 | `nm`、`objdump -t` |
| 动态链接 | 运行时由 loader 找 `.so` 并解析符号 | `readelf -d`、`ldd` |
| 动态装载器 | `ld-linux` 先于 `main` 运行 | `strace`、`LD_DEBUG=libs` |
| 库搜索路径 | loader 按规则找依赖库 | `RPATH`、`RUNPATH`、`LD_LIBRARY_PATH` |
| 符号解析 | 名字绑定到函数/变量地址 | `nm -D`、`readelf --dyn-syms` |
| dlopen | 进程运行中加载 `.so` | `dlopen`、`dlsym`、`strace` |

**下一章**：[`linux/06-network-kernel-primitives`](../06-network-kernel-primitives/README.md)——socket、队列、buffer、`sk_buff` 和内核收发包路径。
