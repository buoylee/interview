# TLS 排查

## 概述

TLS（Transport Layer Security）为网络通信提供加密和认证。当 TLS 出问题时，表现通常是"连不上"或"握手超时"，但背后的原因多种多样：证书过期、证书链不完整、cipher 不匹配、版本不兼容等。本文系统讲解 TLS 握手过程、常见问题排查方法和性能优化。

---

## 一、TLS 握手完整过程

### TLS 1.2 握手（2-RTT）

```
Client                                    Server
  |                                          |
  |--- ClientHello -------------------------→|  RTT 1
  |    (支持的 TLS 版本、cipher suites、       |
  |     随机数 Client Random、SNI)            |
  |                                          |
  |←--- ServerHello -------------------------|
  |    (选定的 cipher suite、随机数            |
  |     Server Random)                       |
  |←--- Certificate -------------------------|
  |    (服务器证书 + 证书链)                    |
  |←--- ServerKeyExchange -------------------|
  |    (ECDHE 参数，用于密钥交换)               |
  |←--- ServerHelloDone --------------------|
  |                                          |
  |--- ClientKeyExchange -------------------→|  RTT 2
  |    (客户端 ECDHE 参数)                     |
  |--- ChangeCipherSpec --------------------→|
  |--- Finished (加密) --------------------→|
  |                                          |
  |←--- ChangeCipherSpec --------------------|
  |←--- Finished (加密) --------------------|
  |                                          |
  |--- Application Data (加密) ---→ ←------|  开始传输
```

### TLS 1.3 握手（1-RTT）

```
Client                                    Server
  |                                          |
  |--- ClientHello -------------------------→|  RTT 1
  |    (支持的 cipher suites、               |
  |     key_share（直接带上 ECDHE 参数）、     |
  |     supported_versions)                  |
  |                                          |
  |←--- ServerHello -------------------------|
  |    (选定的 cipher suite、key_share)       |
  |←--- EncryptedExtensions ----------------|
  |←--- Certificate (加密) ----------------|
  |←--- CertificateVerify (加密) ----------|
  |←--- Finished (加密) -------------------|
  |                                          |
  |--- Finished (加密) --------------------→|  握手完成
  |                                          |
  |--- Application Data (加密) ---→ ←------|  开始传输
```

### TLS 1.3 的关键改进

```
TLS 1.2 vs TLS 1.3：

1. 握手轮次：2-RTT → 1-RTT
   客户端在 ClientHello 中就发送了密钥交换参数
   不需要等服务器先回复再做密钥交换

2. 0-RTT 恢复（PSK + Early Data）
   如果之前连接过，客户端可以用预共享密钥
   在第一个包中就发送应用数据
   → 0 额外延迟
   ⚠ 安全风险：0-RTT 数据可被重放攻击

3. 移除不安全算法
   - 移除 RSA 密钥传输（只保留前向安全的 ECDHE/DHE）
   - 移除 MD5、SHA-1、RC4、DES、3DES
   - 只保留 AEAD 加密模式（如 AES-GCM、ChaCha20-Poly1305）

4. 加密范围扩大
   证书和大部分握手消息都加密传输
   → 防止中间人窥探服务器证书（隐私保护）
```

---

## 二、证书链问题排查

### 基本检查工具

```bash
# 最常用：openssl s_client
openssl s_client -connect example.com:443 -servername example.com

# 输出关键信息：
# Certificate chain
#  0 s:CN = example.com
#    i:C = US, O = Let's Encrypt, CN = R3           ← 中间证书
#  1 s:C = US, O = Let's Encrypt, CN = R3
#    i:O = Digital Signature Trust Co., CN = DST Root CA X3  ← 根证书

# Verify return code: 0 (ok)    ← 验证成功
# 或
# Verify return code: 21 (unable to verify the first certificate) ← 证书链不完整
```

### 证书过期

```bash
# 检查证书有效期
openssl s_client -connect example.com:443 -servername example.com 2>/dev/null | \
  openssl x509 -noout -dates

# 输出：
# notBefore=Jan  1 00:00:00 2024 GMT
# notAfter=Apr  1 00:00:00 2024 GMT   ← 过期时间

# 批量检查多个域名
for domain in api.example.com web.example.com admin.example.com; do
  echo -n "$domain: "
  echo | openssl s_client -connect $domain:443 -servername $domain 2>/dev/null | \
    openssl x509 -noout -enddate
done

# 查看证书详细信息
openssl s_client -connect example.com:443 -servername example.com 2>/dev/null | \
  openssl x509 -noout -text | head -30
```

