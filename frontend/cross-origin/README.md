# 跨域完整知识体系

本目录包含了跨域相关的完整知识体系，包括本地调试、面试复习、实战案例等。

## 📚 文档导航

### 🎯 实战篇（本地开发调试）

#### 1. [本地调试跨域Cookie登录问题解决方案.md](./本地调试跨域Cookie登录问题解决方案.md)
**📘 最详细的技术文档**（12 KB）

- 问题背景和现象
- 深入的原理分析
- 完整的解决方案
- 分步配置指南
- 常见问题排查
- 验证方法
- 核心原理总结

**适合**：深入理解本地调试跨域 Cookie 问题

#### 2. [快速配置指南.md](./快速配置指南.md)
**⚡ TL;DR 版本**（1.8 KB）

- 一键配置脚本
- 快速使用方式
- 常见错误速查表
- 验证清单

**适合**：已经理解原理，快速配置环境

#### 3. [代码配置示例.js](./代码配置示例.js)
**💻 可直接复制的代码**（11 KB）

- vue.config.js 配置
- Vue 组件配置
- Mixin 工具函数
- Shadowrocket 配置
- 调试工具函数

**适合**：直接复制代码到项目中使用

#### 4. [修改文件清单.md](./修改文件清单.md)
**📝 详细的变更记录**（9.2 KB）

- 每个文件的修改前后对比
- 影响范围分析
- 回滚方案
- 验证清单

**适合**：了解所有改动，追踪变更

### 📖 理论篇（深入理解）

#### 5. [Cookie域名策略详解.md](./Cookie域名策略详解.md)
**🍪 Cookie 跨域专题**（约 15 KB）

- 服务端设置 Cookie 的规则
- 同源策略 vs Cookie 域名策略
- 为什么 localhost 不行，local.cocorobo.cn 可以
- 实战验证代码
- 常见误区解答

**适合**：深入理解 Cookie 跨域机制

### 🎓 面试篇（求职必备）

#### 6. [跨域完全指南-面试版.md](./跨域完全指南-面试版.md) ⭐⭐⭐⭐⭐
**📖 最全面的面试复习资料**（约 45 KB）

包含 10 个章节：
1. 基础概念
2. 同源策略详解
3. 跨域解决方案（9种）
4. Cookie 跨域专题
5. 实战案例
6. 高频面试题
7. 进阶知识
8. 快速记忆口诀
9. 面试加分项
10. 总结

**适合**：全面系统地复习跨域知识

#### 7. [跨域速查表.md](./跨域速查表.md)
**⚡ 30秒速记手册**（约 8 KB）

- 30秒速记要点
- 高频考点
- 常用代码片段
- 常见错误速查
- 面试回答模板
- 时间分配建议

**适合**：面试前快速复习

#### 8. [跨域面试真题集.md](./跨域面试真题集.md)
**📝 真题 + 答案 + 解析**（约 20 KB）

包含 5 类题目：
- 基础题（必会）
- 进阶题（加分）
- 场景题（实战）
- 手写题（代码）
- 综合题（高级）

**适合**：针对性练习，查漏补缺

## 🎯 核心问题

**在本地开发环境中，如何测试需要跨域 Cookie 的登录流程？**

### 问题本质

```
登录 iframe：edu.cocorobo.cn
设置 Cookie：Domain=.cocorobo.cn

前端页面：localhost:8081
浏览器规则：localhost ≠ *.cocorobo.cn
结果：Cookie 不会被发送 ❌
```

### 解决方案

```
使用本地子域名：local.cocorobo.cn
浏览器规则：local.cocorobo.cn ∈ *.cocorobo.cn
结果：Cookie 正常发送 ✅
```

## 📖 学习路径建议

### 路径 1：本地开发调试（解决实际问题）

1. 先看 **快速配置指南.md**（5分钟）
2. 遇到问题查 **本地调试跨域Cookie登录问题解决方案.md**（30分钟）
3. 需要深入理解看 **Cookie域名策略详解.md**（20分钟）
4. 复制代码参考 **代码配置示例.js**

### 路径 2：面试准备（系统复习）

**第一阶段（2小时）**：
1. 阅读 **跨域完全指南-面试版.md**（90分钟）
2. 做笔记，标记重点

**第二阶段（1小时）**：
1. 刷 **跨域面试真题集.md**（45分钟）
2. 自己先思考答案，再看参考答案

**第三阶段（30分钟）**：
1. 背诵 **跨域速查表.md**（15分钟）
2. 默写核心知识点（15分钟）

**面试前（10分钟）**：
- 快速浏览 **跨域速查表.md**
- 回顾自己的项目经验

