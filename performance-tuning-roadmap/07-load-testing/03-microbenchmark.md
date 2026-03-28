# 微基准测试

## 什么是微基准测试

微基准测试（Microbenchmark）测量的是**一小段代码的性能**——一个方法、一个算法、一种数据结构的操作。与系统级压测不同，微基准测试关注的是纳秒到微秒级别的性能差异。

微基准测试的价值在于：**当你需要在两种实现之间做选择时，用数据说话，而不是靠猜**。

但微基准测试也是最容易写错的测试——编译器优化、JIT 编译、CPU 缓存、分支预测都会让你得到完全不反映真实情况的结果。

---

## 一、Java: JMH 详解

JMH（Java Microbenchmark Harness）是 OpenJDK 官方提供的微基准测试框架，由 JIT 编译器开发者编写，专门解决 JVM 上微基准测试的各种陷阱。

### 基本结构

```java
@BenchmarkMode(Mode.AverageTime)        // 测量模式
@OutputTimeUnit(TimeUnit.NANOSECONDS)    // 输出时间单位
@State(Scope.Thread)                      // 状态作用域
@Warmup(iterations = 5, time = 1)        // 预热：5 次迭代，每次 1 秒
@Measurement(iterations = 10, time = 1)  // 测量：10 次迭代，每次 1 秒
@Fork(2)                                  // 2 个独立 JVM 进程
public class StringConcatBenchmark {

    private String prefix;
    private String suffix;

    @Setup
    public void setup() {
        prefix = "Hello";
        suffix = "World";
    }

    @Benchmark
    public String concatWithPlus() {
        return prefix + " " + suffix;
    }

    @Benchmark
    public String concatWithBuilder() {
        return new StringBuilder()
            .append(prefix).append(" ").append(suffix)
            .toString();
    }

    @Benchmark
    public String concatWithFormat() {
        return String.format("%s %s", prefix, suffix);
    }

    @TearDown
    public void tearDown() {
        // 清理资源
    }
}
```

### 五种测量模式

| 模式 | 含义 | 适用场景 |
|------|------|---------|
| `Mode.Throughput` | 每秒操作数 (ops/s) | 吞吐量对比 |
| `Mode.AverageTime` | 平均每次操作耗时 | 延迟对比 |
| `Mode.SampleTime` | 采样延迟分布（含百分位） | 需要看长尾 |
| `Mode.SingleShotTime` | 单次执行时间（不预热） | 测量冷启动性能 |
| `Mode.All` | 以上全部 | 全面分析 |

### 关键注解说明

- **`@Fork(N)`**：启动 N 个独立 JVM 进程。每个 fork 都有独立的 JIT 编译过程，避免单次运行的 JIT 偏差。设为 1 以上。
- **`@Warmup`**：让 JIT 编译器有足够时间完成热点代码编译。预热不充分会测到解释执行的性能。
- **`@State(Scope.Thread)`**：每个线程有自己的状态实例，避免竞争。`Scope.Benchmark` 则所有线程共享。

### 运行 JMH

```bash
# Maven 项目中添加依赖
# pom.xml:
# <dependency>
#   <groupId>org.openjdk.jmh</groupId>
#   <artifactId>jmh-core</artifactId>
#   <version>1.37</version>
# </dependency>

# 构建并运行
mvn clean package
java -jar target/benchmarks.jar

# 只运行特定 benchmark
java -jar target/benchmarks.jar StringConcatBenchmark

# 输出 JSON 结果
java -jar target/benchmarks.jar -rf json -rff results.json
```

### JMH 陷阱与应对

#### 陷阱 1：死代码消除（Dead Code Elimination）

JIT 编译器会发现计算结果没人用，直接把整段代码优化掉。

```java
// 错误写法 — JIT 会消除这段代码
@Benchmark
public void wrong() {
    Math.log(42);  // 返回值没人用，JIT 直接删掉
}

// 正确写法 1 — 返回结果
@Benchmark
public double right_return() {
    return Math.log(42);
}

// 正确写法 2 — 用 Blackhole 消费
@Benchmark
public void right_blackhole(Blackhole bh) {
    bh.consume(Math.log(42));
}
```

#### 陷阱 2：常量折叠（Constant Folding）

JIT 发现输入是常量，直接把结果在编译时算好了。

```java
// 错误写法 — JIT 直接算出 Math.log(42) 的结果
@Benchmark
public double wrong() {
    return Math.log(42);  // 编译期就能确定结果
}

// 正确写法 — 从 @State 字段读取
@State(Scope.Thread)
public static class MyState {
    double x = 42;
}

@Benchmark
public double right(MyState state) {
    return Math.log(state.x);  // JIT 无法在编译期确定 state.x 的值
}
```

#### 陷阱 3：循环优化

JIT 会对循环做向量化、展开等优化，让循环里的计算看起来"免费"。

```java
// 错误写法 — 不要自己写循环
@Benchmark
public int wrong() {
    int sum = 0;
    for (int i = 0; i < 1000; i++) {
        sum += i;  // JIT 可能直接算出 sum = 499500
    }
    return sum;
}

// 正确做法：让 JMH 控制迭代次数（通过 @Measurement 配置）
// 每个 @Benchmark 方法只做一次操作
```

---

## 二、Go: testing.B 与 benchstat

Go 标准库内置 benchmark 支持，简洁实用。

### 编写 Benchmark

