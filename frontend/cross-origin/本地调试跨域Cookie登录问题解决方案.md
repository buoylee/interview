# 本地调试跨域 Cookie 登录问题解决方案

## 问题背景

在本地开发环境中需要测试真实的用户登录流程，但遇到了跨域 Cookie 无法传递的问题：

- **前端地址**：`http://localhost:8081`
- **登录 iframe**：`https://edu.cocorobo.cn/course/login?type=2`
- **登录验证 API**：`https://beta.api.cocorobo.cn/api/getcookieuserid`
- **Cookie 域名**：`.cocorobo.cn`

## 问题现象

1. 用户在登录页面登录成功
2. 登录页面没有消失，停留在登录界面
3. `/api/getcookieuserid` 接口持续返回 **401 Unauthorized**
4. 浏览器控制台没有明显错误

## 问题分析

### 根本原因

**浏览器的同源策略导致跨域 Cookie 无法传递**

登录流程中涉及三个域名：
1. 前端页面：`localhost:8081`
2. 登录 iframe：`edu.cocorobo.cn`
3. 验证 API：`beta.api.cocorobo.cn`

登录 iframe 设置的 Cookie 域名是 `.cocorobo.cn`，但前端运行在 `localhost`，浏览器不会将 `.cocorobo.cn` 域的 Cookie 发送给 `localhost`，导致验证接口无法获取登录态。

### 关键知识点

#### 1. Cookie 的域名限制

```
登录 iframe 设置的 Cookie：
  Domain: .cocorobo.cn
  Path: /
  Secure: true
  SameSite: None

浏览器规则：
  - localhost 无法读取 .cocorobo.cn 域的 Cookie
  - 只有 *.cocorobo.cn 的域名才能读取这个 Cookie
```

#### 2. 为什么代理无法解决问题

即使配置了 webpack-dev-server 代理：

```javascript
proxy: {
  '/api/getcookieuserid': {
    target: 'https://beta.api.cocorobo.cn',
    changeOrigin: true
  }
}
```

**这只能解决 API 请求的跨域问题，无法解决 Cookie 域名不匹配的问题**。

因为：
- 前端页面在 `localhost` 打开
- 登录 iframe 设置的 Cookie 域名是 `.cocorobo.cn`
- 浏览器根据页面的域名（localhost）决定发送哪些 Cookie
- `localhost` 和 `.cocorobo.cn` 域名不匹配，Cookie 不会被发送

## 解决方案

### 完整方案：HTTPS + 本地域名 + 证书

要完全模拟线上环境，需要满足以下条件：

1. ✅ 使用 HTTPS 协议（因为 Cookie 有 Secure 标志）
2. ✅ 使用 `.cocorobo.cn` 子域名（才能读取 Cookie）
3. ✅ 配置 SSL 证书（HTTPS 需要）
4. ✅ 配置代理绕过限制（Shadowrocket 等代理工具）

### 实施步骤

#### 步骤 1：安装 mkcert 并生成本地证书

```bash
# 安装 mkcert（macOS）
brew install mkcert

# 安装本地 CA
mkcert -install

# 生成证书（在项目根目录）
cd /path/to/your/project
mkcert local.cocorobo.cn localhost 127.0.0.1

# 会生成两个文件：
# - local.cocorobo.cn+2-key.pem（私钥）
# - local.cocorobo.cn+2.pem（证书）
```

#### 步骤 2：配置 hosts 文件

```bash
# 编辑 hosts 文件
sudo nano /etc/hosts

# 添加以下内容：
127.0.0.1  local.cocorobo.cn
```

#### 步骤 3：配置 vue.config.js

```javascript
// vue.config.js
module.exports = {
  devServer: {
    host: '0.0.0.0',
    port: 8081,
    allowedHosts: 'all',

    // HTTPS 配置
    https: (() => {
      const fs = require('fs');
      const keyPath = './local.cocorobo.cn+2-key.pem';
      const certPath = './local.cocorobo.cn+2.pem';

      if (fs.existsSync(keyPath) && fs.existsSync(certPath)) {
        console.log('✅ 检测到 HTTPS 证书，启用 HTTPS 模式');
        return {
          key: fs.readFileSync(keyPath),
          cert: fs.readFileSync(certPath),
        };
      } else {
        console.warn('⚠️  未找到 HTTPS 证书，使用 HTTP 模式');
        return false;
      }
    })(),

    // 代理配置（可选，用于跨域 API 请求）
    proxy: {
      '/api/getcookieuserid': {
        target: 'https://beta.api.cocorobo.cn',
        changeOrigin: true,
        secure: false,
        cookieDomainRewrite: {
          '*': ''
        },
        onProxyReq: function(proxyReq, req, res) {
          console.log('🔄 代理请求:', req.url);
        },
        onProxyRes: function(proxyRes, req, res) {
          const setCookieHeaders = proxyRes.headers['set-cookie'];
          if (setCookieHeaders) {
            proxyRes.headers['set-cookie'] = setCookieHeaders.map(cookie => {
              return cookie
                .replace(/; Secure/gi, '')
                .replace(/; SameSite=\w+/gi, '');
            });
          }
          console.log('✅ 代理响应:', req.url, '状态码:', proxyRes.statusCode);
        }
      }
    }
  }
}
```

