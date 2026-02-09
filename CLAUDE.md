# CLAUDE.md

本文档为 Claude Code (claude.ai/code) 提供项目指导。

---

## 项目概述

**nekro-cc-sandbox** 是基于 Claude Code 的持久化工作区 Agent，提供 Web 界面和 API，可在隔离的工作区中运行 Claude Code 并保持会话持久性。

---

## 开发规范

### 依赖管理

- **必须使用 `uv add <包名>` 添加生产依赖**
- **必须使用 `uv add --dev <包名>` 添加开发依赖**
- **禁止直接编辑 `pyproject.toml` 添加依赖**
- 前端依赖必须使用 `pnpm add <包名>` 添加

### 文档自更新规则

当发生以下情况时，**必须**立即更新本文档：

1. 添加了新的命令（`pyproject.toml` 中的 poe tasks）
2. 新增了环境变量
3. 发现并修复了 bug，记录解决方案
4. 引入了新的 API 端点
5. 修改了架构或数据流
6. 任何可能影响其他开发者理解的变更

### 测试规范

- **每次代码修改后必须运行 `poe check`**
- 确保 lint、typecheck、test 全部通过
- 新增功能必须配套测试用例

---

## 命令

```bash
# 安装所有依赖
uv sync --all-extras

# 安装单个依赖（必须使用此方式，禁止直接编辑 pyproject.toml）
uv add <包名>
uv add --dev <包名>

# 前端依赖（必须使用此方式）
pnpm add <包名>

# 运行开发服务器（热重载）
poe dev

# 运行测试
poe test

# 运行 linter
poe lint

# 自动修复 lint 问题
poe lint-fix

# 运行类型检查
poe typecheck

# 运行所有检查
poe check

# Docker 构建
poe docker-build
poe docker-run

# 前端命令
poe frontend-install # 安装前端依赖
poe frontend-dev # 前端开发服务器
poe frontend-build # 构建前端
poe frontend-typecheck # 前端类型检查
poe frontend-lint # 前端 lint
poe frontend-check # 前端检查
poe frontend-preview # 预览构建
```

---

## 架构

```
Client --> FastAPI (main.py) --> API Routers --> ClaudeRuntime --> Claude Code subprocess
 |
 v
WorkspaceManager --> workspaces/
```

### 核心组件

| 组件 | 文件 | 说明 |
|------|------|------|
| FastAPI 应用 | `src/nekro_cc_sandbox/main.py` | 入口点，含生命周期管理、CORS、挂载前端 |
| API 层 | `src/nekro_cc_sandbox/api/` | 消息、状态、SSE 事件的 REST 端点 |
| Claude Runtime | `src/nekro_cc_sandbox/claude/runtime.py` | 管理每个工作区的 Claude Code 子进程 |
| 工作区管理器 | `src/nekro_cc_sandbox/workspace/manager.py` | 创建/管理持久化工作区 |
| 运行时策略 | `src/nekro_cc_sandbox/claude/policy.py` | 控制 Agent 能力（宽松/严格/agent 模式） |
| 设置模块 | `src/nekro_cc_sandbox/settings.py` | API 提供商配置管理 |

### 数据流

1. 客户端通过 `/api/v1/message` 发送消息
2. API 路由到 `ClaudeRuntime` 生成子进程
3. Claude Code 在隔离工作区中运行
4. 结果通过 JSON 响应返回

---

## Claude Code 能力探测与会话管理（后端对齐）

### 工具列表（与聊天会话解耦）

- `GET /api/v1/capabilities/tools`
  - **用途**：读取当前“工具列表缓存”。不触发新的探测/初始化。
- `POST /api/v1/capabilities/tools/refresh`
  - **用途**：独立触发 Claude Code 工具列表探测（`--no-session-persistence`），并刷新缓存。

> 设计约束：工具列表探测必须**独立于聊天 session**，避免“为了拿工具列表先发一条聊天消息”这种耦合与误导。

### 重置工作区会话

- `POST /api/v1/workspaces/{workspace_id}/session/reset`
  - **用途**：清空指定工作区的对话 session（前端用于“重置会话”按钮）。

### CLI 参数约束（工具白名单）

- 当运行时策略配置了 `allowed_tools` 时，后端调用 `claude` 使用 `--tools <comma-separated>` 来**真正限制可用工具**。
- 不要把 `--allowedTools/--allowed-tools` 误当成白名单开关（语义与期望不一致，会导致策略失真）。

---

## 依赖注入

通过 `app.state` 注入组件：

- `workspace_manager`: 全局工作区管理
- `claude_runtime`: Claude Code 子进程处理
- `settings`: 应用程序设置
- `shell_manager`: 交互式 shell 会话管理

