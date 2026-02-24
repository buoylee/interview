// ==========================================
// 本地调试跨域 Cookie 登录 - 代码配置示例
// ==========================================

// ============================================
// 1. vue.config.js - HTTPS 和代理配置
// ============================================

module.exports = {
  devServer: {
    host: '0.0.0.0',
    port: 8081,
    allowedHosts: 'all',

    // HTTPS 配置 - 自动检测证书
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
        console.warn('   提示：运行 mkcert local.cocorobo.cn localhost 127.0.0.1 生成证书');
        return false;
      }
    })(),

    // 代理配置 - 解决跨域 API 请求
    proxy: {
      '/api/getcookieuserid': {
        target: 'https://beta.api.cocorobo.cn',
        changeOrigin: true,
        secure: false,
        cookieDomainRewrite: {
          '*': '' // 将 cookie 域名改写为空（本地域名）
        },
        onProxyReq: function(proxyReq, req, res) {
          console.log('🔄 代理请求:', req.url, '→', 'https://beta.api.cocorobo.cn' + req.url);
        },
        onProxyRes: function(proxyRes, req, res) {
          const setCookieHeaders = proxyRes.headers['set-cookie'];
          if (setCookieHeaders) {
            proxyRes.headers['set-cookie'] = setCookieHeaders.map(cookie => {
              // 移除 Secure 和 SameSite 限制，便于本地开发
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
};


// ============================================
// 2. Vue 组件 - 本地测试模式配置
// ============================================

export default {
  created() {
    this.aiChatMessages = [];
    window.exposed_outputs = [];
    this.session_name = uuidv4();

    const url = window.location.href;
    const isLocalEnv = url.includes('localhost') || url.includes('192.168');
    const testRealLogin = this.getUrlParams(url)["testRealLogin"] === 'true';

    // 🔧 本地测试模式：使用测试用户数据，跳过登录流程
    // 💡 如需测试真实登录流程，请添加 URL 参数: &testRealLogin=true
    if (isLocalEnv && !testRealLogin) {
      console.log('🔧 本地测试模式：使用测试用户数据');
      console.log('💡 如需测试真实登录流程，请添加 URL 参数: &testRealLogin=true');

      // 📝 测试用户数据（可根据需要修改）
      this.user = {
        userId: 'test-user-id',
        userName: 'testUser',
        organizeid: 'test-org-id',
        org: '',
        classid: 'test-class-001'
      };

      // 同步到 Vuex store
      this.$store.commit('set_user', this.user);

      // 标记为已登录
      this.isLogin = true;

      // 关闭 loading
      this.loadingInstance = Loading.service({ fullscreen: true });
      this.$nextTick(() => {
        this.loadingInstance.close();
      });

      // 初始化 LogicFlow
      this.$nextTick(() => {
        this.init_lf();
      });

      // 获取 agent 数据
      if (url.includes('?id=')) {
        let argument = url.split('?id=')[1].split('&type=');
        const id = argument[0];
        this.agent_id = id;
        this.type = this.getUrlParams(url)["type"];

        if (this.type == 'agent') {
          this.get_agent_id(id);
        } else {
          this.get_muti_agent_id(id);
        }
      }

      return; // 跳过后续的登录流程
    }

    // 🧪 本地环境 - 测试真实登录流程
    if (isLocalEnv && testRealLogin) {
      console.log('🧪 本地环境 - 测试真实登录流程');
      console.log('💡 使用本地代理，避免跨域 Cookie 问题');

      // 本地测试时使用相对路径，通过 webpack-dev-server 代理
      this.LOGIN_IFRAME_URL = 'https://edu.cocorobo.cn/course/login?type=2';
      this.COOKIE_API_URL = '/api/getcookieuserid'; // 使用代理路径

      this.loadingInstance = Loading.service({ fullscreen: true });
      this.getLoginState();
      if (!this.isLogin) {
        this.setTimeState = setInterval(() => {
          this.getLoginState();
        }, 2000);
      }
      return; // 跳过后续的 URL 配置
    }

    // 🌐 正常的线上登录流程
    switch (this.domain_name) {
      case 'cn':
        this.LOGIN_IFRAME_URL = 'https://edu.cocorobo.cn/course/login?type=2';
        this.COOKIE_API_URL = 'https://beta.api.cocorobo.cn/api/getcookieuserid';
        break;
      case 'hk':
        this.LOGIN_IFRAME_URL = 'https://edu.cocorobo.hk/LoginIframe?type=2';
        this.COOKIE_API_URL = 'https://cloud.api.cocorobo.hk/api/getcookieuserid';
        break;
      case 'com':
        this.LOGIN_IFRAME_URL = 'https://edu.cocorobo.com/login_en?type=2';
        this.COOKIE_API_URL = 'https://cloud.api.cocorobo.com/api/getcookieuserid';
        break;
      default:
        this.LOGIN_IFRAME_URL = 'https://edu.cocorobo.cn/course/login?type=2';
        this.COOKIE_API_URL = 'https://beta.api.cocorobo.cn/api/getcookieuserid';
        break;
    }

    this.loadingInstance = Loading.service({ fullscreen: true });
    this.getLoginState();
    if (!this.isLogin) {
      this.setTimeState = setInterval(() => {
        this.getLoginState();
      }, 2000);
    }
  }
}


// ============================================
// 3. Mixin - 修复 Hash 路由参数读取
// ============================================

export const myMixin = {
  methods: {
    /**
     * 从 URL 中提取查询参数
     * 支持两种格式：
     * 1. 标准格式：?id=xxx&type=xxx
     * 2. Hash 路由格式：#/?id=xxx&type=xxx
     */
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
  }
}


// ============================================
// 4. Shadowrocket 配置文件示例
// ============================================

/*
[General]
bypass-system = true
skip-proxy = 127.0.0.1, 192.168.0.0/16, 10.0.0.0/8, 172.16.0.0/12, localhost, *.local, local.cocorobo.cn

[Rule]
# 本地开发规则（添加在最上面，优先级最高）
DOMAIN-SUFFIX,local.cocorobo.cn,DIRECT
DOMAIN,localhost,DIRECT
IP-CIDR,127.0.0.1/32,DIRECT

# 其他规则...
GEOIP,CN,DIRECT
FINAL,PROXY
*/


// ============================================
// 5. 调试工具函数
// ============================================

/**
 * 检查 Cookie 是否正确设置
 */
function checkCookie() {
  const cookies = document.cookie.split(';').map(c => c.trim());
  console.log('📋 当前页面 Cookie：', cookies);

  const hasCocoroCookie = cookies.some(c =>
    c.includes('cocorobo') || c.includes('session') || c.includes('token')
  );

  if (hasCocoroCookie) {
    console.log('✅ 检测到 cocorobo 相关 Cookie');
  } else {
    console.warn('⚠️  未检测到 cocorobo 相关 Cookie');
    console.warn('   可能原因：');
    console.warn('   1. 未登录');
    console.warn('   2. 使用了 localhost 而不是 local.cocorobo.cn');
    console.warn('   3. Cookie 域名不匹配');
  }

  return hasCocoroCookie;
}

/**
 * 测试登录状态
 */
async function testLoginState() {
  try {
    const response = await fetch('/api/getcookieuserid', {
      method: 'GET',
      credentials: 'include' // 重要：携带 Cookie
    });

    console.log('🔍 登录状态检查：');
    console.log('  状态码:', response.status);

    if (response.status === 200) {
      const data = await response.json();
      console.log('  ✅ 已登录，用户信息:', data);
      return true;
    } else if (response.status === 401) {
      console.log('  ❌ 未登录（401）');
      console.log('  请检查：');
      console.log('  1. 是否使用 https://local.cocorobo.cn:8081');
      console.log('  2. 是否已在登录页面完成登录');
      console.log('  3. Cookie 是否正确设置（查看 Application → Cookies）');
      return false;
    } else {
      console.log('  ⚠️  未知状态:', response.status);
      return false;
    }
  } catch (error) {
    console.error('❌ 请求失败:', error);
    return false;
  }
}

/**
 * 完整的调试流程
 */
async function debugLogin() {
  console.log('==========================================');
  console.log('🔍 开始调试登录流程');
  console.log('==========================================');

  // 1. 检查当前 URL
  console.log('\n📍 步骤 1：检查 URL');
  const url = window.location.href;
  console.log('  当前 URL:', url);

  if (url.includes('localhost')) {
    console.warn('  ⚠️  使用了 localhost，可能无法获取 .cocorobo.cn 域的 Cookie');
    console.warn('  建议使用: https://local.cocorobo.cn:8081');
  } else if (url.includes('local.cocorobo.cn')) {
    console.log('  ✅ 使用了正确的域名');
  }

  if (!url.startsWith('https://')) {
    console.warn('  ⚠️  未使用 HTTPS，Cookie 可能无法传递（如果有 Secure 标志）');
  }

  // 2. 检查 Cookie
  console.log('\n🍪 步骤 2：检查 Cookie');
  const hasCookie = checkCookie();

  // 3. 测试登录状态
  console.log('\n🔐 步骤 3：测试登录状态');
  const isLoggedIn = await testLoginState();

  // 4. 总结
  console.log('\n📊 调试总结：');
  console.log('  URL 正确:', !url.includes('localhost') && url.startsWith('https://'));
  console.log('  Cookie 存在:', hasCookie);
  console.log('  登录状态:', isLoggedIn ? '已登录' : '未登录');

  console.log('\n==========================================');
  if (isLoggedIn) {
    console.log('✅ 登录流程正常！');
  } else {
    console.log('❌ 登录流程异常，请检查上述问题');
  }
  console.log('==========================================');
}

// 导出调试函数（可在控制台直接调用）
window.debugLogin = debugLogin;
window.checkCookie = checkCookie;
window.testLoginState = testLoginState;

console.log('💡 调试工具已加载，可在控制台使用：');
console.log('  - debugLogin()      : 完整调试流程');
console.log('  - checkCookie()     : 检查 Cookie');
console.log('  - testLoginState()  : 测试登录状态');