### 中间证书缺失

```
问题现象：
- 浏览器能访问（浏览器有缓存的中间证书）
- curl / Java / Go 客户端报证书验证失败
- openssl 报 "unable to verify the first certificate"

原因：
  服务器只配了叶子证书，没有配中间证书
  浏览器可以自动下载中间证书（AIA），但大多数程序库不会

诊断：
  openssl s_client -connect example.com:443 的输出中
  Certificate chain 只有一层（只有叶子证书）→ 中间证书缺失
```

```bash
# 修复：在服务器配置中包含完整证书链
# Nginx 示例
# ssl_certificate 应该包含叶子证书 + 中间证书
cat server.crt intermediate.crt > fullchain.crt
# nginx.conf:
# ssl_certificate /etc/nginx/ssl/fullchain.crt;
# ssl_certificate_key /etc/nginx/ssl/server.key;

# 验证证书链是否完整
openssl verify -CAfile /etc/ssl/certs/ca-certificates.crt \
  -untrusted intermediate.crt server.crt
```

### SNI 问题

```
SNI（Server Name Indication）：
  一个 IP 上托管多个 HTTPS 域名时，客户端在 ClientHello 中
  告诉服务器要访问哪个域名，服务器据此选择正确的证书。

问题场景：
  客户端没发 SNI → 服务器返回默认证书 → 域名不匹配 → 验证失败

排查：
```

```bash
# 不发 SNI
openssl s_client -connect 10.0.1.50:443
# 可能返回错误的证书

# 发 SNI
openssl s_client -connect 10.0.1.50:443 -servername api.example.com
# 返回正确的证书

# curl 发 SNI
curl -v --resolve api.example.com:443:10.0.1.50 https://api.example.com/
```

---

## 三、Cipher 协商失败

### 问题诊断

```bash
# 查看服务器支持的 cipher suites
nmap --script ssl-enum-ciphers -p 443 example.com

# 或用 openssl
openssl s_client -connect example.com:443 -cipher 'ECDHE-RSA-AES256-GCM-SHA384'
# 如果成功 → 服务器支持这个 cipher
# 如果失败 → 不支持

# 查看本地 openssl 支持的 ciphers
openssl ciphers -v 'ALL' | head -20

# 查看 TLS 1.3 的 cipher suites
openssl ciphers -v -tls1_3
```

### 常见 Cipher 协商失败原因

```
1. 客户端和服务端没有共同支持的 cipher suite
   - 老客户端只支持 RC4、DES
   - 新服务器已禁用这些不安全的 cipher
   → 解决：升级客户端或在服务器临时开启兼容 cipher

2. TLS 版本不匹配
   - 客户端只支持 TLS 1.0
   - 服务器只接受 TLS 1.2+
   → 解决：升级客户端

3. 证书类型不匹配
   - 服务器证书是 ECDSA 的
   - 客户端的 cipher 列表只有 RSA 相关的
   → 解决：配置双证书（RSA + ECDSA）
```

### 推荐 Cipher 配置

```nginx
# Nginx 推荐配置（2024 年）
ssl_protocols TLSv1.2 TLSv1.3;

# TLS 1.2 cipher suites（按优先级排列）
ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305;

# 服务器优先选择 cipher（而非客户端）
ssl_prefer_server_ciphers on;

# TLS 1.3 cipher suites 由 OpenSSL 自动管理，不需要手动配置
```

---

## 四、TLS 性能影响

### 握手延迟

```
TLS 1.2 握手开销：
  额外 2 个 RTT
  如果 RTT = 50ms → 额外 100ms 延迟

TLS 1.3 握手开销：
  额外 1 个 RTT
  如果 RTT = 50ms → 额外 50ms 延迟

TLS 1.3 0-RTT：
  0 额外延迟（用缓存的 PSK）
```

### CPU 开销

```bash
# RSA vs ECDSA 性能对比（openssl speed）
openssl speed rsa2048
# sign: ~1000 ops/s, verify: ~30000 ops/s

openssl speed ecdsap256
# sign: ~20000 ops/s, verify: ~8000 ops/s

# RSA 签名慢、验证快
# ECDSA 签名快、验证相对慢（但比 RSA 签名快得多）

# 对服务器来说：
# TLS 握手时服务器要做签名 → ECDSA 更快
# RSA-2048 签名 ≈ 1ms
# ECDSA-P256 签名 ≈ 0.05ms
# 差 20 倍！高并发下差异明显
```

### 数据传输加密开销