#### 步骤 4：配置前端代码支持本地测试

在 `created()` 生命周期中添加本地测试分支：

```javascript
// dialogMode.vue
created() {
  const url = window.location.href;
  const isLocalEnv = url.includes('localhost') || url.includes('192.168');
  const testRealLogin = this.getUrlParams(url)["testRealLogin"] === 'true';

  // 本地测试模式：使用测试用户数据
  if (isLocalEnv && !testRealLogin) {
    console.log('🔧 本地测试模式：使用测试用户数据');

    this.user = {
      userId: 'test-user-id',
      userName: 'testUser',
      organizeid: 'test-org-id',
      org: '',
      classid: 'test-class-001'
    };

    this.$store.commit('set_user', this.user);
    this.isLogin = true;

    // 初始化并加载数据...
    return; // 跳过登录流程
  }

  // 测试真实登录流程
  if (isLocalEnv && testRealLogin) {
    console.log('🧪 本地环境 - 测试真实登录流程');
    console.log('💡 使用本地代理，避免跨域 Cookie 问题');

    this.LOGIN_IFRAME_URL = 'https://edu.cocorobo.cn/course/login?type=2';
    this.COOKIE_API_URL = '/api/getcookieuserid'; // 使用代理路径

    this.loadingInstance = Loading.service({ fullscreen: true });
    this.getLoginState();
    if (!this.isLogin) {
      this.setTimeState = setInterval(() => {
        this.getLoginState();
      }, 2000);
    }
    return;
  }

  // 正常的线上登录流程...
}
```

#### 步骤 5：修复 Hash 路由参数读取

Vue Router 使用 hash 模式时，URL 格式是 `#/?id=xxx&type=xxx`，需要修改参数读取逻辑：

```javascript
// src/common/mixin.js
getUrlParams(url) {
  const params = {};
  const urlObj = new URL(url);

  // 尝试从标准查询字符串获取参数（?id=...&type=...）
  let queryString = urlObj.search.slice(1);

  // 如果没有查询字符串，尝试从 hash 中获取（#/?id=...&type=...）
  if (!queryString && urlObj.hash) {
    const hashParts = urlObj.hash.split('?');
    if (hashParts.length > 1) {
      queryString = hashParts[1];
    }
  }

  const queryPairs = queryString.split('&');

  queryPairs.forEach(pair => {
    const [key, value] = pair.split('=');
    if (key) {
      params[decodeURIComponent(key)] = decodeURIComponent(value || '');
    }
  });

  return params;
}
```

#### 步骤 6：配置 Shadowrocket（绕过代理）

如果使用了 Shadowrocket 等代理工具，需要配置本地域名直连：

**方法 1：通过界面添加规则**

1. 打开 Shadowrocket
2. 点击底部"配置"标签
3. 点击当前配置右侧的编辑按钮
4. 添加规则：
   - 类型：`DOMAIN-SUFFIX`，值：`local.cocorobo.cn`，策略：`DIRECT`
   - 类型：`DOMAIN`，值：`localhost`，策略：`DIRECT`
   - 类型：`IP-CIDR`，值：`127.0.0.1/32`，策略：`DIRECT`

**方法 2：编辑配置文件**

在配置文件的 `[Rule]` 部分最上面添加：

```
DOMAIN-SUFFIX,local.cocorobo.cn,DIRECT
DOMAIN,localhost,DIRECT
IP-CIDR,127.0.0.1/32,DIRECT
```

**方法 3：修改 skip-proxy**

在 `[General]` 部分添加：

```
skip-proxy = 127.0.0.1, localhost, *.local, local.cocorobo.cn
```

### 使用方式

#### 模式 1：快速开发模式（使用测试用户）

```
访问地址：
https://localhost:8081/standalone.html#/?id=xxx&type=mutiagent

特点：
- 自动跳过登录流程
- 使用预设的测试用户数据
- 快速启动开发调试
```

#### 模式 2：测试真实登录流程

```
访问地址：
https://local.cocorobo.cn:8081/standalone.html#/?id=xxx&type=mutiagent&testRealLogin=true

特点：
- 完整模拟线上登录流程
- 使用真实的登录 iframe
- 测试 Cookie 传递和验证
```

## 常见问题排查

### 问题 1：ERR_EMPTY_RESPONSE

**原因**：使用 HTTP 访问 HTTPS 服务器

