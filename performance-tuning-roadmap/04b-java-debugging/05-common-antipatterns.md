# Java 常见性能反模式

## 概述

性能问题的 80% 来自应用代码本身，而不是 JVM 参数或基础设施。本文汇总 Java 后端开发中最常见的性能反模式，每个反模式都附带问题代码、修复方案和性能数据，帮助你在 Code Review 和性能排查中快速识别问题。

---

## 1. 字符串拼接

### 问题

```java
// 反模式：循环中用 + 拼接字符串
public String buildReport(List<Record> records) {
    String result = "";
    for (Record record : records) {
        result += record.toString() + "\n";  // 每次拼接都创建新的 String 对象
    }
    return result;
}
// 1000 条记录：创建约 1000 个临时 String 和 StringBuilder 对象
// 10000 条记录：严重的 GC 压力，且时间复杂度为 O(n^2)
```

### 修复

```java
// 正确做法：使用 StringBuilder
public String buildReport(List<Record> records) {
    StringBuilder sb = new StringBuilder(records.size() * 64);  // 预估容量
    for (Record record : records) {
        sb.append(record.toString()).append('\n');
    }
    return sb.toString();
}
```

### JDK 9+ 的 invokedynamic 优化

```java
// JDK 9+ 使用 invokedynamic 优化字符串拼接
// 简单的非循环拼接可以放心用 +
String greeting = "Hello, " + name + "! Welcome to " + city;
// JDK 9+ 编译器会使用 StringConcatFactory 处理
// 性能与 StringBuilder 持平，代码更简洁

// 但循环中仍然必须用 StringBuilder！
// JDK 的 invokedynamic 优化只针对单条语句的拼接
```

---

## 2. 正则回溯

### 灾难性回溯

```java
// 危险正则：嵌套量词导致指数级回溯
Pattern pattern = Pattern.compile("(a+)+b");
// 输入 "aaaaaaaaaaaaaaaaac"
// 回溯次数随 a 的数量指数增长，可能导致 CPU 100% 甚至应用卡死

// 另一个真实案例：验证邮箱
Pattern emailPattern = Pattern.compile("^([a-zA-Z0-9]+\\.?)+@[a-zA-Z0-9]+\\.[a-zA-Z]+$");
// 输入 "aaaaaaaaaaaaaaaaaaaaa@" → 灾难性回溯
```

### 检测方法

```java
// 方法一：设置匹配超时（JDK 没有内置超时，需要手动实现）
ExecutorService executor = Executors.newSingleThreadExecutor();
Future<Boolean> future = executor.submit(() -> pattern.matcher(input).matches());
try {
    boolean result = future.get(1, TimeUnit.SECONDS);  // 1 秒超时
} catch (TimeoutException e) {
    future.cancel(true);
    log.warn("Regex timeout for input: {}", input.substring(0, 50));
}

// 方法二：使用在线工具测试
// https://regex101.com/ → 显示回溯次数

// 方法三：async-profiler CPU 模式
// 如果看到 java.util.regex.Pattern$xxx 占用大量 CPU，就是正则问题
```

### 避免方法

```java
// 1. 避免嵌套量词：(a+)+ → a+
// 2. 使用原子组或占有量词（防止回溯）
Pattern safe = Pattern.compile("(?>a+)b");  // 原子组
Pattern safe2 = Pattern.compile("a++b");    // 占有量词

// 3. 预编译正则（避免重复编译）
// 反模式：
public boolean validate(String input) {
    return input.matches("\\d{4}-\\d{2}-\\d{2}");  // 每次调用都编译正则
}

// 正确做法：
private static final Pattern DATE_PATTERN = Pattern.compile("\\d{4}-\\d{2}-\\d{2}");
public boolean validate(String input) {
    return DATE_PATTERN.matcher(input).matches();
}

// 4. 对于简单的字符串检查，优先用 String 方法代替正则
input.contains("keyword")       // 代替 Pattern.compile(".*keyword.*")
input.startsWith("prefix")      // 代替 Pattern.compile("^prefix.*")
input.endsWith(".txt")           // 代替 Pattern.compile(".*\\.txt$")
```

