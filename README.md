# nekro-cc-sandbox

`nekro-cc-sandbox` 是一个基于 **Claude Code** 的持久化工作区沙盒服务，用于为上层 Agent 系统提供可隔离、可持续、可流式返回的任务执行环境。

它适合被用作：

- Claude Code 的 API 化执行后端
- 持久化 workspace / sandbox runtime
- 上层 Agent 编排系统的执行层
- 带会话、工具探测、任务排队能力的工作区服务

如果你在搜索这些关键词：

- `Claude Code sandbox`
- `Claude Code workspace backend`
- `persistent workspace agent`
- `agent sandbox runtime`
- `nekro cc sandbox`

这个项目就是对应实现。

与 **Nekro Agent** 生态的关系：

- `nekro-cc-sandbox` 可以独立理解和开发
- 它同时也是 **[KroMiose/nekro-agent](https://github.com/KroMiose/nekro-agent)** 工作区执行链路的重要基础组件
- 如果你想看完整的多平台 Agent 编排系统，可以继续访问主项目：<https://github.com/KroMiose/nekro-agent>

## 这个项目解决什么问题

Claude Code 很强，但在真实系统里直接把 CLI 裸接到业务层通常会遇到这些问题：

- 缺少稳定的 API 封装
- 会话上下文不易持久化
- 多任务并发时容易互相干扰
- 缺少工作区隔离与状态管理
- 不方便接入上层 WebUI、SSE 和调度系统

`nekro-cc-sandbox` 的作用，就是把 Claude Code 包装成一个更适合系统集成的工作区执行服务：

```text
Client / Agent Orchestrator
  -> nekro-cc-sandbox API
  -> Workspace Manager
  -> Claude Runtime
  -> Claude Code CLI
  -> JSON / SSE / Status / Shell
```

## 核心能力

- **持久化工作区**：每个 workspace 有独立目录、独立会话和独立运行上下文
- **Claude Code Runtime**：通过 `claude -p` 驱动 Claude Code CLI 完成任务执行
- **流式消息接口**：支持 SSE 持续输出文本片段、工具调用和工具结果
- **任务排队机制**：同一工作区内自动串行化任务，避免上下文污染
- **工具能力探测**：独立查询和刷新 Claude Code 当前可用工具列表
- **会话重置**：支持按 workspace 清空当前 Claude 会话
- **运行策略控制**：支持 `agent`、`relaxed`、`strict` 三种 runtime policy
- **交互式 Shell**：用于调试沙盒内真实环境
- **Web 调试界面**：便于本地验证状态、消息和工作区行为
- **待投递结果暂存**：为上层系统断连场景提供容灾缓冲

## 典型场景

- 给上层 AI Agent 系统提供执行层
- 为 Claude Code 构建 HTTP / SSE 服务化封装
- 做持久化 workspace agent 研究
- 做自动化代码任务、文件任务、工具调用任务编排
- 做独立的 Agent sandbox / runtime backend

## 项目结构

```text
nekro_cc_sandbox/
├── src/nekro_cc_sandbox/
│   ├── api/            # FastAPI 路由：消息、状态、SSE、shell
│   ├── claude/         # Claude Runtime 与运行策略
│   ├── workspace/      # 工作区管理
│   ├── shell/          # 交互式 shell
│   ├── store/          # 暂存与状态存储
│   └── main.py         # 应用入口
├── frontend/           # 本地调试前端
├── tests/              # 单元、集成、E2E 测试
├── Dockerfile
└── pyproject.toml
```

## API 概览

常用接口：

- `POST /api/v1/message`
- `POST /api/v1/message/stream`
- `GET /api/v1/capabilities/tools`
- `POST /api/v1/capabilities/tools/refresh`
- `POST /api/v1/workspaces/{workspace_id}/session/reset`
- `GET /api/v1/status`
- `GET /health`

接口职责：

- `/api/v1/message`：非流式调用 Claude Code
- `/api/v1/message/stream`：流式执行任务并返回 SSE 事件
- `/api/v1/capabilities/tools`：读取工具能力缓存
- `/api/v1/capabilities/tools/refresh`：主动刷新工具能力
- `/api/v1/workspaces/{workspace_id}/session/reset`：重置工作区会话

## 本地开发

环境要求：

- Python `>= 3.13`
- `uv`
- Node.js 与 `pnpm`（如需运行前端）
- 可用的 `claude` CLI

安装依赖：

```bash
uv sync --all-extras
```

启动开发服务：

```bash
poe dev
```

运行检查：

```bash
poe lint
poe typecheck
poe test
poe check
```

前端调试：

```bash
poe frontend-install
poe frontend-dev
```

## Docker

构建镜像：

```bash
poe docker-build
```

本地运行：

```bash
poe docker-run
```

如果你是从 **[KroMiose/nekro-agent](https://github.com/KroMiose/nekro-agent)** 生态了解这个项目，通常它会作为工作区沙盒容器由主系统自动管理，而不是手工长期单独运行。

## 环境变量

常用配置项：

- `WORKSPACE_ROOT`：工作区根目录
- `SETTINGS_PATH`：设置文件路径
- `RUNTIME_POLICY`：运行策略，支持 `agent` / `relaxed` / `strict`
- `SKIP_PERMISSIONS`：是否跳过权限确认
- `HOST`：监听地址
- `PORT`：监听端口

默认推荐使用 `agent` 模式，它更适合被上层系统编排调用，而不是给人类直接做交互式终端使用。

## 为什么这个项目适合做执行后端

相比直接调用 Claude Code CLI，`nekro-cc-sandbox` 多提供了几层系统化能力：

- 对外稳定的 HTTP API
- 工作区隔离与目录管理
- 会话生命周期管理
- 流式事件协议
- 任务并发控制
- 状态查询与调试能力

这使它更适合接入 Agent 平台、工作流系统或自定义编排层。

## 生态链接

- 主项目 `KroMiose/nekro-agent`: <https://github.com/KroMiose/nekro-agent>
- 文档站: <https://doc.nekro.ai>
- NekroAI 云社区: <https://cloud.nekro.ai>

## License

请以当前仓库中的 License 文件和相关说明为准。
