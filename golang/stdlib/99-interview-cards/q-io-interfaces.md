# io 接口家族:Reader/Writer/Copy

## 一句话回答

`io.Reader`(`Read(p []byte)(n,err)`)和 `io.Writer`(`Write`)是两个**单方法接口**,撑起 Go 所有「字节流」——文件/网络/内存/压缩/HTTP body 全是 Reader/Writer,凡接受它们的函数(`io.Copy`/`bufio`/`json.Decoder`)一视同仁;层层包装(`bufio.NewReader(gzip.NewReader(file))`)就是组合(≈ Java 装饰器流,但靠隐式小接口)。这是「小接口组合」哲学的标准库范本。

## Read 契约坑

```go
n, err := r.Read(buf)
if n > 0 { process(buf[:n]) }    // 可能同时返回 n>0 和 err,先处理已读数据
if err == io.EOF { break }       // io.EOF 是正常结束的哨兵,不是错误
if err != nil { return err }
```

## io.Copy

`io.Copy(dst, src)` 缓冲搬运到 EOF;若 dst 实现 `ReaderFrom` 或 src 实现 `WriterTo` 则直接调用(可能零拷贝/sendfile)。流式处理大数据(避免 `io.ReadAll` OOM)的主力。

## 证据链接

- 正文:[`00 io 接口家族`](../00-io/README.md);接口设计 [`design/00`](../../design/00-interface-design/README.md);io.EOF [`error-handling/01`](../../error-handling/01-error-values/README.md)

## 易追问的延伸

- **怎么流式不 OOM?** io.Copy / bufio.Scanner / json.Decoder,别 io.ReadAll;io.LimitReader 设上限。
- **bufio 作用?** 缓冲减系统调用;Scanner 按行/token(默认行上限 64KB)。
- **常用组合件?** MultiReader/MultiWriter、TeeReader、LimitReader、io.Discard。
- **为什么函数收 io.Reader 更好?** 文件/网络/内存/strings.Reader 都能传,利复用 + 可测(testing/01)。
