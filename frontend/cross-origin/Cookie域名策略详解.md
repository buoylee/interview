# Cookie 域名策略详解

## 问题 1：服务端设置 Cookie 的域名可以自定义吗？

### 简短回答

**可以，但有严格的安全限制**：服务端只能将 Cookie 的域名设置为**当前域名**或**其父域名**，不能设置为其他任意域名。

### 详细说明

#### Set-Cookie 响应头示例

```http
HTTP/1.1 200 OK
Set-Cookie: sessionId=abc123; Domain=.cocorobo.cn; Path=/; Secure; HttpOnly
```

#### 服务端设置 Cookie 的规则

| 当前请求域名 | 可以设置的 Domain | 不可以设置的 Domain |
|-------------|------------------|-------------------|
| `edu.cocorobo.cn` | `.cocorobo.cn` ✅ | `.other.com` ❌ |
| `edu.cocorobo.cn` | `edu.cocorobo.cn` ✅ | `.edu.other.cn` ❌ |
| `edu.cocorobo.cn` | `cocorobo.cn` ✅ | `www.baidu.com` ❌ |
| `cocorobo.cn` | `.cocorobo.cn` ✅ | `.cn` ❌（公共后缀） |
| `localhost` | `localhost` ✅ | `.cocorobo.cn` ❌ |

#### 安全限制原因

**为什么有这个限制？**

如果没有限制，会导致严重的安全问题：

```javascript
// ❌ 假设没有限制（危险场景）
// 恶意网站 evil.com 的服务端响应：
Set-Cookie: sessionId=hacked; Domain=.bank.com

// 结果：用户访问 bank.com 时会带上这个恶意 Cookie
// → 可能导致 Session Fixation 攻击
```

因此浏览器强制要求：**只能设置当前域名或其父域名**。

### 实际案例分析

#### 场景：登录系统

```
用户访问：https://edu.cocorobo.cn/login
登录成功后，服务端响应：

HTTP/1.1 200 OK
Set-Cookie: userId=12345; Domain=.cocorobo.cn; Path=/; Secure; HttpOnly; SameSite=None
```

**Domain 设置分析**：

1. **当前域名**：`edu.cocorobo.cn`
2. **设置的 Domain**：`.cocorobo.cn`（父域名）
3. **结果**：✅ 合法，浏览器接受这个 Cookie

**为什么设置为 `.cocorobo.cn`？**

因为系统有多个子域名需要共享登录态：
- `edu.cocorobo.cn`（教育平台）
- `cloud.cocorobo.cn`（云平台）
- `api.cocorobo.cn`（API 服务）
- `beta.api.cocorobo.cn`（测试 API）

设置 `Domain=.cocorobo.cn` 后，所有 `*.cocorobo.cn` 的子域名都能访问这个 Cookie。

---

## 问题 2：local.cocorobo.cn 和 cocorobo.cn 是跨域的，为什么能获取到 cookies？

### 核心概念区分

这是一个**非常重要但容易混淆**的概念：

**同源策略（Same-Origin Policy）≠ Cookie 域名策略（Cookie Domain Policy）**

这是**两个不同的安全机制**！

### 同源策略 vs Cookie 域名策略

#### 1. 同源策略（Same-Origin Policy）

**定义**：协议、域名、端口**完全相同**才算同源

```javascript
// 判断是否同源
URL1: https://local.cocorobo.cn:8081
URL2: https://cocorobo.cn:8081

协议：https === https ✅
域名：local.cocorobo.cn !== cocorobo.cn ❌
端口：8081 === 8081 ✅

结论：❌ 不同源（跨域）
```

**同源策略限制的内容**：
- ❌ 无法读取对方的 DOM
- ❌ 无法读取对方的 LocalStorage
- ❌ 无法发起 AJAX 请求（除非 CORS 允许）
- ❌ 无法读取对方页面的 JavaScript 变量

**示例**：

