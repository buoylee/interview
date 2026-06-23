# 21 · Python↔C 边界

> **为什么这章重要**:numpy/torch 的数组都活在这层;理解它才知道「为什么 `.numpy()` 常免拷贝」「为什么处理大二进制别用 `bytes` 切片」;以及如何用 `ctypes`/`cffi` 直接调原生库做 FFI。**CPython 对象大多是「带头的盒子」,但有一类对象愿意把一段连续内存暴露出来共享——这就是缓冲区协议,零拷贝与 C 互操作都建在它上面。**

## 一、缓冲区协议(buffer protocol)

缓冲区协议是 CPython 内部定义的一套契约:只要一个对象实现了它,就能向消费者暴露「一段连续内存 + 形状/步长/元素类型」,让消费者**直接读写这段内存,而无需拷贝一份**。

实现了缓冲区协议的类型包括:`bytes`、`bytearray`、`array.array`、`memoryview` 本身,以及 numpy/torch 的 ndarray/Tensor。正是因为大家共享这套契约,`memoryview(arr)` 和 `np.asarray(buf)` 才能零拷贝地「接走」底层内存——它们不是在复制数据,而是拿到了同一块内存的视图。

底层:CPython 的 C API 里这套契约叫 `Py_buffer`,包含 `buf`(指针)、`len`、`ndim`、`shape`、`strides`、`format`(元素类型码,如 `"B"` 代表 unsigned char、`"i"` 代表 int32)等字段。`memoryview` 就是把这个 C 结构暴露到 Python 层的薄包装。

## 二、`memoryview`:零拷贝视图

`memoryview` 是处理大缓冲(网络包、文件块、图像帧)的正确姿势。和 `bytes` 切片的关键区别:

```python
buf = bytearray(b"abcdef")
mv = memoryview(buf)      # 不拷贝,view 直接指向 buf 的内存
mv[0:3] = b"XYZ"          # 改 view 即改底层
print(buf)                # bytearray(b'XYZdef')
```

**`bytes` 切片会拷贝,`memoryview` 切片只挪指针/长度**——对大缓冲来说差别是量级级的:

```python
big = bytes(10_000_000)
sub_copy = big[1:]                 # bytes 切片:拷贝约 10MB
sub_view = memoryview(big)[1:]     # memoryview 切片:零拷贝,只挪指针/长度
```

读写权限由底层对象决定:`bytearray` 的 `memoryview` 可读写(如上例);`bytes` 是不可变的,包出来的 `memoryview` 只读——对只读视图赋值会抛 `TypeError`。把大缓冲传给解析函数时,传 `memoryview` 而非 `bytes`/`bytearray`,消费方切片不会产生副本。

## 三、`struct` 与 `array`

### struct:把 Python 值打包成定长二进制

协议解析、文件格式读写都离不开精确的字节布局。`struct` 模块做的就是 Python 值 ↔ 定长二进制的相互转换:

```python
import struct
packed = struct.pack(">Ih", 1, -2)     # 大端:uint32 + int16 → 共 6 字节
print(packed)                          # b'\x00\x00\x00\x01\xff\xfe'
print(struct.unpack(">Ih", packed))    # (1, -2)
```

格式串规则:
- 首字符控字节序:`>` 大端(网络序)、`<` 小端、`=` 原生序、`!` 同 `>`
- 后续字母控元素类型/宽度:`I` = uint32、`h` = int16、`q` = int64、`f` = float32、`d` = float64、`c` = 单字节

两个常用技巧:`struct.calcsize(fmt)` 算出格式对应的字节数,方便验证;复用同一格式串时用 `struct.Struct(fmt)` 预编译,批量 pack/unpack 能省不少时间。

### array:紧凑同质数值数组

`array.array` 是只能存同一类型数值的数组,内存远比 `list` 紧凑:

```python
import array, sys
arr = array.array("i", [1, 2, 3, 1000])  # 紧凑同质 int 数组,连续存原始值
print(arr.itemsize * len(arr))            # 16  —— 4 字节 × 4 个
print(sys.getsizeof([1, 2, 3, 1000]))     # 88  —— list 是指针数组(还没算元素对象本身)
```

`list` 本质是**指针数组**:每个槽存一个指向 PyObject 的指针(8 字节),而每个 PyObject 本身还有对象头(引用计数 + 类型指针,额外占 28 字节起)。`array.array` 连续存原始值——没有逐元素的对象开销,`itemsize` 就是元素的真实字节宽度。

处理大量同质数值且不需要 numpy 时(嵌入式、无依赖脚本),`array.array` 是比 `list` 更经济的选择。它同样实现了缓冲区协议,可以零拷贝传给 `struct`/`socket`/`ctypes`。

## 四、`ctypes`:调 C 动态库

`ctypes` 是标准库自带的 FFI(Foreign Function Interface):无需编写胶水代码、无需编译,就能直接调已有动态库里的 C 函数。

```python
import ctypes
from ctypes.util import find_library

libc = ctypes.CDLL(find_library("c"))   # 跨平台定位 libc(mac: libSystem;linux: libc.so.6)
libc.strlen.restype = ctypes.c_size_t   # 必须显式声明返回/参数类型
libc.strlen.argtypes = [ctypes.c_char_p]
print(libc.strlen(b"hello"))            # 5
print(libc.abs(-7))                     # 7 —— abs 返回/接收 c_int,恰好与 ctypes 默认相符,故可不另设
```