---

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `WORKSPACE_ROOT` | 工作区根目录 | `./workspaces` |
| `SKIP_PERMISSIONS` | 跳过权限提示 | `false` |
| `DEBUG` | 启用调试模式 | `false` |
| `SETTINGS_PATH` | 设置文件路径 | `./data/settings.json` |
| `HOST` | 服务器绑定地址 | `0.0.0.0` |
| `PORT` | 服务器端口 | `7021` |
| `RUNTIME_POLICY` | 运行时能力策略（`agent`/`relaxed`/`strict`） | `agent` |

### RUNTIME_POLICY 说明

- `agent`：面向“对外提供的非交互自动运行沙盒”的默认策略。特点是**明确工具白名单**，并禁用一组交互型工具，避免 CLI 进入等待交互导致卡死。
- `relaxed`：开发用宽松策略（默认不做工具层面的限制）。
- `strict`：生产用收敛策略（禁用写文件/命令执行/网络等）。

---

## 日志

- 日志目录: `./data/logs/`
- 主日志文件: `app.log`
- 自动轮转: 文件达到 10MB 时截断
- 保留策略: 10 个压缩归档（.gz）
- 编码: UTF-8

### 日志格式

```
2026-02-04 15:55:13,135 [INFO] → GET /api/v1/status
2026-02-04 15:55:13,136 [INFO] ← GET /api/v1/status - 200
```

### 查看日志的正确方式

```bash
# 实时查看最新日志（推荐）
tail -f data/logs/app.log

# 查看最近 50 行
tail -n 50 data/logs/app.log

# 查看所有日志文件（包括压缩归档）
ls -la data/logs/

# 解压查看历史日志
gunzip -c data/logs/app.log.1.gz | tail

# 搜索错误信息
grep -i error data/logs/app.log

# 统计错误数量
grep -c "ERROR" data/logs/app.log
```

---

## 扩展性

- **MCP 服务器** (`extensions/mcp.py`): Model Context Protocol 服务器管理
- **技能** (`extensions/skills.py`): 从 YAML 配置加载技能

---

## 已记录的问题与解决方案

### 1. TestClient 与 lifespan 状态隔离

**问题**: `TestClient` 创建独立的作用域，不会与 lifespan 共享 `app.state`

**症状**: 测试中 `request.state.claude_runtime` 为 `None`

**解决方案**: 使用 `request.app.state.claude_runtime` 替代 `request.state.claude_runtime`

**参考**: `src/nekro_cc_sandbox/api/messages.py`

### 2. AsyncMock 返回值配置

**问题**: `AsyncMock()` 默认返回不可等待的对象

**症状**: `RuntimeWarning: coroutine was never awaited`

**解决方案**: 为 `AsyncMock` 设置 `return_value`

```python
_mock_runtime.start = AsyncMock(return_value=_mock_session)
```

**参考**: `tests/integration/test_api.py`

### 3. pytest autouse fixture 状态泄漏

**问题**: `autouse=True` 的 fixture 在测试间可能泄漏状态

**症状**: `test_send_message_no_runtime` 失败（runtime 未被清理）

**解决方案**: 在测试前显式清理状态

```python
def test_send_message_no_runtime(self):
    if hasattr(app.state, "claude_runtime"):
        del app.state.claude_runtime
```

**参考**: `tests/integration/test_api.py`

### 4. Vite 代理配置

**问题**: `/docs` 等端点未被代理

**症状**: FastAPI 文档页面显示 HTML 片段

**解决方案**: 在 `vite.config.ts` 中添加所有需要代理的路径（含 WebSocket）

```typescript
proxy: {
  "/api": { target: "http://localhost:7021", ws: true },
  "/docs": { target: "http://localhost:7021" },
  "/openapi.json": { target: "http://localhost:7021" },
  "/redoc": { target: "http://localhost:7021" },
}
```

**参考**: `frontend/vite.config.ts`

### 5. 请求状态访问路径

**问题**: `request.state` 与 `request.app.state` 是不同对象

**症状**: "Claude runtime not available" 错误

**解决方案**: 从 `request.app.state` 获取应用级状态

```python
runtime = getattr(request.app.state, "claude_runtime", None)
```

**参考**: `src/nekro_cc_sandbox/api/messages.py`

### 6. 前端 API 代理端口

**问题**: 前端 vite 代理端口与后端不匹配

**症状**: 前端显示 "已断开"

**解决**: 确保 `vite.config.ts` 中 `/api` 代理到正确的后端端口

### 7. 使用 poe 命令执行检查

**问题**: 直接在命令行执行前端检查命令

**解决**: 必须使用 `poe frontend-typecheck` 等 poe 命令

### 8. Claude Code CLI：pipe/无 TTY 场景会卡住 & stream-json schema 与假设不一致

**问题**:

- 在部分环境中，`claude -p` 运行在 stdin/stdout 为 pipe（无 TTY）时可能卡住无输出
- `--output-format stream-json` 的真实输出结构与“顶层 tool_use/tool_result/text”这类假设不同

**解决方案**:

- 后端改为“一次请求一次 `claude -p` 调用”，并用 pseudo-tty 包装（例如 `script -q -c ... /dev/null`）以稳定行为
- 解析 `stream-json` 时以实测 schema 为准：增量文本来自 `stream_event.content_block_delta(text_delta)`；工具调用/结果出现在 `assistant.message.content[].tool_use` 与 `type=user` 的 `tool_result` 中

**参考**: `.cursor/docs/knowledge.md`

### 9. provider 真实 API 测试默认不应阻塞 `poe check`

**问题**: `tests/providers/` 下的测试依赖真实密钥，默认执行会导致无密钥环境失败。

**解决方案**: 引入 `--enable-provider-tests` 开关；未开启时自动跳过 `@pytest.mark.provider`。

**参考**: `tests/conftest.py`

### 10. `/api/v1/message` 不能 `success=true` 但返回空 `message`

**问题**: CLI 输出路径多样，若仅依赖 delta，可能出现 `success=true` 但 `message=""` 的“无反馈”。

**解决方案**:

- 后端兜底解析 `assistant` 快照与最终 `result.result`
- 若最终仍无可解析文本，返回明确失败（包含 `err_id`）

**参考**: `src/nekro_cc_sandbox/claude/runtime.py`、`src/nekro_cc_sandbox/api/messages.py`

### 11. Claude CLI `--resume` 会话不存在：自动降级重试

**问题**: `--resume` 指向不存在会话时，继续持久化该 `session_id` 会导致“永远失败”。

**解决方案**:

- 仅在成功 result 时持久化 `session_id`
- 识别 `errors[]` 包含 `No conversation found with session ID`，清空 workspace 的 `session_id` 并自动重试一次（不带 `--resume`）

**参考**: `src/nekro_cc_sandbox/claude/runtime.py`

### 12. 错误处理协议（早期架构规范）

**目标**: 任何失败都必须“可定位、可恢复、可展示”，避免前端只能得到一段字符串。

**约束**:

- 后端统一返回结构化错误（`err_id/code/message/retryable/details`）
- 禁止捕获异常后返回“无 schema dict”（会破坏 OpenAPI 契约）

**参考**: `src/nekro_cc_sandbox/api/schemas.py`、`src/nekro_cc_sandbox/main.py`

### 13. 容器内 Shell 面板（持久交互）

**用途**: 供外部项目/使用者在容器内进行资源检查与必要操作（交互式、可持续）。

**后端接口**:

- `POST /api/v1/shells`
- `GET /api/v1/shells`
- `DELETE /api/v1/shells/{id}`
- `WS /api/v1/shells/{id}/ws`

**参考**: `src/nekro_cc_sandbox/shell/manager.py`、`src/nekro_cc_sandbox/api/shells.py`、`frontend/src/components/ShellPanel.tsx`

### 14. 工具列表探测失败（--init-only 无输出）与 500 错误无 schema

**问题**:

- `claude --init-only --output-format stream-json` 实测不会产生可解析的 `system.init` 对象
- 中间件吞异常返回 `{"error":"..."}` 会导致 OpenAPI 无稳定 schema

**解决方案**:

- 工具探测改为 `claude -p ... --no-session-persistence -- ping`，从 `system.init.tools` 读取后立即终止进程
- 统一异常处理：`AppError`/未知异常返回 `status="error"` + `ErrorInfo`

**参考**: `src/nekro_cc_sandbox/claude/runtime.py`、`src/nekro_cc_sandbox/main.py`

### 15. Docker 构建与容器启动（前后端一体）常见坑

**问题**:

- `ghcr.io/astral-sh/uv` 镜像无 `/bin/sh`，不能直接用于包含 `RUN ...` 的 build stage
- `pnpm install` 在无 TTY 的 Docker build 场景会中止（需要 `CI=true`）
- bind mount 的 `WORKSPACE_ROOT` 若对 `appuser` 不可写，会导致启动时 `PermissionError`

**解决方案**:

- `uv` 镜像仅作为 uv 二进制来源（`COPY --from=uv-bin /uv ...`），依赖安装在 `python:3.13-slim` 阶段执行
- 前端构建阶段设置 `ENV CI=true` 并使用 `pnpm install --frozen-lockfile`
- 增加 `docker-entrypoint.sh`：检测 `WORKSPACE_ROOT` 对 `appuser` 的写权限，不可写则尝试 `chown`，随后以 `appuser` 启动

**参考**: `Dockerfile`、`docker-entrypoint.sh`

---

## 注意事项速查

1. **依赖添加必须用 `uv add` / `pnpm add`**
2. **每次修改后运行 `poe check`**
3. **lifespan 中初始化的对象用 `request.app.state.xxx` 访问**
4. **测试 fixture 清理要显式处理**
5. **前端代理要包含 `/docs` 等文档路径**
6. **新增内容立即更新本文档**
7. **严格禁止猜测任何接口、外部系统行为、参数等信息，必须通过权威文档或实际测试验证**