```javascript
// 在 local.cocorobo.cn 的页面中
const iframe = document.createElement('iframe');
iframe.src = 'https://cocorobo.cn/page.html';
document.body.appendChild(iframe);

// ❌ 跨域错误：无法访问 iframe 的内容
console.log(iframe.contentWindow.document);
// DOMException: Blocked a frame with origin "https://local.cocorobo.cn"
// from accessing a cross-origin frame.
```

#### 2. Cookie 域名策略（Cookie Domain Policy）

**定义**：Cookie 可以通过 `Domain` 属性实现**父子域共享**

```javascript
Cookie 设置：
  Domain: .cocorobo.cn

可以访问这个 Cookie 的域名：
  ✅ cocorobo.cn
  ✅ www.cocorobo.cn
  ✅ api.cocorobo.cn
  ✅ local.cocorobo.cn
  ✅ beta.api.cocorobo.cn
  ✅ 任何 *.cocorobo.cn 的子域名
```

**Cookie 域名匹配规则**：

| Cookie Domain | 当前页面域名 | 是否发送 Cookie |
|--------------|-------------|----------------|
| `.cocorobo.cn` | `cocorobo.cn` | ✅ 发送 |
| `.cocorobo.cn` | `local.cocorobo.cn` | ✅ 发送 |
| `.cocorobo.cn` | `api.cocorobo.cn` | ✅ 发送 |
| `.cocorobo.cn` | `sub.local.cocorobo.cn` | ✅ 发送 |
| `.cocorobo.cn` | `localhost` | ❌ 不发送 |
| `.cocorobo.cn` | `other.com` | ❌ 不发送 |
| `edu.cocorobo.cn` | `api.cocorobo.cn` | ❌ 不发送（精确匹配） |

### 为什么会有这两个不同的策略？

#### 同源策略的目的

**保护页面内容和脚本不被跨域访问**

```javascript
// 场景：防止恶意网站读取银行网站的内容
// evil.com 的页面：
const iframe = document.createElement('iframe');
iframe.src = 'https://bank.com/account';

// ❌ 同源策略阻止：evil.com 无法读取 bank.com 的 DOM
// 保护了用户的银行账户信息
```

#### Cookie 域名策略的目的

**允许同一组织的多个子域名共享登录态**

```javascript
// 场景：公司有多个子系统需要单点登录（SSO）
// 用户在 login.cocorobo.cn 登录
// 设置 Cookie: Domain=.cocorobo.cn

// ✅ 用户访问 cloud.cocorobo.cn 时自动带上 Cookie，无需重新登录
// ✅ 用户访问 edu.cocorobo.cn 时也自动带上 Cookie
// 实现了单点登录（SSO）
```

### 实际案例分析

#### 案例 1：Google 的多域名登录

```
用户在 accounts.google.com 登录
设置 Cookie: Domain=.google.com

结果：
✅ www.google.com - 搜索服务（已登录）
✅ mail.google.com - Gmail（已登录）
✅ drive.google.com - Google Drive（已登录）
✅ youtube.com - YouTube（需要单独登录，不是 .google.com 的子域）

虽然这些域名之间是"跨域"的（同源策略角度），
但它们都能共享 .google.com 的 Cookie（Cookie 域名策略）
```

#### 案例 2：你的项目

```
登录流程：
1. 用户在 edu.cocorobo.cn 登录
2. 服务端设置：Set-Cookie: sessionId=xxx; Domain=.cocorobo.cn
3. 用户访问 local.cocorobo.cn:8081

同源策略角度：
❌ edu.cocorobo.cn 和 local.cocorobo.cn 是跨域的
  - 无法直接通过 JavaScript 互相访问 DOM
  - 无法直接读取对方的 LocalStorage

Cookie 域名策略角度：
✅ local.cocorobo.cn 匹配 .cocorobo.cn
  - 浏览器会自动在请求中携带 Cookie
  - 可以获取到登录态
```

### 可视化说明

