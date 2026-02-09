---
name: agent-browser
description: This skill should be used when the user asks to test, demonstrate, or use agent-browser for browser automation tasks. Use for web scraping, form filling, UI testing, and any web interaction tasks.
version: 1.0.0
---

# agent-browser 实战经验

## 是什么
- **作者**: Vercel Labs
- **定位**: 为 AI 设计的浏览器自动化 CLI 工具
- **架构**: Rust CLI + Node.js Daemon（client-daemon 模式）
- **安装**: `npm install -g agent-browser`
- **路径**: `~/.nvm/versions/node/v20.20.0/bin/agent-browser`
- **官网**: https://agent-browser.dev/

## 核心特性
- **Agent-first**: 紧凑的文本输出，~200-400 tokens vs ~3000-5000 for full DOM
- **Ref-based**: 快照返回带 refs 的可访问性树，元素选择确定且快速
- **Fast**: Rust 原生 CLI，命令解析瞬间完成
- **Complete**: 50+ 命令，覆盖导航、表单、截图、网络、存储
- **Sessions**: 多隔离浏览器实例，各自独立认证状态
- **Cross-platform**: macOS/Linux/Windows

## 工作流程
```
agent-browser open <url>      # 打开页面
agent-browser snapshot -i     # 获取交互元素快照
agent-browser click @e1       # 使用 ref 点击
agent-browser fill @e2 "text" # 填写表单
agent-browser screenshot      # 截图
agent-browser close           # 关闭
```

## 安装和依赖（重要经验）

### 必须先安装 Playwright 浏览器
```bash
npx playwright install chromium
```

**重要教训**:
- 只安装 Playwright 包不够，必须运行 `playwright install`
- agent-browser 不会自动安装浏览器
- 之前尝试用 `--browser=firefox` 指向系统 Firefox，**失败** - 只能使用 Playwright 安装的浏览器

### Linux 依赖
```bash
agent-browser install --with-deps
# 或
npx playwright install-deps chromium
```

## 核心命令详解

### 导航和基础操作
```bash
agent-browser open <url>        # 打开 URL（别名: goto, navigate）
agent-browser back              # 后退
agent-browser forward           # 前进
agent-browser reload            # 刷新
agent-browser close             # 关闭浏览器
```

### 元素交互
```bash
agent-browser click <sel>           # 点击元素
agent-browser dblclick <sel>        # 双击
agent-browser fill <sel> <text>     # 清空并填写（表单最佳选择）
agent-browser type <sel> <text>     # 追加输入
agent-browser press <key>           # 按键 (Enter, Tab, Control+a)
agent-browser hover <sel>           # 悬停
agent-browser select <sel> <val>    # 选择下拉选项
agent-browser check <sel>           # 选中复选框
agent-browser uncheck <sel>         # 取消选中
agent-browser scroll <dir> [px]     # 滚动 (up/down/left/right)
```

### 获取信息
```bash
agent-browser get text <sel>    # 获取文本内容
agent-browser get html <sel>    # 获取 innerHTML
agent-browser get value <sel>   # 获取输入值
agent-browser get attr <sel> <attr>  # 获取属性
agent-browser get title         # 获取页面标题
agent-browser get url           # 获取当前 URL
agent-browser get count <sel>   # 统计匹配元素数量
agent-browser get box <sel>     # 获取边界框
```

### 检查状态
```bash
agent-browser is visible <sel>  # 是否可见
agent-browser is enabled <sel>  # 是否可用
agent-browser is checked <sel>  # 是否选中
```

### 等待
```bash
agent-browser wait <selector>       # 等待元素出现
agent-browser wait <ms>             # 等待毫秒
agent-browser wait --text "Welcome" # 等待文本出现
agent-browser wait --url "**/dash"  # 等待 URL 匹配
agent-browser wait --load           # 等待加载完成
agent-browser wait --fn "condition" # 等待 JS 条件为真
agent-browser wait --download [path]  # 等待下载完成
```

### 鼠标操作
```bash
agent-browser mouse move <x> <y>    # 移动鼠标
agent-browser mouse down [button]   # 按下鼠标
agent-browser mouse up [button]     # 抬起鼠标
agent-browser mouse wheel <dy> [dx] # 滚轮滚动
```

