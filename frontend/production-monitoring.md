# 前端生产监控实践指南

> 适用于 10 人左右的小团队，以 Sentry 为核心的一站式方案。

---

## 一、核心认知：前端日志 ≠ 后端日志

| 对比 | 后端 | 前端 |
|------|------|------|
| 代码运行在 | 自己的服务器 | 用户的浏览器 |
| 日志存储 | 磁盘文件 / ELK | 需主动上报到服务端 |
| 看日志方式 | `tail -f` / Kibana | Sentry 面板 / Grafana |
| 异常来源 | 单一环境 | 成千上万种浏览器/设备/网络 |
| 复现难度 | 低（同一环境） | 高（需 SourceMap + Session Replay） |

**核心思路：采集 → 上报 → 聚合 → 告警**

---

## 二、推荐方案：Sentry（SaaS Team 方案）

### 为什么选 Sentry

- **功能覆盖 80% 的监控需求**：错误捕获、性能监控、会话回放、告警、Release 追踪
- **价格友好**：Team 方案 ~$26/月起，远低于自建成本
- **接入成本极低**：10 分钟完成基础接入
- **前后端统一**：支持 Vue/React/Node.js/Java/Go 等主流技术栈
- **社区活跃**：开源，文档完善，遇到问题容易找到解决方案

### 方案对比

| 方案 | 优点 | 缺点 | 适合场景 |
|------|------|------|---------|
| **Sentry SaaS** ✅ | 开箱即用，免运维 | 数据在海外 | 一般小团队 |
| **Sentry 自建** | 数据私有化 | 需维护 Docker 集群 | 有合规要求 |
| **LogRocket** | 回放体验好 | 贵，错误监控弱于 Sentry | 偏产品分析 |
| **阿里 ARMS** | 国内云原生 | 和阿里云绑定 | 全栈阿里云 |
| **自建 ELK** | 完全可控 | 运维成本高 | 大团队 (50+) |

---

## 三、落地步骤

### 第 1 步：前端接入 Sentry SDK

#### Vue 项目

```bash
npm install @sentry/vue
```

```javascript
// main.js
import * as Sentry from '@sentry/vue';
import { createApp } from 'vue';
import App from './App.vue';
import router from './router';

const app = createApp(App);

Sentry.init({
  app,
  dsn: 'https://your-dsn@o0.ingest.sentry.io/0', // 从 Sentry 项目设置获取
  integrations: [
    Sentry.browserTracingIntegration({ router }), // 自动追踪路由切换性能
    Sentry.replayIntegration(),                    // 会话回放
  ],

  // 性能监控：采样 20% 的请求
  tracesSampleRate: 0.2,

  // 会话回放：常规会话录制 10%，出错会话 100% 录制
  replaysSessionSampleRate: 0.1,
  replaysOnErrorSampleRate: 1.0,

  // 环境标记
  environment: process.env.NODE_ENV, // 'production' / 'staging'

  // Release 版本追踪（配合 CI/CD）
  release: process.env.VUE_APP_VERSION || 'unknown',
});

app.use(router);
app.mount('#app');
```

#### React 项目

```bash
npm install @sentry/react
```

```javascript
// main.jsx
import * as Sentry from '@sentry/react';

Sentry.init({
  dsn: 'https://your-dsn@o0.ingest.sentry.io/0',
  integrations: [
    Sentry.browserTracingIntegration(),
    Sentry.replayIntegration(),
  ],
  tracesSampleRate: 0.2,
  replaysSessionSampleRate: 0.1,
  replaysOnErrorSampleRate: 1.0,
  environment: process.env.NODE_ENV,
  release: process.env.REACT_APP_VERSION || 'unknown',
});
```

---

### 第 2 步：上传 SourceMap（关键！）

没有 SourceMap，Sentry 捕获的错误只有压缩后的代码，无法定位到源码行号。

#### 方式一：Vite 插件（推荐）

```bash
npm install @sentry/vite-plugin
```