```
┌─────────────────────────────────────────────────────────┐
│                   同源策略（严格）                        │
│                                                         │
│  https://local.cocorobo.cn:8081                        │
│        vs                                               │
│  https://cocorobo.cn:8081                              │
│                                                         │
│  结果：❌ 不同源（域名不同）                              │
│  限制：无法访问 DOM、LocalStorage、直接 AJAX            │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│               Cookie 域名策略（灵活）                      │
│                                                         │
│  Cookie: Domain=.cocorobo.cn                           │
│                                                         │
│  可访问此 Cookie 的域名：                                │
│  ✅ cocorobo.cn                                         │
│  ✅ www.cocorobo.cn                                     │
│  ✅ local.cocorobo.cn                                   │
│  ✅ api.cocorobo.cn                                     │
│  ✅ 任何 *.cocorobo.cn                                  │
│                                                         │
│  结果：✅ 可以获取 Cookie（域名匹配）                     │
└─────────────────────────────────────────────────────────┘
```

### Domain 前缀的含义

#### `.cocorobo.cn` vs `cocorobo.cn`

**历史上的区别**（旧浏览器）：

```javascript
// 带点：Domain=.cocorobo.cn
可访问：cocorobo.cn, www.cocorobo.cn, api.cocorobo.cn

// 不带点：Domain=cocorobo.cn
可访问：仅 cocorobo.cn（不包括子域名）
```

**现代浏览器的行为**：

```javascript
// 根据 RFC 6265，现代浏览器会忽略前导点
Domain=.cocorobo.cn === Domain=cocorobo.cn

// 都表示：cocorobo.cn 及其所有子域名都可以访问
```

**最佳实践**：

```javascript
// 推荐：显式添加前导点（更清晰）
Set-Cookie: sessionId=xxx; Domain=.cocorobo.cn

// 含义明确：包括主域名和所有子域名
```

---

## 常见误区解答

### 误区 1：跨域就完全无法共享数据

**❌ 错误理解**：
"local.cocorobo.cn 和 cocorobo.cn 是跨域的，所以完全无法共享任何数据"

**✅ 正确理解**：
- **同源策略**限制：无法直接访问 DOM、LocalStorage、JavaScript 变量
- **Cookie 域名策略**允许：可以共享 Cookie（如果 Domain 设置正确）
- **CORS** 允许：可以发起跨域 AJAX 请求（如果服务端配置允许）
- **postMessage** 允许：可以通过消息传递通信

### 误区 2：localhost 可以读取任何 Cookie

**❌ 错误理解**：
"我在 localhost 开发，应该可以获取 .cocorobo.cn 的 Cookie"

**✅ 正确理解**：
```javascript
Cookie: Domain=.cocorobo.cn

localhost 是否匹配 .cocorobo.cn？
❌ 不匹配！localhost ≠ *.cocorobo.cn

必须使用：local.cocorobo.cn
✅ 匹配！local.cocorobo.cn ∈ *.cocorobo.cn
```

### 误区 3：设置 Domain=.cn 可以让所有 .cn 网站共享 Cookie

**❌ 错误理解**：
"我设置 Domain=.cn，这样所有 .cn 的网站都能用"

**✅ 正确理解**：
```javascript
// 浏览器会拒绝这个 Cookie
Set-Cookie: sessionId=xxx; Domain=.cn

// 原因：.cn 是公共后缀（Public Suffix）
// 如果允许，会导致严重的安全问题
```