---

## 3. 序列化开销

### 性能对比

```
序列化框架性能对比（100 万次序列化一个中等大小的 POJO）：

| 框架       | 序列化时间 | 反序列化时间 | 序列化大小 |
|-----------|-----------|------------|-----------|
| Protobuf  | 1x (基准)  | 1x (基准)   | 1x (最小)  |
| Jackson    | 3-5x      | 3-5x       | 2-3x       |
| Gson       | 5-8x      | 5-8x       | 2-3x       |
| JDK 序列化  | 10-20x    | 10-20x     | 5-10x      |
```

### 实用建议

```java
// 1. Jackson ObjectMapper 必须复用（线程安全）
// 反模式：
String json = new ObjectMapper().writeValueAsString(obj);  // 每次创建新的！

// 正确：
private static final ObjectMapper MAPPER = new ObjectMapper();
String json = MAPPER.writeValueAsString(obj);

// 2. 对性能敏感的内部通信，考虑 Protobuf
// 3. Jackson 性能调优
ObjectMapper mapper = new ObjectMapper();
mapper.configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false);
mapper.configure(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS, true);
// 使用 afterburner 模块加速（通过字节码生成避免反射）
mapper.registerModule(new AfterburnerModule());
```

---

## 4. 连接泄漏

### 数据库连接泄漏

```java
// 反模式：忘记关闭连接
public User getUser(long id) {
    Connection conn = dataSource.getConnection();
    PreparedStatement ps = conn.prepareStatement("SELECT * FROM users WHERE id = ?");
    ps.setLong(1, id);
    ResultSet rs = ps.executeQuery();
    if (rs.next()) {
        return mapToUser(rs);
    }
    return null;
    // conn 没有关闭！每次调用都泄漏一个连接
    // 最终连接池耗尽，所有新请求阻塞在 getConnection()
}

// 正确做法：try-with-resources
public User getUser(long id) {
    try (Connection conn = dataSource.getConnection();
         PreparedStatement ps = conn.prepareStatement("SELECT * FROM users WHERE id = ?")) {
        ps.setLong(1, id);
        try (ResultSet rs = ps.executeQuery()) {
            if (rs.next()) {
                return mapToUser(rs);
            }
        }
    }  // 自动关闭 conn 和 ps
    return null;
}
```

### HTTP 连接泄漏

```java
// 反模式：HttpURLConnection 忘记断开
HttpURLConnection conn = (HttpURLConnection) new URL(url).openConnection();
InputStream is = conn.getInputStream();
String result = IOUtils.toString(is, "UTF-8");
// is 和 conn 都没关闭

// 正确做法：
try {
    HttpURLConnection conn = (HttpURLConnection) new URL(url).openConnection();
    conn.setConnectTimeout(5000);
    conn.setReadTimeout(10000);
    try (InputStream is = conn.getInputStream()) {
        return IOUtils.toString(is, "UTF-8");
    }
} finally {
    conn.disconnect();
}

// 更好的做法：使用 OkHttp 或 Apache HttpClient 自带连接池管理
```

### 连接泄漏检测

```bash
# HikariCP 连接泄漏检测
spring.datasource.hikari.leak-detection-threshold=60000  # 60 秒未归还视为泄漏

# 日志中会出现：
# WARN  HikariPool - Connection leak detection triggered for conn0,
# stack trace follows
# java.lang.Exception: Apparent connection leak detected
#     at com.example.dao.UserDao.getUser(UserDao.java:23)
#     at com.example.service.UserService.findById(UserService.java:45)
```

---

## 5. N+1 查询

### 问题