```go
// sort_benchmark_test.go
package sort

import (
    "math/rand"
    "sort"
    "testing"
)

func BenchmarkBubbleSort(b *testing.B) {
    for i := 0; i < b.N; i++ {
        b.StopTimer()
        data := rand.Perm(1000) // 数据准备不计入计时
        b.StartTimer()
        bubbleSort(data)
    }
}

func BenchmarkStdSort(b *testing.B) {
    for i := 0; i < b.N; i++ {
        b.StopTimer()
        data := rand.Perm(1000)
        b.StartTimer()
        sort.Ints(data)
    }
}

// 子 benchmark：测试不同规模
func BenchmarkSort(b *testing.B) {
    sizes := []int{100, 1000, 10000}
    for _, size := range sizes {
        b.Run(fmt.Sprintf("size=%d", size), func(b *testing.B) {
            for i := 0; i < b.N; i++ {
                b.StopTimer()
                data := rand.Perm(size)
                b.StartTimer()
                sort.Ints(data)
            }
        })
    }
}
```

```bash
# 运行 benchmark
go test -bench=. -benchmem -count=10 ./... > old.txt

# 参数说明：
# -bench=.       运行所有 benchmark
# -benchmem      报告内存分配
# -count=10      运行 10 次用于统计

# 输出示例：
# BenchmarkBubbleSort-8    1234    967352 ns/op    8192 B/op    1 allocs/op
# BenchmarkStdSort-8       15678    76543 ns/op    4096 B/op    1 allocs/op
```

### benchstat 统计对比

```bash
# 安装 benchstat
go install golang.org/x/perf/cmd/benchstat@latest

# 优化前跑 10 次
go test -bench=BenchmarkSort -count=10 ./... > old.txt

# 优化后跑 10 次
go test -bench=BenchmarkSort -count=10 ./... > new.txt

# 对比
benchstat old.txt new.txt
```

```
name          old time/op    new time/op    delta
Sort/size=1000  76.5µs ± 3%   45.2µs ± 2%   -40.92% (p=0.000 n=10+10)
Sort/size=10000 1.23ms ± 4%   0.89ms ± 3%   -27.64% (p=0.000 n=10+10)
```

**p-value 判断显著性**：
- `p < 0.05`：差异具有统计显著性，优化真的有效
- `p > 0.05`：差异不显著，可能只是噪音
- `n=10+10`：表示两组各 10 个有效样本

---

## 三、Python: pytest-benchmark

```python
# test_performance.py
import json

def serialize_with_json(data):
    return json.dumps(data)

def serialize_with_ujson(data):
    import ujson
    return ujson.dumps(data)

# 使用 benchmark fixture
def test_json_serialize(benchmark):
    data = {"users": [{"name": f"user_{i}", "age": i} for i in range(100)]}
    result = benchmark(serialize_with_json, data)
    assert result is not None

def test_ujson_serialize(benchmark):
    data = {"users": [{"name": f"user_{i}", "age": i} for i in range(100)]}
    result = benchmark(serialize_with_ujson, data)
    assert result is not None

# 使用 pedantic 模式获取更精确的结果
def test_json_precise(benchmark):
    data = {"key": "value"}
    benchmark.pedantic(serialize_with_json, args=(data,),
                       rounds=1000, warmup_rounds=100)
```

```bash
# 运行
pip install pytest-benchmark
pytest test_performance.py --benchmark-only

# 输出示例：
# -------------------- benchmark: 2 tests --------------------
# Name                    Min      Max     Mean    StdDev   Median     IQR
# test_json_serialize   45.2µs   89.3µs  52.1µs   5.2µs   50.8µs   4.1µs
# test_ujson_serialize  12.1µs   25.4µs  14.3µs   2.1µs   13.9µs   1.8µs

# 保存基线并对比
pytest test_performance.py --benchmark-save=baseline
# 优化后
pytest test_performance.py --benchmark-compare=0001_baseline
```

---

## 四、跨语言共同陷阱与最佳实践

### 共同陷阱

| 陷阱 | Java | Go | Python |
|------|------|----|--------|
| 编译器优化消除代码 | JIT 死代码消除 | 编译器内联消除 | 较少（解释执行） |
| 预热不足 | JIT 未完成编译 | 首次 GC 干扰 | import 延迟 |
| 测量了准备工作 | Setup 写在 Benchmark 里 | StopTimer/StartTimer 遗漏 | 数据构造计入时间 |
| 单次运行就下结论 | 没有 @Fork | 没有 -count | 没有足够 rounds |
| 忽略内存分配 | 只看时间不看 GC | 没用 -benchmem | 没关注对象创建 |

### 最佳实践

1. **多次运行取统计值**：单次结果毫无意义。Java 用 `@Fork(2+)`，Go 用 `-count=10`，Python 用足够的 rounds。

2. **隔离测量目标**：只测你想测的代码，数据准备、初始化等开销不要算在内。

3. **注意环境干扰**：关闭不必要的后台程序，固定 CPU 频率（禁用 turbo boost），避免在笔记本电脑上跑关键 benchmark。

4. **对比而非绝对值**：微基准测试的绝对数字受环境影响大，有意义的是**同一环境下的对比**。

5. **不要过度优化微基准**：微基准测试显示方案 A 比方案 B 快 5 纳秒，但在真实系统中这个方法每秒只被调用 100 次——这 5 纳秒完全不值得牺牲可读性。

```
微基准测试的正确用法：
  ✓ 比较两种数据结构在特定操作上的性能
  ✓ 验证算法优化是否有效
  ✓ 确认性能回归

  ✗ 用纳秒级差异来指导架构决策
  ✗ 脱离真实场景的纯理论对比
  ✗ 只看速度不看内存 / GC 影响
```

---

## 总结

微基准测试是性能工程的显微镜——当你需要精确测量一小段代码的性能时，它是不可替代的工具。但和显微镜一样，如果不知道怎么正确使用，看到的东西可能完全是假象。

关键记住：**预热充分、消除编译器优化干扰、多次运行取统计值、用数据对比而非绝对值下结论**。