**公共后缀列表（Public Suffix List）**：
- `.com`, `.cn`, `.org` 等顶级域名
- `.co.uk`, `.com.cn` 等二级域名
- 浏览器维护一个[公共后缀列表](https://publicsuffix.org/)
- 不允许为公共后缀设置 Cookie

---

## 实战验证

### 验证 Cookie 域名策略

在浏览器控制台运行：

```javascript
// 1. 查看当前页面的所有 Cookie
console.log('所有 Cookie:', document.cookie);

// 2. 查看详细的 Cookie 信息
// 打开 DevTools → Application → Cookies → 选择域名
// 查看每个 Cookie 的 Domain 属性

// 3. 测试 Cookie 匹配
function testCookieDomain(cookieDomain, currentDomain) {
  // 移除前导点
  const domain = cookieDomain.replace(/^\./, '');

  // 检查是否匹配
  const isExactMatch = currentDomain === domain;
  const isSubdomainMatch = currentDomain.endsWith('.' + domain);

  console.log(`Cookie Domain: ${cookieDomain}`);
  console.log(`Current Domain: ${currentDomain}`);
  console.log(`Match: ${isExactMatch || isSubdomainMatch ? '✅' : '❌'}`);

  return isExactMatch || isSubdomainMatch;
}

// 测试示例
testCookieDomain('.cocorobo.cn', 'local.cocorobo.cn');  // ✅
testCookieDomain('.cocorobo.cn', 'cocorobo.cn');        // ✅
testCookieDomain('.cocorobo.cn', 'localhost');          // ❌
```

### 验证同源策略

```javascript
// 在 local.cocorobo.cn 页面中尝试访问 cocorobo.cn 的内容

// 1. 创建 iframe
const iframe = document.createElement('iframe');
iframe.src = 'https://cocorobo.cn';
document.body.appendChild(iframe);

// 2. 尝试访问 iframe 内容（会被同源策略阻止）
setTimeout(() => {
  try {
    console.log(iframe.contentWindow.document);
    console.log('✅ 可以访问（同源）');
  } catch (e) {
    console.log('❌ 无法访问（跨域）:', e.message);
    // DOMException: Blocked a frame with origin "https://local.cocorobo.cn"
    // from accessing a cross-origin frame.
  }
}, 1000);

// 3. 但是可以发送 postMessage
iframe.contentWindow.postMessage('Hello', 'https://cocorobo.cn');
console.log('✅ postMessage 可以跨域通信');
```

---

## 总结

### 核心要点

1. **服务端设置 Cookie 的域名限制**
   - ✅ 可以设置为当前域名或父域名
   - ❌ 不能设置为其他任意域名
   - ❌ 不能设置为公共后缀（如 .com, .cn）

2. **同源策略 ≠ Cookie 域名策略**
   - 同源策略：严格要求协议、域名、端口完全相同
   - Cookie 域名策略：允许父子域共享（通过 Domain 属性）

3. **local.cocorobo.cn 和 cocorobo.cn**
   - ❌ 不同源（同源策略角度）→ 无法互相访问 DOM
   - ✅ 可以共享 Cookie（Cookie 域名策略）→ `Domain=.cocorobo.cn`

4. **localhost 的特殊性**
   - localhost 是一个独立的域名
   - 不属于任何其他域名的子域
   - 无法获取 .cocorobo.cn 的 Cookie
   - 必须使用 local.cocorobo.cn 等子域名

### 实用图表

```
Cookie 域名层级：

                    .cocorobo.cn (父域)
                          |
        ┌─────────────────┼─────────────────┐
        |                 |                 |
   cocorobo.cn    local.cocorobo.cn   api.cocorobo.cn
                          |
                          |
              sub.local.cocorobo.cn

Cookie: Domain=.cocorobo.cn
所有这些域名都能获取这个 Cookie ✅

localhost
这个域名无法获取 .cocorobo.cn 的 Cookie ❌
```

### 实际应用建议

1. **单点登录（SSO）系统**
   - 使用 `Domain=.your-domain.com`
   - 所有子系统共享登录态

2. **本地开发调试**
   - 使用子域名（如 `local.your-domain.com`）
   - 不要使用 `localhost`（无法获取父域 Cookie）

3. **安全考虑**
   - 敏感 Cookie 添加 `HttpOnly`（防止 JavaScript 读取）
   - HTTPS 下使用 `Secure`（防止中间人攻击）
   - 根据需要设置 `SameSite`（防止 CSRF 攻击）

---

## 参考资料

- [RFC 6265 - HTTP State Management Mechanism](https://tools.ietf.org/html/rfc6265)
- [MDN - Same-origin policy](https://developer.mozilla.org/en-US/docs/Web/Security/Same-origin_policy)
- [MDN - Set-Cookie](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Set-Cookie)
- [Public Suffix List](https://publicsuffix.org/)