### 截图和页面
```bash
agent-browser screenshot [path]     # 截图（--full 截取完整页面）
agent-browser pdf <path>            # 保存为 PDF
agent-browser eval <js>             # 执行 JavaScript
```

### 语义定位器（重要功能）
```bash
agent-browser find role <role> <action> [value]
agent-browser find text <text> <action>
agent-browser find label <label> <action> [value]
agent-browser find placeholder <ph> <action> [value]
agent-browser find testid <id> <action> [value]
agent-browser find first <sel> <action> [value]
agent-browser find nth <n> <sel> <action> [value]

# 示例
agent-browser find role button click --name "Submit"
agent-browser find label "Email" fill "test@test.com"
agent-browser find placeholder "Search..." fill "query"
```

### 快照（核心功能）
```bash
agent-browser snapshot              # 完整可访问性树
agent-browser snapshot -i           # 仅交互元素（推荐）
agent-browser snapshot -c           # 紧凑模式（移除空元素）
agent-browser snapshot -d 3         # 限制深度为 3 层
agent-browser snapshot -s "#main"   # 限定 CSS 选择器范围
agent-browser snapshot --json       # JSON 格式输出
```

**输出示例**:
```
@e1 [heading] "Example Domain" [level=1]
@e2 [button] "Submit"
@e3 [input type="email"] placeholder="Email"
@e4 [link] "Learn more"
```

### 网络控制
```bash
agent-browser network route <url>           # 拦截请求
agent-browser network route <url> --abort   # 阻止请求
agent-browser network route <url> --body <json>  # 模拟响应
agent-browser network unroute [url]         # 移除路由
agent-browser network requests              # 查看追踪的请求
```

### Cookie 和存储
```bash
agent-browser cookies                       # 获取所有 cookie
agent-browser cookies set <name> <val>      # 设置 cookie
agent-browser cookies clear                 # 清除 cookie
agent-browser storage local                 # 获取所有 localStorage
agent-browser storage local <key>           # 获取特定 key
agent-browser storage local set <k> <v>     # 设置值
agent-browser storage local clear           # 清除所有
agent-browser storage session               # sessionStorage（同上）
```

### 标签页和框架
```bash
agent-browser tab                    # 列出标签页
agent-browser tab new [url]          # 新建标签页
agent-browser tab <n>                # 切换到标签页
agent-browser tab close [n]          # 关闭标签页
agent-browser frame <sel>            # 切换到 iframe
agent-browser frame main             # 返回主框架
```

### 调试
```bash
agent-browser trace start [path]     # 开始追踪
agent-browser trace stop [path]      # 停止并保存
agent-browser console                # 查看控制台消息
agent-browser errors                 # 查看页面错误
agent-browser highlight <sel>        # 高亮元素
agent-browser state save <path>      # 保存认证状态
agent-browser state load <path>      # 加载认证状态
```

### 设置
```bash
agent-browser set viewport <w> <h>   # 设置视口大小
agent-browser set device <name>      # 模拟设备 ("iPhone 14")
agent-browser set geo <lat> <lng>    # 设置地理位置
agent-browser set offline [on|off]   # 离线模式
agent-browser set headers <json>     # HTTP 请求头
agent-browser set credentials <u> <p>  # HTTP 基本认证
agent-browser set media [dark|light]  # 模拟颜色方案
```

## 选择器系统

### Refs（推荐）
从 snapshot 获取的引用，最适合 AI 使用：
```bash
agent-browser snapshot -i
# 输出: - button "Submit" [ref=e1]
agent-browser click @e1
agent-browser fill @e2 "test@example.com"
```

**优点**:
- 确定: ref 直接指向快照中的元素
- 快速: 无需重新查询 DOM
- AI 友好: LLM 可以可靠解析

### CSS 选择器
```bash
agent-browser click "#id"
agent-browser click ".class"
agent-browser click "div > button"
agent-browser click "[data-testid='submit']"
```