```java
// ORM（如 JPA/Hibernate）的典型 N+1 问题
// 查询所有订单（1 条 SQL）
List<Order> orders = orderRepository.findAll();
// 每个订单访问关联的用户（N 条 SQL）
for (Order order : orders) {
    System.out.println(order.getUser().getName());
    // 每次 getUser() 都触发一条 SELECT * FROM users WHERE id = ?
}
// 如果有 100 个订单 → 1 + 100 = 101 条 SQL

// 实际 SQL 执行：
// SELECT * FROM orders                          -- 第 1 条
// SELECT * FROM users WHERE id = 1              -- 第 2 条
// SELECT * FROM users WHERE id = 2              -- 第 3 条
// ...                                           -- ...
// SELECT * FROM users WHERE id = 100            -- 第 101 条
```

### 修复

```java
// 方案一：JOIN FETCH（JPA）
@Query("SELECT o FROM Order o JOIN FETCH o.user")
List<Order> findAllWithUser();
// 一条 SQL：SELECT o.*, u.* FROM orders o JOIN users u ON o.user_id = u.id

// 方案二：@EntityGraph
@EntityGraph(attributePaths = {"user"})
List<Order> findAll();

// 方案三：批量 IN 查询（手动）
List<Order> orders = orderRepository.findAll();
Set<Long> userIds = orders.stream().map(Order::getUserId).collect(Collectors.toSet());
Map<Long, User> userMap = userRepository.findAllById(userIds).stream()
    .collect(Collectors.toMap(User::getId, Function.identity()));
// 只有 2 条 SQL：SELECT * FROM orders + SELECT * FROM users WHERE id IN (1,2,3,...)

// 方案四：Hibernate 批量抓取
@BatchSize(size = 50)  // 每次批量加载 50 个关联对象
@ManyToOne(fetch = FetchType.LAZY)
private User user;
```

### 检测

```bash
# 1. 开启 Hibernate SQL 日志
spring.jpa.show-sql=true
spring.jpa.properties.hibernate.format_sql=true

# 2. 使用 p6spy 拦截 SQL 并统计
# 3. 使用 Arthas trace 看 DAO 层方法被调用了多少次
[arthas@12345]$ monitor com.example.dao.UserDao findById -c 10
```

---

## 6. 日志性能陷阱

### 问题

```java
// 反模式1：高频代码中不检查日志级别
for (Order order : hugeList) {
    // 即使 DEBUG 级别关闭，toString() 仍然会被执行！
    logger.debug("Processing order: " + order.toString());
}

// 反模式2：复杂对象拼接
logger.debug("Request details: " + request.getHeaders() + ", body: " + request.getBody());
// getHeaders() 和 getBody() 可能涉及复杂计算或大对象序列化
```

### 修复

```java
// 方案一：参数化日志（SLF4J {}）
logger.debug("Processing order: {}", order.getId());
// 只有在 DEBUG 启用时才会调用 order.getId() 和格式化

// 方案二：isDebugEnabled 检查（复杂参数场景）
if (logger.isDebugEnabled()) {
    logger.debug("Request details: {}, body: {}",
        request.getHeaders(), request.getBody());
}

// 方案三：使用 Supplier（Log4j2 / SLF4J 2.0）
logger.debug("Expensive computation result: {}", () -> expensiveMethod());
// Supplier 只在日志级别满足时才执行
```

### 异步日志

```xml
<!-- Logback 异步 Appender -->
<appender name="ASYNC" class="ch.qos.logback.classic.AsyncAppender">
    <queueSize>1024</queueSize>           <!-- 队列大小 -->
    <discardingThreshold>0</discardingThreshold>  <!-- 0=不丢弃 -->
    <neverBlock>true</neverBlock>         <!-- 队列满时不阻塞，丢弃日志 -->
    <appender-ref ref="FILE" />
</appender>

<!-- 注意：neverBlock=true 意味着极端情况下会丢日志
     如果不能丢日志，设 neverBlock=false，但要注意队列满时会阻塞业务线程 -->
```

---

## 7. 大对象分配

### 问题

```java
// 大对象直接进入 Old Gen（G1 中超过 Region 50% 为 Humongous 对象）
// 触发 Full GC 的常见原因

// 反模式1：一次性加载大量数据到内存
List<Record> allRecords = repository.findAll();  // 可能返回百万条记录
byte[] allBytes = IOUtils.toByteArray(inputStream);  // 可能是几百 MB 的文件

// 反模式2：大数组作为临时缓冲
byte[] buffer = new byte[10 * 1024 * 1024];  // 10MB 临时缓冲
```

