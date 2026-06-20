# 00 · io 接口家族:Reader / Writer / 组合

> `io.Reader` 和 `io.Writer` 是 Go 标准库的灵魂——两个单方法接口,撑起了文件、网络、内存、压缩、加密、HTTP body 的统一处理。理解它就理解了 [`design/00`](../../design/00-interface-design/README.md) 的「小接口 + 组合」哲学在标准库的实践。
>
> 桥接锚点:Java `InputStream`/`OutputStream` + 装饰器流(`BufferedInputStream(new FileInputStream(...))`)←→ Go `io.Reader`/`io.Writer` + 组合包装(`bufio.NewReader(file)`)。思想一致,但 Go 接口更小、隐式实现。

---

## 1. 核心问题

- `io.Reader`/`io.Writer` 为什么只有一个方法?这么小有什么用?
- 文件、网络、内存 buffer、HTTP body 怎么用同一套代码处理?
- `io.Copy(dst, src)` 怎么做到「从任意源拷到任意目的地」?

---

## 2. 直觉理解

### 两个单方法接口,统一一切「字节流」

```go
type Reader interface { Read(p []byte) (n int, err error) }   // 把数据读进 p
type Writer interface { Write(p []byte) (n int, err error) }  // 把 p 写出去
```

只要实现这一个方法,就能接入整个 io 生态。所以:

- `*os.File`、`net.Conn`、`*bytes.Buffer`、`strings.Reader`、`http.Request.Body`、`gzip.Reader`…… **全是 `io.Reader`**;
- 任何接受 `io.Reader` 的函数(`io.Copy`、`bufio.NewReader`、`json.NewDecoder`)**对它们一视同仁**。

这就是 [`design/00`](../../design/00-interface-design/README.md) 「接口越小,越多类型能满足,组合力越强」的活教材。

### 组合:像搭管道一样包装

```go
f, _ := os.Open("data.gz")
gz, _ := gzip.NewReader(f)        // gzip.Reader 包住 file(它也是 Reader)
br := bufio.NewReader(gz)         // 再加缓冲
// br 是 Reader,底层:bufio → gzip 解压 → file 读字节
```

每层都「是一个 Reader、又包着一个 Reader」——和 Java 装饰器流一模一样,但靠隐式接口零声明。

---

## 3. 原理深入

### 3.1 Read 的契约(容易答错)

`Read(p []byte) (n int, err error)`:

- 把数据读进 `p`,返回**读了几个字节 n** 和 err。
- **可能同时返回 `n > 0` 和 `err != nil`**(读到一些数据同时遇到结尾)——所以**先处理 n 个字节,再判 err**,别一看到 err 就丢掉已读数据。
- 流结束返回 `io.EOF`(一个哨兵 error,见 [`error-handling/01`](../../error-handling/01-error-values/README.md));`io.EOF` 不是「错误」是「正常结束」,要 `errors.Is(err, io.EOF)` 或 `== io.EOF` 判断。

```go
for {
    n, err := r.Read(buf)
    if n > 0 { process(buf[:n]) }       // 先用已读数据
    if err == io.EOF { break }          // 正常结束
    if err != nil { return err }        // 真错误
}
```

### 3.2 io.Copy 与 ReaderFrom/WriterTo 优化

```go
io.Copy(dst, src)        // 从 src 读、往 dst 写,直到 EOF;内部用一个缓冲区搬运
```

`io.Copy(dst Writer, src Reader)` 对任意组合都работает。优化:如果 `dst` 实现了 `ReaderFrom`、或 `src` 实现了 `WriterTo`,`io.Copy` 会**直接调用它们**(可能零拷贝/用 sendfile),跳过中间缓冲。这是「接口 + 可选能力探测」的精妙设计。

### 3.3 常用组合件

| 包/类型 | 作用 |
|---|---|
| `bufio.Reader`/`Writer`/`Scanner` | 缓冲(减少系统调用)、按行/按 token 读 |
| `bytes.Buffer` / `strings.Reader` | 内存里的 Writer / Reader |
| `io.MultiReader` / `MultiWriter` | 串联多个源 / 同时写多个目的(≈ tee) |
| `io.TeeReader` | 读的同时复制一份到 Writer |
| `io.LimitReader` | 限制最多读 N 字节(防超大输入) |
| `io.Discard` | 黑洞 Writer(丢弃) |