### 文本和 XPath
```bash
agent-browser click "text=Submit"
agent-browser click "xpath=//button[@type='submit']"
```

## Sessions（会话隔离）

### 基本用法
```bash
# 不同会话，完全隔离
agent-browser --session agent1 open site-a.com
agent-browser --session agent2 open site-b.com

# 环境变量方式
AGENT_BROWSER_SESSION=agent1 agent-browser click "#btn"

# 列出活动会话
agent-browser session list
```

### 持久化配置
```bash
# 使用持久化配置目录
agent-browser --profile ~/.myapp-profile open myapp.com
# 下次打开时登录状态保留

# 环境变量方式
AGENT_BROWSER_PROFILE=~/.myapp-profile agent-browser open myapp.com
```

**存储内容**:
- Cookies 和 localStorage
- IndexedDB 数据
- Service workers
- 浏览器缓存
- 登录会话

### 认证头（重要功能）
```bash
# 为特定域名设置 HTTP 头
agent-browser open api.example.com --headers '{"Authorization": "Bearer <token>"}'
# 仅 api.example.com 收到认证头，其他域名不泄露

# 多域名不同认证
agent-browser open api.example.com --headers '{"Authorization": "Bearer token1"}'
agent-browser open api.acme.com --headers '{"Authorization": "Bearer token2"}'

# 全局头
agent-browser set headers '{"X-Custom-Header": "value"}'
```

## Ref 生命周期（重要经验）

**关键点**: refs 在页面变化后会失效！

```bash
# 正确流程
agent-browser click @e4    # 点击导航到新页面
agent-browser snapshot -i  # 重新获取快照（必须！）
agent-browser click @e1    # 使用新的 refs
```

**教训**:
- `click` 可能触发导航，之前的 ref 就失效了
- 每次页面变化后都要重新 `snapshot`
- 不要缓存 ref 供后续使用

## 最佳实践

1. **总是使用 `-i` 标志**: 只获取交互元素，减少 token 消耗
2. **页面变化后重新快照**: 导航、点击、表单提交后都要重新获取
3. **使用 `-s` 限定范围**: 对复杂页面，只获取感兴趣的部分
4. **使用 `-d` 限制深度**: 避免过深的树结构
5. **优先使用 `fill` 而非 `type`**: `fill` 会先清空输入框，更适合表单
6. **使用 `--json` 编程解析**: 脚本中需要结构化数据时使用

## 使用场景示例

### 表单填写
```bash
agent-browser open https://example.com/form
agent-browser snapshot -i
agent-browser find label "Email" fill "user@example.com"
agent-browser find label "Password" fill "secret123"
agent-browser find role button click --name "Login"
```

### 页面截图
```bash
agent-browser open https://example.com
agent-browser screenshot page.png
agent-browser screenshot full-page.png --full
```

### 数据提取
```bash
agent-browser open https://example.com
agent-browser snapshot -i
agent-browser get text @e1
agent-browser get count "li"
```

### 等待元素
```bash
agent-browser open https://example.com
agent-browser wait --text "Welcome back"
agent-browser wait 3000
agent-browser wait --load
```

### 网络拦截和模拟
```bash
agent-browser open https://example.com
agent-browser network route "**/api/data" --body '{"mock": true}'
agent-browser reload
```

## 常见错误和解决方案

| 错误 | 解决方案 |
|------|----------|
| "Executable doesn't exist" | 运行 `npx playwright install chromium` |
| Ref 无效 | 重新执行 `agent-browser snapshot` |
| 元素找不到 | 使用 `find` 语义定位器 |
| 页面加载超时 | 使用 `agent-browser wait --load` |
| 下载失败 | 使用 `agent-browser wait --download [path]` |

## 环境变量
```bash
AGENT_BROWSER_SESSION=default        # 会话名称
AGENT_BROWSER_PROFILE=~/.browser     # 持久化配置
AGENT_BROWSER_EXECUTABLE_PATH=/path  # 自定义浏览器路径
```

## 兼容的 AI 平台
- Claude Code
- Cursor
- GitHub Copilot
- OpenAI Codex
- Google Gemini
- opencode
- 任何可以运行 shell 命令的 AI agent