### 路径 3：深入理解（技术提升）

1. **跨域完全指南-面试版.md** → 建立知识框架
2. **Cookie域名策略详解.md** → 理解核心机制
3. **跨域面试真题集.md** → 实践练习
4. **手写代码** → JSONP、CORS 中间件
5. **实际项目** → 应用到工作中

## 🔥 重点概念速记

### 同源策略
```
协议 + 域名 + 端口 = 完全相同 ✅
任一不同 = 跨域 ❌
```

### Cookie 域名策略
```
Cookie: Domain=.example.com

可访问：
✅ example.com
✅ *.example.com（所有子域）

不可访问：
❌ localhost
❌ 其他域名
```

### CORS 配置
```javascript
// 服务端
res.header('Access-Control-Allow-Origin', 'https://example.com')
res.header('Access-Control-Allow-Credentials', 'true')

// 前端
fetch(url, { credentials: 'include' })
```

### 跨域方案选择
```
API 请求 → CORS
开发环境 → webpack-dev-server 代理
生产环境 → Nginx 反向代理
窗口通信 → postMessage
实时通信 → WebSocket
```

## 💡 常见问题 FAQ

### Q1：localhost 为什么无法获取 .example.com 的 Cookie？

**A**：因为 `localhost` 不属于 `*.example.com` 的子域，Cookie 域名不匹配。

**解决**：使用 `local.example.com` 代替 localhost。

### Q2：CORS 和 JSONP 有什么区别？

**A**：
- **CORS**：标准方案，支持所有 HTTP 方法，需要服务端配置
- **JSONP**：利用 `<script>` 标签，仅支持 GET，已过时

**推荐**：使用 CORS

### Q3：携带 Cookie 时为什么 Origin 不能用 `*`？

**A**：安全考虑。如果允许 `*`，任何网站都能携带用户的 Cookie 访问 API，导致安全风险。

### Q4：预检请求是什么？如何优化？

**A**：
- **定义**：不满足简单请求条件时，浏览器先发送 OPTIONS 请求
- **优化**：使用 `Access-Control-Max-Age` 缓存预检结果

### Q5：同源策略和 Cookie 域名策略有什么区别？

**A**：
- **同源策略**：严格，协议+域名+端口完全相同
- **Cookie 域名策略**：灵活，允许父子域共享

这是两个不同的安全机制！

## ⚡ 快速开始

### 5 分钟配置

```bash
# 1. 安装工具
brew install mkcert && mkcert -install

# 2. 生成证书
cd /path/to/your/project
mkcert local.cocorobo.cn localhost 127.0.0.1

# 3. 配置 hosts
echo "127.0.0.1  local.cocorobo.cn" | sudo tee -a /etc/hosts

# 4. 配置 Shadowrocket（如果使用代理）
# 在 [Rule] 最上面添加：
# DOMAIN-SUFFIX,local.cocorobo.cn,DIRECT

# 5. 启动项目
npm run serve

# 6. 访问
https://local.cocorobo.cn:8081
```

## 🔍 使用方式

### 开发模式（自动登录）
```
https://localhost:8081/standalone.html#/?id=xxx&type=mutiagent
```
- ✅ 无需登录
- ✅ 自动使用测试用户
- ✅ 快速开发

### 测试模式（真实登录）
```
https://local.cocorobo.cn:8081/standalone.html#/?id=xxx&type=mutiagent&testRealLogin=true
```
- ✅ 完整登录流程
- ✅ 测试 Cookie 传递
- ✅ 真实环境模拟

## 🐛 常见问题

| 错误提示 | 快速解决 |
|---------|---------|
| ERR_EMPTY_RESPONSE | 改用 `https://`（不是 http） |
| ERR_TUNNEL_CONNECTION_FAILED | 配置代理工具直连本地域名 |
| 登录后页面不消失 | 使用 `local.cocorobo.cn`（不是 localhost） |
| 401 Unauthorized | 检查域名、HTTPS、代理配置 |

## 📖 相关技术

- Cookie 跨域策略
- Same-Origin Policy
- HTTPS 证书配置
- Webpack Dev Server Proxy
- Vue Router Hash 模式
- 代理工具配置

## 🔗 相关链接

- [MDN - HTTP Cookies](https://developer.mozilla.org/zh-CN/docs/Web/HTTP/Cookies)
- [mkcert GitHub](https://github.com/FiloSottile/mkcert)
- [webpack-dev-server](https://webpack.js.org/configuration/dev-server/)

## 📝 更新日志

- 2025-12-30：初始版本，完整解决方案文档