### 3.4 接口的组合定义

```go
type ReadWriter interface { Reader; Writer }          // 嵌入组合(type-system/04)
type ReadCloser interface { Reader; Closer }
```

函数声明它**真正需要的最小能力**:只读收 `io.Reader`,要关才收 `io.ReadCloser`(见 [`design/00`](../../design/00-interface-design/README.md))。

---

## 4. 日常开发应用

- **函数收 `io.Reader`/`io.Writer` 而非 `*os.File`/`[]byte`**:这样文件、网络、内存、测试用的 `strings.Reader` 都能传(可测!见 [`testing/01`](../../testing/01-mock-interfaces/README.md))。
- **大数据流式处理用 io.Copy / Scanner**,别 `ReadAll` 把整个读进内存。
- **加缓冲用 bufio**(频繁小读写时减少系统调用)。
- **Read 循环先处理 n 再判 err**,`io.EOF` 当正常结束。
- **测试**:用 `bytes.Buffer`(Writer)、`strings.Reader`(Reader)替代真文件/网络。

---

## 5. 生产&调优实战

- **`io.ReadAll` 是 OOM 隐患**:把整个响应/文件读进内存,大输入直接撑爆;用流式(`io.Copy`/`Scanner`/`Decoder`)或 `io.LimitReader` 设上限。
- **bufio 减少系统调用**:逐字节/逐小块读写裸 `*os.File`/`net.Conn` 会有大量 syscall;包一层 `bufio` 显著提速。
- **务必 Close + 排空**:`io.ReadCloser`(HTTP body、文件)要 `defer Close()`;HTTP body 还要读完才能复用连接(见 [`01`](../01-net-http/README.md))。
- **`io.Copy` 的零拷贝**:文件→网络等场景,实现了 ReaderFrom/WriterTo 的类型让 Copy 走 sendfile,省内核态拷贝。
- **`bufio.Scanner` 的行长上限**:默认 64KB,超长行会报错;大行用 `Scanner.Buffer` 调大或换 `bufio.Reader.ReadString`。

---

## 6. 面试高频考点

- **io.Reader/Writer 为什么这么设计?** 单方法接口 → 无数类型能满足 → 文件/网络/内存/压缩/HTTP 用同一套代码处理。小接口组合的典范(design/00)。
- **Read 的契约坑?** 可能同时返回 `n>0` 和 err;要**先处理 n 字节再判 err**;`io.EOF` 是正常结束的哨兵不是错误。
- **io.Copy 怎么工作 / 优化?** 缓冲区从 src 读往 dst 写到 EOF;若 dst 实现 ReaderFrom 或 src 实现 WriterTo 则直接调用(可能零拷贝/sendfile)。
- **怎么流式处理大文件不 OOM?** io.Copy / bufio.Scanner / json.Decoder,别 io.ReadAll;io.LimitReader 设上限。
- **bufio 有什么用?** 缓冲减少系统调用;Scanner 按行/token 读。
- **和 Java 流对比?** java.io 装饰器流(BufferedInputStream 包 FileInputStream)≈ Go bufio.NewReader(file);Go 接口更小、隐式实现。

---

## 7. 一句话总结

> **`io.Reader`(`Read(p []byte)(n,err)`)和 `io.Writer`(`Write`)是两个单方法接口,撑起 Go 所有「字节流」**——文件/网络/内存/压缩/HTTP body 全是 Reader/Writer,凡接受它们的函数(`io.Copy`/`bufio`/`json.Decoder`)一视同仁;层层包装(`bufio(gzip(file))`)就是组合,≈ Java 装饰器流但靠隐式小接口。Read 契约的坑:**可能同时返回 `n>0` 和 err,要先处理 n 再判 err,`io.EOF` 是正常结束的哨兵**。`io.Copy` 对任意源/目的搬运,若实现 ReaderFrom/WriterTo 则走零拷贝。生产上:函数收 `io.Reader` 利于复用与测试、流式处理避免 `io.ReadAll` OOM、bufio 减系统调用、ReadCloser 务必 Close。

下一章 → [`01 net/http`](../01-net-http/README.md):用 io 之上,Go 自带生产级 HTTP server 和 client——中间件怎么写、client 为什么要复用、连接池和超时的坑。｜ 回 [`stdlib` 索引](../README.md)