```
AES-GCM（硬件加速）：
  有 AES-NI 指令集的 CPU 上几乎无开销
  吞吐量接近明文传输

ChaCha20-Poly1305：
  适合没有 AES-NI 的设备（如老的 ARM 处理器）
  纯软件实现也很快

检查 CPU 是否支持 AES-NI：
```

```bash
grep -o aes /proc/cpuinfo | head -1
# 有输出 "aes" → 支持 AES-NI → 使用 AES-GCM
# 无输出 → 不支持 → 考虑使用 ChaCha20-Poly1305
```

---

## 五、会话复用

会话复用避免每次连接都做完整的 TLS 握手，显著降低延迟和 CPU 开销。

### Session ID（TLS 1.2）

```
原理：
  首次握手后，服务器分配一个 Session ID
  下次连接时，客户端带上这个 Session ID
  服务器在内存中查找并恢复会话
  → 跳过密钥交换，只需 1-RTT

缺点：
  服务器需要存储所有 Session 状态
  多台服务器无法共享（除非用 Redis 等共享存储）
  内存占用随连接数线性增长
```

### Session Ticket（TLS 1.2）

```
原理：
  服务器用自己的密钥加密会话状态
  把加密后的 "ticket" 发给客户端保存
  下次连接时客户端带上 ticket
  服务器解密 ticket 恢复会话
  → 服务器不需要存储状态

优点：
  服务器无状态，天然支持多实例
  只需要多台服务器共享 ticket 加密密钥

配置（Nginx）：
```

```nginx
# 启用 Session Ticket
ssl_session_tickets on;
ssl_session_timeout 1d;

# 多台服务器共享同一个 ticket key
ssl_session_ticket_key /etc/nginx/ssl/ticket.key;

# 生成 ticket key（48 字节）
# openssl rand 48 > /etc/nginx/ssl/ticket.key
# 注意：ticket key 需要定期轮换（如每天），否则影响前向安全性
```

### TLS 1.3 PSK 与 0-RTT

```
TLS 1.3 用 PSK（Pre-Shared Key）替代了 Session ID 和 Session Ticket。

PSK 恢复（1-RTT）：
  安全地恢复之前的 TLS 会话
  无安全风险

0-RTT Early Data：
  客户端在 ClientHello 中就携带应用数据
  服务器收到第一个包就可以处理请求
  → 0 额外延迟

⚠ 0-RTT 安全风险：
  Early Data 可以被攻击者捕获并重放
  → 不适合非幂等操作（如支付、转账）
  → 只适合幂等的 GET 请求

  防御措施：
  1. 服务端只接受幂等请求的 0-RTT 数据
  2. 使用 anti-replay 机制（时间窗口 + 一次性令牌）
```

```nginx
# Nginx TLS 1.3 0-RTT 配置
ssl_early_data on;

# 在代理到后端时传递 Early-Data 标志
proxy_set_header Early-Data $ssl_early_data;

# 后端应用检查 Early-Data 头
# 如果 Early-Data: 1，拒绝非幂等请求
```

---

## 六、TLS 排查命令速查

```bash
# 完整 TLS 握手诊断
openssl s_client -connect host:443 -servername hostname -state -debug

# 只看证书链
openssl s_client -connect host:443 -servername hostname -showcerts

# 检查证书有效期
echo | openssl s_client -connect host:443 2>/dev/null | openssl x509 -noout -dates

# 检查证书 SAN（Subject Alternative Names）
echo | openssl s_client -connect host:443 2>/dev/null | \
  openssl x509 -noout -ext subjectAltName

# 测试特定 TLS 版本
openssl s_client -connect host:443 -tls1_2
openssl s_client -connect host:443 -tls1_3

# 测试特定 cipher
openssl s_client -connect host:443 -cipher 'ECDHE-RSA-AES128-GCM-SHA256'

# curl 详细 TLS 信息
curl -vI --tls-max 1.2 https://example.com 2>&1 | grep -E 'TLS|SSL|subject|expire'
```

---

## 总结

TLS 排查的核心知识：

1. **理解握手过程**：知道每一步在做什么，才能定位是哪一步出了问题
2. **证书链必须完整**：浏览器能访问不代表一切正常，要用 `openssl s_client` 验证
3. **TLS 1.3 是正确方向**：更快（1-RTT）、更安全（移除弱算法）、更简单
4. **ECDSA 比 RSA 更快**：新部署的服务优先使用 ECDSA 证书
5. **会话复用很重要**：减少握手次数是降低 TLS 延迟的最有效手段
6. **0-RTT 要谨慎**：只用于幂等请求，必须有重放攻击防护