**为什么必须设 `argtypes` / `restype`?** `ctypes` 默认把没有声明的返回值按 C `int`(32 位)处理。如果真实返回值是指针(64 位)或 `size_t`(平台相关),只取低 32 位的结果会截断甚至出错。参数同理——错误的类型声明会传入错误的字节宽度,导致 C 函数读到脏数据,轻则返回错误结果,重则段错误。

常用 ctypes 类型对照:

| C 类型 | ctypes | Python |
|--------|--------|--------|
| `int` | `c_int` | `int` |
| `unsigned int` | `c_uint` | `int` |
| `size_t` | `c_size_t` | `int` |
| `char *` | `c_char_p` | `bytes` |
| `void *` | `c_void_p` | `int` 或 `None` |
| `double` | `c_double` | `float` |

**`cffi` 是更现代的选择**:声明方式贴近 C 头文件(直接粘 C 函数签名字符串),类型更安全,性能更好,且常配合编译生成扩展模块(ABI 模式免编译,API 模式编译一次享全速)。两者主要选型原则:只需调几个现成库函数、不想引入依赖,用 `ctypes`;构建生产级绑定或嵌入 C 库较深,用 `cffi`。

## 五、收口:numpy / torch 的零拷贝原理

`tensor.numpy()`、`np.asarray(buf)` 之所以「常常免拷贝」,根本原因就是缓冲区协议:

- numpy ndarray 和 PyTorch CPU tensor 都实现了 `__array_interface__`/缓冲区协议,暴露的就是底层那段连续内存的指针 + 形状 + dtype。
- `np.asarray(bytearray_or_array)` 调用时 numpy 直接拿这个指针建视图,不拷贝数据;改 numpy 数组,底层 `bytearray` 也随之改变。
- `tensor.numpy()` 在 CPU 同 dtype(float32→float32)、内存连续时同理。

下面这段需安装 numpy(数据/AI 环境一般默认有),故以注释示意——`frombuffer` 不拷贝,直接在原 `bytearray` 上建视图:

```python
# import numpy as np
# a = np.frombuffer(bytearray(b"\x01\x02\x03\x04"), dtype=np.uint8)  # 零拷贝:共享缓冲区
# a[0] = 99   # 改 numpy 数组,底层 bytearray 也跟着变
```

**何时会触发拷贝?** 以下情况缓冲区协议失效或 numpy 主动复制:
- **dtype/步长不匹配**:如把 `array.array("i")` (int32) 用 float64 视图接走——numpy 无法在不改变字节布局的前提下共享,会拷贝并转换。
- **非连续内存**:切片转置等操作产生非连续(strided)数组,再调 `.numpy()` 前需先 `.contiguous()`(PyTorch)否则报错。
- **CPU↔GPU 跨设备**:GPU tensor(`.cuda()`)的内存不在 Python 进程能直接访问的 RAM 里,`.numpy()` 必须先 `.cpu()` 搬回主存——这就是拷贝。

掌握这条逻辑,就能在 numpy/torch 数据管道里判断哪里有隐式拷贝、哪里真正零拷贝,从而有意识地控制内存带宽。

## Java/Go 对照框

| | Java | Go | Python |
|--|------|----|--------|
| 调原生库 | JNI(需编写胶水代码、编译) | cgo(在 Go 文件里嵌 C 注释,需 C 工具链) | `ctypes`/`cffi`(免编译直接调动态库) |
| 直接内存/零拷贝 | `ByteBuffer.allocateDirect`、NIO | `[]byte` 切片(切片操作共享底层数组,无额外拷贝) | 缓冲区协议 + `memoryview` |
| 紧凑数值数组 | `int[]` 原生数组(连续、无装箱) | `[]int`(连续、无装箱) | `array.array` / numpy(对比 `list`:指针数组,每元素是独立对象) |
| 二进制打包 | `ByteBuffer` put/get | `encoding/binary` | `struct.pack` / `struct.unpack` |

## 章末面试卡

**Q1. `memoryview` 解决什么问题?**
`bytes` 切片会复制整段数据;`memoryview` 切片只挪指针和长度,是真正的零拷贝。处理大缓冲(网络包、图像帧、文件块)时,把 `bytes`/`bytearray` 包成 `memoryview` 再传递/切片,省去大量内存分配和复制。底层对象可变(`bytearray`)时 `memoryview` 还支持原地写入。

**Q2. `list` 和 `array.array` 内存差别为什么这么大?**
`list` 是指针数组:每个槽是一个 8 字节的 PyObject 指针,指向的对象本身还有对象头(引用计数 + 类型指针,≥28 字节)。`array.array` 连续存原始值,没有逐元素的对象开销,`itemsize` 就是 C 类型的真实宽度(如 `"i"` 是 4 字节)。千万个整数时差距可以是一个数量级。

**Q3. 用 `ctypes` 调 C 函数,为什么必须设 `argtypes` / `restype`?**
`ctypes` 默认按 C `int`(32 位)处理未声明的返回值。若真实返回类型是 `size_t`、`char *` 等 64 位类型,只截取低 32 位会得到错误或崩溃。参数声明错误则传入错误字节宽度,导致 C 函数读脏数据。正确做法:调用前显式设 `restype` 和 `argtypes`。如果要构建生产级绑定,`cffi` 是更安全、更现代的替代。