**解决**：确保 URL 使用 `https://`（不是 `http://`）

### 问题 2：ERR_TUNNEL_CONNECTION_FAILED

**原因**：代理工具（Shadowrocket）拦截了本地域名请求

**解决**：在代理工具中配置本地域名直连（见步骤 6）

### 问题 3：This site can't provide a secure connection

**原因**：证书问题

**解决**：
1. 确认证书文件存在
2. 浏览器提示"不安全"时，点击"高级" → "继续访问"
3. 重新运行 `mkcert -install`

### 问题 4：登录成功但页面没有消失

**原因**：使用 localhost 而不是 local.cocorobo.cn

**解决**：必须使用 `https://local.cocorobo.cn:8081`，而不是 localhost

### 问题 5：401 Unauthorized

**检查清单**：
1. ✅ 使用了 `https://local.cocorobo.cn:8081`（不是 localhost）
2. ✅ URL 中包含 `testRealLogin=true` 参数
3. ✅ 代理工具配置了本地域名直连
4. ✅ 浏览器控制台查看 Cookie 是否设置成功（Application → Cookies）

## 验证方法

### 1. 检查服务器启动

```bash
# 启动开发服务器
npm run serve

# 应该看到：
# ✅ 检测到 HTTPS 证书，启用 HTTPS 模式
# App running at:
#   - Local:   https://localhost:8081/
```

### 2. 测试连接

```bash
# 测试 HTTPS 连接
curl -k -I https://local.cocorobo.cn:8081/standalone.html

# 应该返回 HTTP/1.1 200 OK
```

### 3. 浏览器验证

1. 访问 `https://local.cocorobo.cn:8081/standalone.html#/?id=xxx&type=mutiagent&testRealLogin=true`
2. 打开浏览器控制台（F12）
3. 检查：
   - **Console 标签**：应该看到 `🧪 本地环境 - 测试真实登录流程`
   - **Network 标签**：查看 `/api/getcookieuserid` 请求状态码（应该是 200）
   - **Application → Cookies**：查看是否有 Cookie（域名应该是 `.cocorobo.cn`）

## 核心原理总结

### 为什么必须使用域名？

```
Cookie 域名规则：
  .cocorobo.cn  →  可以被 *.cocorobo.cn 读取

有效的域名：
  ✅ https://local.cocorobo.cn:8081
  ✅ https://test.cocorobo.cn:8081
  ✅ https://dev.cocorobo.cn:8081

无效的域名：
  ❌ https://localhost:8081  →  localhost ≠ *.cocorobo.cn
  ❌ https://127.0.0.1:8081  →  IP 地址 ≠ *.cocorobo.cn
  ❌ http://local.cocorobo.cn:8081  →  Cookie 有 Secure 标志，必须 HTTPS
```

### Cookie 传递流程

```
1. 用户在 edu.cocorobo.cn 登录
   ↓
2. 登录成功后设置 Cookie
   Domain: .cocorobo.cn
   Secure: true
   ↓
3. 前端页面（local.cocorobo.cn）发起请求
   浏览器检查：local.cocorobo.cn 匹配 .cocorobo.cn ✅
   ↓
4. 浏览器自动附带 Cookie
   ↓
5. 代理转发到 beta.api.cocorobo.cn/api/getcookieuserid
   ↓
6. 后端验证 Cookie，返回用户信息
```

## 文件修改清单

本次解决方案修改了以下文件：

1. **vue.config.js**
   - 添加 HTTPS 证书配置
   - 添加开发服务器代理配置

2. **src/standalone/dialogMode/dialogMode.vue**
   - 添加 `testRealLogin` 参数逻辑
   - 区分本地测试模式和真实登录模式

3. **src/common/mixin.js**
   - 修复 `getUrlParams()` 方法，支持 hash 路由参数读取

4. **系统配置**
   - `/etc/hosts`：添加域名映射
   - Shadowrocket：配置本地域名直连规则

## 最佳实践建议

1. **开发时使用测试用户**：`https://localhost:8081`，快速启动，无需登录
2. **测试登录时使用域名**：`https://local.cocorobo.cn:8081?testRealLogin=true`
3. **提交代码前回归测试**：确保线上环境不受影响
4. **不要提交证书文件**：将 `*.pem` 添加到 `.gitignore`

## 参考资料

- [MDN - HTTP Cookies](https://developer.mozilla.org/zh-CN/docs/Web/HTTP/Cookies)
- [Same-Origin Policy](https://developer.mozilla.org/zh-CN/docs/Web/Security/Same-origin_policy)
- [mkcert - Simple zero-config tool for making locally-trusted development certificates](https://github.com/FiloSottile/mkcert)
- [webpack-dev-server Proxy](https://webpack.js.org/configuration/dev-server/#devserverproxy)