```javascript
// vite.config.js
import { sentryVitePlugin } from '@sentry/vite-plugin';

export default defineConfig({
  build: {
    sourcemap: true, // 必须开启
  },
  plugins: [
    sentryVitePlugin({
      org: 'your-org',
      project: 'your-project',
      authToken: process.env.SENTRY_AUTH_TOKEN, // CI/CD 环境变量中配置
    }),
  ],
});
```

#### 方式二：Webpack 插件

```bash
npm install @sentry/webpack-plugin
```

```javascript
// vue.config.js 或 webpack.config.js
const { sentryWebpackPlugin } = require('@sentry/webpack-plugin');

module.exports = {
  productionSourceMap: true,
  configureWebpack: {
    plugins: [
      sentryWebpackPlugin({
        org: 'your-org',
        project: 'your-project',
        authToken: process.env.SENTRY_AUTH_TOKEN,
      }),
    ],
  },
};
```

#### 方式三：CI/CD 中手动上传

```bash
# 安装 CLI
npm install -g @sentry/cli

# 上传（在构建产物目录中执行）
sentry-cli releases files $RELEASE upload-sourcemaps ./dist \
  --org your-org \
  --project your-project
```

> ⚠️ **安全提示**：SourceMap 只上传到 Sentry，不要部署到生产服务器。构建流程中上传完毕后删除 `.map` 文件。

---

### 第 3 步：后端接入 Sentry（实现全链路追踪）

#### Node.js (Express)

```bash
npm install @sentry/node
```

```javascript
const Sentry = require('@sentry/node');

Sentry.init({
  dsn: 'https://your-backend-dsn@o0.ingest.sentry.io/0',
  tracesSampleRate: 0.2,
  environment: process.env.NODE_ENV,
});

const app = express();

// Sentry 请求处理（必须在所有路由之前）
Sentry.setupExpressErrorHandler(app);

// 你的路由...
app.get('/api/users', (req, res) => { ... });
```

#### Java (Spring Boot)

```xml
<!-- pom.xml -->
<dependency>
    <groupId>io.sentry</groupId>
    <artifactId>sentry-spring-boot-starter</artifactId>
    <version>7.x.x</version>
</dependency>
```

```yaml
# application.yml
sentry:
  dsn: https://your-dsn@o0.ingest.sentry.io/0
  traces-sample-rate: 0.2
  environment: production
```

> 前后端接入后，Sentry 会自动通过 `sentry-trace` header 关联前后端的 Trace，实现全链路追踪。

---

### 第 4 步：配置告警规则

在 Sentry 后台 → **Alerts** → **Create Alert Rule**：

| 告警场景 | 配置建议 |
|---------|---------|
| 新错误首次出现 | 立即通知 |
| 同一错误 1 小时内 > 100 次 | 高优先级通知 |
| 某接口 P95 响应 > 3s | 性能告警 |
| 错误率突增 (spike) | 异常检测告警 |

**通知渠道配置：**

- **飞书 / 钉钉**：通过 Webhook Integration 接入
- **Slack**：原生集成
- **邮件**：默认支持

---

### 第 5 步：接口层监控增强

Sentry 会自动追踪 `fetch`/`XMLHttpRequest`，但建议在 Axios 拦截器中补充业务级信息：

```javascript
import * as Sentry from '@sentry/vue';

// 请求拦截器 - 记录请求开始时间
axios.interceptors.request.use(config => {
  config._startTime = Date.now();
  return config;
});

// 响应拦截器 - 捕获异常并附加上下文
axios.interceptors.response.use(
  response => response,
  error => {
    const duration = Date.now() - (error.config?._startTime || 0);

    Sentry.withScope(scope => {
      scope.setTag('api.url', error.config?.url);
      scope.setTag('api.method', error.config?.method);
      scope.setTag('api.status', error.response?.status);
      scope.setExtra('api.duration_ms', duration);
      scope.setExtra('api.request_data', error.config?.data);
      scope.setExtra('api.response_data', error.response?.data);
      scope.setLevel('error');
      Sentry.captureException(error);
    });

    return Promise.reject(error);
  }
);
```

---

### 第 6 步：Web Vitals 性能监控