### 修复

```java
// 方案一：流式处理，避免全量加载
// 数据库：使用游标或分页
try (Stream<Record> stream = repository.streamAll()) {
    stream.forEach(record -> process(record));
}

// 文件：流式读取
try (BufferedReader reader = Files.newBufferedReader(path)) {
    String line;
    while ((line = reader.readLine()) != null) {
        process(line);
    }
}

// 方案二：复用缓冲区
// 使用对象池（如 Netty 的 ByteBuf pool）
// 或使用 ThreadLocal 复用
private static final ThreadLocal<byte[]> BUFFER = ThreadLocal.withInitial(() -> new byte[8192]);
```

---

## 8. 反射开销

### 问题

```java
// 反射调用比直接调用慢 5-50 倍
// 反模式：在热路径上频繁使用反射
public Object getValue(Object obj, String fieldName) {
    Field field = obj.getClass().getDeclaredField(fieldName);  // 每次查找字段
    field.setAccessible(true);                                  // 每次设置可访问
    return field.get(obj);                                      // 反射读取
}
```

### 修复

```java
// 方案一：缓存 Field/Method 对象
private static final Map<String, Field> FIELD_CACHE = new ConcurrentHashMap<>();

public Object getValue(Object obj, String fieldName) {
    Field field = FIELD_CACHE.computeIfAbsent(
        obj.getClass().getName() + "." + fieldName,
        key -> {
            try {
                Field f = obj.getClass().getDeclaredField(fieldName);
                f.setAccessible(true);
                return f;
            } catch (NoSuchFieldException e) {
                throw new RuntimeException(e);
            }
        });
    return field.get(obj);
}

// 方案二：使用 MethodHandle（JDK 7+，比反射更快）
MethodHandle handle = MethodHandles.lookup()
    .findVirtual(MyClass.class, "getName", MethodType.methodType(String.class));
String name = (String) handle.invoke(obj);

// 方案三：使用 LambdaMetafactory（最快，接近直接调用性能）
// 适合大量重复调用同一方法的场景

// 方案四：如果可能，直接用接口代替反射
// 反射通常是设计问题的信号
```

### 性能数据

```
方法调用方式性能对比（JMH，单次调用）：
直接调用:           ~2 ns
缓存的 Method.invoke: ~20 ns
未缓存的反射:         ~500 ns（包含 getDeclaredField 查找）
MethodHandle:        ~5 ns（warmup 后接近直接调用）
```

---

## 快速检查清单

在 Code Review 时，检查以下反模式：

```
[ ] 循环中是否有字符串 + 拼接？
[ ] 正则表达式是否有嵌套量词？是否预编译？
[ ] ObjectMapper 是否全局复用？
[ ] 数据库/HTTP 连接是否用 try-with-resources 关闭？
[ ] ORM 查询是否有 N+1 问题？
[ ] 高频日志是否用参数化格式 {}？
[ ] 是否一次性加载大量数据到内存？
[ ] 热路径上是否有未缓存的反射调用？
```

---

## 小结

| 反模式 | 影响 | 修复 |
|--------|------|------|
| 循环字符串 + 拼接 | O(n^2) 时间，大量临时对象 | StringBuilder + 预估容量 |
| 正则灾难性回溯 | CPU 100%，应用卡死 | 避免嵌套量词，使用占有量词 |
| 重复创建 ObjectMapper | CPU 浪费，GC 压力 | 静态常量复用 |
| 连接泄漏 | 连接池耗尽，请求阻塞 | try-with-resources |
| N+1 查询 | 数据库压力倍增 | JOIN FETCH / 批量 IN |
| 日志参数先计算 | 无意义的 CPU 消耗 | 参数化日志 {} |
| 大对象分配 | 触发 Full GC | 流式处理，复用缓冲区 |
| 反射未缓存 | 热路径性能损耗 | 缓存 Field/Method，或用 MethodHandle |