Sentry 的 `browserTracingIntegration` 已自动采集 Web Vitals，但如果需要更细粒度的自定义上报：

```bash
npm install web-vitals
```

```javascript
import { onLCP, onINP, onCLS } from 'web-vitals';
import * as Sentry from '@sentry/vue';

function reportWebVital(metric) {
  Sentry.setMeasurement(metric.name, metric.value, metric.name === 'CLS' ? '' : 'millisecond');
}

onLCP(reportWebVital);
onINP(reportWebVital);  // 2024+ 替代 FID
onCLS(reportWebVital);
```

**核心指标解读：**

| 指标 | 含义 | 好 | 需改进 | 差 |
|------|------|:--:|:------:|:--:|
| **LCP** | 最大内容绘制时间 | ≤2.5s | ≤4s | >4s |
| **INP** | 交互响应延迟 | ≤200ms | ≤500ms | >500ms |
| **CLS** | 累计布局偏移 | ≤0.1 | ≤0.25 | >0.25 |

---

## 四、自定义业务日志（可选）

如果需要像后端一样打业务日志，可以封装一个 Logger 并通过 Sentry Breadcrumb 记录：

```javascript
const logger = {
  info(message, data = {}) {
    Sentry.addBreadcrumb({
      category: 'app.info',
      message,
      data,
      level: 'info',
    });
    console.log(`[INFO] ${message}`, data);
  },

  warn(message, data = {}) {
    Sentry.addBreadcrumb({
      category: 'app.warn',
      message,
      data,
      level: 'warning',
    });
    console.warn(`[WARN] ${message}`, data);
  },

  error(message, error, data = {}) {
    Sentry.withScope(scope => {
      scope.setExtras(data);
      Sentry.captureException(error || new Error(message));
    });
    console.error(`[ERROR] ${message}`, error, data);
  },
};

export default logger;
```

使用方式：

```javascript
import logger from '@/utils/logger';

logger.info('用户下单成功', { orderId: '12345', amount: 99.9 });
logger.error('支付回调异常', new Error('timeout'), { orderId: '12345' });
```

---

## 五、团队工作流

### 日常流程

```
每日：  值班同学查看 Sentry 新增告警（轮值机制）
每周：  团队 Review Sentry 面板，整理 Top 5 高频错误
每版本：检查 Release 关联的错误趋势，确认新版本未引入回归
```

### Sentry 面板关注重点

1. **Issues** → 按 `Events` 排序 → 修复影响用户最多的错误
2. **Performance** → 关注 P95 慢请求和 Web Vitals 不达标页面
3. **Replays** → 结合错误 Issue 回放用户操作路径，辅助复现
4. **Alerts** → 确保告警规则覆盖关键业务场景

### 错误处理原则

| 优先级 | 标准 | 处理方式 |
|--------|------|---------|
| P0 | 影响核心功能且大面积出现 | 立即修复，必要时回滚 |
| P1 | 影响核心功能但小范围 | 当天修复 |
| P2 | 非核心功能错误 | 排入迭代修复 |
| P3 | 低频、无明显影响 | 记录，空闲时处理 |

---

## 六、SourceMap 安全注意事项

```
✅ SourceMap 上传到 Sentry → 用于错误堆栈还原
❌ SourceMap 部署到生产 CDN → 暴露源码，安全风险

推荐在 CI/CD 中：
1. 构建时生成 SourceMap
2. 上传到 Sentry
3. 删除 .map 文件
4. 部署不含 .map 的产物
```

---

## 七、进阶：补充工具（按需选用）

| 需求 | 推荐工具 | 说明 |
|------|---------|------|
| 免费的用户行为热力图 | Microsoft Clarity | 微软出品，完全免费 |
| 更强的产品分析 | Mixpanel / Amplitude | 用户漏斗、留存分析 |
| 可视化监控大盘 | Grafana | 聚合前后端指标 |
| 全链路追踪标准化 | OpenTelemetry | 替代各厂商私有 SDK |
| 稳定性 SLO 管理 | Sentry 自带 | 设置错误率目标 |
