# Claude Code 知识文档

本文档汇总和整理 Claude Code 的相关知识信息，皆在辅助于通过外部程序控制 Claude Code 行为，作为 Agent 中枢的研究

> 官方文档: `https://code.claude.com/docs`

## 全流程导航（从配置到使用）

- 安装与基础检查：见下文“安装 Claude Code”“CLI：已验证的可复现实验”
- 认证/凭证：优先参考 IAM 与 Setup（不同组织/计费方式差异很大）
- 配置（用户/项目/本地/托管）：见“配置 Claude Code（官方）”
- 第三方提供商（LLM gateway / OpenAI compatible / MiniMax 等）：见“第三方提供商配置范式”
- 使用（交互模式 / 脚本 -p / 输出格式 / 会话恢复）：见“使用 Claude Code（官方 + 实测）”
- 自动化（Hooks/权限/沙箱）：见“Hooks（全自动工作流的‘发动机’）”“权限与沙箱”
- 集成到本项目：见“对本项目集成的直接结论（必须读）”

## 结论优先（对本项目最关键）

### 1) `claude` 在“无 TTY / 管道模式”下可能卡住

**已验证现象（本机 2026-02-04 / Claude Code 2.1.29）**：
- 直接运行（stdin/stdout 是 pipe）：
  - `claude -p "只回复 pong"` **无输出并长期卡住**（需要 `timeout` 强制退出）
- 提供 pseudo-tty（让进程认为自己在真实终端里）：
  - `script -q -c 'claude -p "只回复 pong"' /dev/null` **可正常返回 `pong`**

这对 `src/nekro_cc_sandbox/claude/runtime.py` 影响极大：当前实现用 `asyncio.create_subprocess_exec(..., stdin=PIPE, stdout=PIPE)` 启动 `claude`，等价于“无 TTY / 管道模式”，因此**非常可能复现“无输出卡住”**。后续要做“全自动工作流”，必须先解决 **PTY/伪终端** 启动方式或使用官方推荐的 headless/SDK 路线。

相关参考：
- CLI 参考: `https://code.claude.com/docs/zh-CN/cli-reference`
- 编程使用（Headless / Agent SDK CLI）: `https://code.claude.com/docs/zh-CN/headless`
- `claude --help`（本机输出）中明确 `-p/--print` 为非交互，但仍可能受 TTY 影响（见上方实测）。

### 2) `--print` + `--output-format=stream-json` 需要 `--verbose`

**已验证**：当使用 `--print` 且 `--output-format=stream-json`，若未指定 `--verbose`，会报错：
`Error: When using --print, --output-format=stream-json requires --verbose`

这与本项目 runtime 当前的启动参数（`--output-format stream-json --verbose`）是匹配的。

## 对本项目集成的直接结论（必须读）

本项目当前 `ClaudeRuntime` 采用 `stdin=PIPE/stdout=PIPE` 方式启动 `claude`（等价“无 TTY / 管道模式”），**非常可能触发“卡住无输出”**。要做“全自动开发工作流”，优先级最高的是：

- **优先选项 A（推荐）**：用 **PTY/伪终端** 启动 `claude` 子进程（确保 `-p`/JSON/stream-json 行为可预测）
- **选项 B**：改用官方 Agent SDK（Python/TS）做程序化控制（依旧要验证在 CI/无 TTY 场景下的行为边界）

在解决 PTY 之前，任何“流式输出、会话恢复、hooks 自动化”都会不稳定，属于在沙地上盖楼。

## 安装 Claude Code

推荐使用 Node 20

```bash
curl -fsSL https://claude.ai/install.sh | bash
```

## 认证/凭证（官方入口）

Claude Code 的“认证方式”因你接入的提供商不同而不同（Claude.ai/Console、Bedrock、Vertex、Foundry、LLM gateway 等）。官方总入口：
- IAM（权限/认证概览）：`https://code.claude.com/docs/zh-CN/iam`
- Setup（安装/登录/组织）：`https://code.claude.com/docs/zh-CN/setup`

本文档**不重复**各云厂商 IAM 细节，只记录“本项目集成需要知道的行为事实”和“可复现命令”。

## 配置 Claude Code（官方）

### 配置作用域与文件位置（官方）

Claude Code 的配置按作用域分层（优先级从高到低）：
- **Managed**（系统级，管理员下发，不可覆盖）
- **命令行参数**（一次会话临时覆盖）
- **Local**：`.claude/settings.local.json`（gitignored，个人在当前仓库的覆盖）
- **Project**：`.claude/settings.json`（提交到 git，团队共享）
- **User**：`~/.claude/settings.json`（个人全局）

参考：`https://code.claude.com/docs/zh-CN/settings`

### 常见设置能力（官方）

- **env 注入**：可在 `settings.json` 的 `env` 字段为每个会话注入环境变量（同样也可通过进程环境变量注入）
- **permissions**：用 allow/ask/deny 规则控制工具权限
- **hooks**：围绕工具调用/会话生命周期执行命令（做自动化工作流非常关键）

参考：
- 设置: `https://code.claude.com/docs/zh-CN/settings`
- IAM/权限: `https://code.claude.com/docs/zh-CN/iam`
- Hooks: `https://code.claude.com/docs/zh-CN/hooks`

## 第三方提供商配置范式（从“配置”到“可用”）

> 目标：让 `claude` 的模型请求走你选择的提供商/网关（例如 MiniMax 的 Anthropic 兼容网关、OpenAI compatible 网关、本地 Ollama / LM Studio 等）。

### 1) 两条主路径（建议二选一，别混用）

- **路径 A：环境变量（最直观，便于容器/CI 注入）**
  - 在启动 `claude` 的进程环境中设置（或由 `settings.json` 的 `env` 字段统一注入）
- **路径 B：设置文件（User/Project/Local/Managed）**
  - `~/.claude/settings.json` 或 `.claude/settings.json` 中的 `env`（项目可共享、可审计）

官方说明（env 可在 settings.json 中配置）：`https://code.claude.com/docs/zh-CN/settings#环境变量`

### 2) MiniMax（示例：Anthropic 兼容网关）

下面示例仅展示“字段形态”和“配置意图”，请把 `MINIMAX_API_KEY` 替换为你自己的凭证（**不要提交到仓库**）。

推荐放在 **用户设置**（`~/.claude/settings.json`）或 **本地项目设置**（`.claude/settings.local.json`）。

```jsonc
{
  "env": {
    "ANTHROPIC_BASE_URL": "https://api.minimaxi.com/anthropic",
    "ANTHROPIC_AUTH_TOKEN": "MINIMAX_API_KEY",
    "API_TIMEOUT_MS": "3000000",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": 1,
    "ANTHROPIC_MODEL": "MiniMax-M2.1",
    "ANTHROPIC_SMALL_FAST_MODEL": "MiniMax-M2.1",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "MiniMax-M2.1",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "MiniMax-M2.1",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "MiniMax-M2.1"
  }
}
```

补充：
- 你也可以通过 CLI 参数 `--settings <file>` 加载额外 settings（适合自动化脚本临时覆盖）。
- 更复杂的“网关形态/自定义 header”等请查官方 `ANTHROPIC_CUSTOM_HEADERS`、`LLM gateway` 相关文档（在 settings 文档的环境变量列表里有入口）。

### 3) `.claude.json` 与“项目状态/缓存”

官方说明：`~/.claude.json` 用于存放偏好设置、OAuth 会话、MCP 配置（用户/本地作用域）、项目状态等；**不要依赖未公开字段作为稳定接口**。
参考：`https://code.claude.com/docs/zh-CN/settings#设置文件`

## Hooks（全自动工作流的“发动机”）

> 目标：让 Claude Code 在**每次工具调用前后**自动执行校验/格式化/安全策略，并能在违反规则时阻断。

### 配置位置（官方）

Hooks 写在 `settings.json` 中的 `hooks` 字段，支持用户/项目/本地三层：
- `~/.claude/settings.json`
- `.claude/settings.json`
- `.claude/settings.local.json`

参考：`https://code.claude.com/docs/zh-CN/hooks`、`https://code.claude.com/docs/zh-CN/settings`

### 事件模型（官方）

常用事件：
- **PreToolUse**：工具执行前（可拦截/自动批准/修改输入）
- **PermissionRequest**：弹权限对话框时（可代替用户允许/拒绝）
- **PostToolUse**：工具成功后（可向 Claude 注入额外上下文或阻断继续）
- **UserPromptSubmit**：用户提交提示时（可注入上下文或阻断提示）
- **Stop / SubagentStop**：Claude 要停止时（可要求继续）
- **SessionStart / SessionEnd**：会话开始/结束（适合注入上下文、准备环境、清理）

### Hook 的“返回控制”（官方关键点）

- **退出码 0**：成功。部分事件下 stdout 会被加入上下文（如 `UserPromptSubmit`、`SessionStart`）。
- **退出码 2**：阻断（不同事件行为不同，PreToolUse 会直接阻止工具执行并把 stderr 展示给 Claude）。
- **stdout JSON（退出码 0 才解析）**：可用结构化字段控制 allow/deny/ask、追加上下文等。

### 实施建议（用于本项目后续工作）

- 用 **PreToolUse + PermissionRequest** 组合实现“无需人工干预但仍可控”的自动化（例如只允许 `poe check`、禁止 `git push`、禁止读 `.env`）。
- 用 **SessionStart** 写入 `CLAUDE_ENV_FILE`，让后续每次 Bash 都自动具备一致环境（参考 settings 文档里对 `CLAUDE_ENV_FILE` 的说明）。

## 权限与沙箱（自动化需要的安全地基）

- 权限模型（allow/ask/deny、权限模式 default/acceptEdits/plan/dontAsk/bypassPermissions）：`https://code.claude.com/docs/zh-CN/iam`
- settings.json 权限规则语法与优先级：`https://code.claude.com/docs/zh-CN/settings`
- bash 沙箱隔离（bubblewrap/seatbelt、逃生舱 dangerouslyDisableSandbox 等）：`https://code.claude.com/docs/zh-CN/sandboxing`

实践建议（面向“全自动工作流”）：
- **用 permissions + hooks 做双保险**：权限提供静态边界，hooks 提供动态校验与阻断。
- **禁止把安全寄托在 Bash 参数匹配上**：官方明确 Bash 规则很脆弱（可被参数位置/变量/重定向等绕过）；对域名限制优先用 WebFetch 规则或 PreToolUse hook 解析命令内容。

## 使用 Claude Code（官方 + 实测）

### 交互模式（官方）

交互模式的快捷键/内置命令（`/hooks`、`/permissions`、`/tasks`、`/rewind` 等）参考：
`https://code.claude.com/docs/zh-CN/interactive-mode`

### 脚本/CI 用法（官方）

官方将 `claude -p` 归类为 Agent SDK CLI（曾称 headless），入口：
`https://code.claude.com/docs/zh-CN/headless`

## 输出协议手册（字段 schema 级别，Claude Code 2.1.29 实测）

> 目标：给“外部开发 agent / 程序”一个**可以直接实现解析器**的稳定参考。
>
> 注意：Claude Code 的输出除了 JSON 之外，可能夹杂终端控制序列（尤其在 pseudo‑tty 下）。因此：
> - **`--output-format json`**：建议“只解析第一行 JSON”，忽略后续残留。
> - **`--output-format stream-json`**：建议“逐行解析 JSONL”，忽略以 `[` 开头的残留行与空行。

### 1) `--output-format text`（实测）

文件样例：`tmp/claude-cli-lab/01_text.sanitized.txt`

**语义**：stdout 主要是模型的最终文本（例如 `pong`），但尾部可能有残留控制字符（实测出现 `[` 开头残留）。

### 2) `--output-format json`：Result Object（实测 schema）

样例：`tmp/claude-cli-lab/02_json.sanitized.txt` 第一行（JSON）

#### 顶层字段与类型（实测）

- `type`: string（固定为 `"result"`）
- `subtype`: string（例如 `"success"`）
- `is_error`: boolean
- `duration_ms`: integer
- `duration_api_ms`: integer
- `num_turns`: integer
- `result`: string（最终文本输出）
- `session_id`: string（UUID）
- `total_cost_usd`: number
- `usage`: object（见下）
- `modelUsage`: object（以模型名为 key 的 map，见下）
- `permission_denials`: array（实测为 `[]`）
- `uuid`: string（UUID）

#### `usage` 字段（实测）

- `usage.input_tokens`: integer
- `usage.output_tokens`: integer
- `usage.cache_creation_input_tokens`: integer
- `usage.cache_read_input_tokens`: integer
- `usage.service_tier`: string（例如 `"standard"`）
- `usage.server_tool_use`: object
  - `usage.server_tool_use.web_search_requests`: integer
  - `usage.server_tool_use.web_fetch_requests`: integer
- `usage.cache_creation`: object
  - `usage.cache_creation.ephemeral_1h_input_tokens`: integer
  - `usage.cache_creation.ephemeral_5m_input_tokens`: integer

#### `modelUsage` 字段（实测）

结构为：`{ "<model_name>": ModelUsageEntry }`

`ModelUsageEntry`（实测字段）：
- `inputTokens`: integer
- `outputTokens`: integer
- `cacheReadInputTokens`: integer
- `cacheCreationInputTokens`: integer
- `webSearchRequests`: integer
- `costUSD`: number
- `contextWindow`: integer
- `maxOutputTokens`: integer

#### JSON Schema（可直接用于校验器）

```jsonc
{
  "type": "object",
  "required": ["type", "subtype", "is_error", "duration_ms", "num_turns", "result", "session_id", "usage", "modelUsage", "uuid"],
  "properties": {
    "type": { "const": "result" },
    "subtype": { "type": "string" },
    "is_error": { "type": "boolean" },
    "duration_ms": { "type": "integer" },
    "duration_api_ms": { "type": "integer" },
    "num_turns": { "type": "integer" },
    "result": { "type": "string" },
    "session_id": { "type": "string" },
    "total_cost_usd": { "type": "number" },
    "permission_denials": { "type": "array" },
    "uuid": { "type": "string" },
    "usage": {
      "type": "object",
      "required": ["input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "server_tool_use", "service_tier", "cache_creation"],
      "properties": {
        "input_tokens": { "type": "integer" },
        "output_tokens": { "type": "integer" },
        "cache_creation_input_tokens": { "type": "integer" },
        "cache_read_input_tokens": { "type": "integer" },
        "service_tier": { "type": "string" },
        "server_tool_use": {
          "type": "object",
          "required": ["web_search_requests", "web_fetch_requests"],
          "properties": {
            "web_search_requests": { "type": "integer" },
            "web_fetch_requests": { "type": "integer" }
          }
        },
        "cache_creation": {
          "type": "object",
          "required": ["ephemeral_1h_input_tokens", "ephemeral_5m_input_tokens"],
          "properties": {
            "ephemeral_1h_input_tokens": { "type": "integer" },
            "ephemeral_5m_input_tokens": { "type": "integer" }
          }
        }
      }
    },
    "modelUsage": {
      "type": "object",
      "additionalProperties": {
        "type": "object",
        "required": ["inputTokens", "outputTokens", "cacheReadInputTokens", "cacheCreationInputTokens", "webSearchRequests", "costUSD", "contextWindow", "maxOutputTokens"],
        "properties": {
          "inputTokens": { "type": "integer" },
          "outputTokens": { "type": "integer" },
          "cacheReadInputTokens": { "type": "integer" },
          "cacheCreationInputTokens": { "type": "integer" },
          "webSearchRequests": { "type": "integer" },
          "costUSD": { "type": "number" },
          "contextWindow": { "type": "integer" },
          "maxOutputTokens": { "type": "integer" }
        }
      }
    }
  }
}
```

### 3) `--output-format stream-json`：JSONL 事件流（实测 schema）

样例：`tmp/claude-cli-lab/03_stream.sanitized.jsonl`

#### 3.0) 一个容易踩坑：带“变长参数”的 flag 会吞掉 prompt

以下 flag 在 CLI 中是 **变长参数**（会消耗后续位置参数），例如：
- `--tools <tools...>`
- `--allowedTools <tools...>` / `--disallowedTools <tools...>`
- `--add-dir <directories...>` 等

**实测现象**：如果不加 `--` 分隔符，后面的 prompt 可能被当成该 flag 的参数，从而报错：
`Error: Input must be provided either through stdin or as a prompt argument when using --print`

**推荐写法（在 prompt 前加 `--`）**：

```bash
claude -p --output-format json --disallowedTools "Read" -- "你的 prompt..."
```

#### 顶层“事件类型”集合（实测）

在一次请求中实测出现四类顶层对象：
- `type="system"`（init）
- `type="stream_event"`
- `type="assistant"`（聚合态 message 快照）
- `type="result"`（最终汇总，同 `--output-format json`）

另外，在开启 `--include-partial-messages` 且发生工具调用时，实测还会出现：
- `type="user"`（注意：这里的 `user` 是“工具结果回填”，不一定来自真实用户输入）

#### 3.1) 两种 stream-json 形态：是否开启 `--include-partial-messages`

**形态 A：不加 `--include-partial-messages`**
- 仍是 JSONL（逐行 JSON）
- 更偏“按轮次输出 message 快照”，常见顶层类型：`system` / `assistant` / `user` / `result`
- 适合只关心最终文本与工具结果的场景

**形态 B：加 `--include-partial-messages`（推荐用于精细流式解析）**
- 顶层会额外出现大量 `type="stream_event"` 的增量事件（message_start/delta/stop 等）
- 同时仍会穿插 `assistant`（message 聚合快照）与 `user`（tool_result 回填）

#### `system.init`（实测）

字段（实测均存在）：
- `type`: `"system"`
- `subtype`: `"init"`
- `cwd`: string
- `session_id`: string
- `tools`: string[]
- `mcp_servers`: array
- `model`: string
- `permissionMode`: string（例如 `"default"`）
- `slash_commands`: string[]
- `apiKeySource`: string（实测 `"none"`）
- `claude_code_version`: string（例如 `"2.1.29"`）
- `output_style`: string
- `agents`: string[]
- `skills`: array
- `plugins`: array
- `uuid`: string

#### `stream_event`（实测）

公共字段：
- `type`: `"stream_event"`
- `event`: object（见下）
- `session_id`: string
- `parent_tool_use_id`: null | string（实测为 null）
- `uuid`: string

本次样例中 `event.type` 分布（实测）：
- `message_start`
- `content_block_start`
- `content_block_delta`
- `content_block_stop`
- `message_delta`
- `message_stop`

`content_block_start`：
- `event.index`: integer
- `event.content_block.type`: `"thinking"` | `"text"`
- `event.content_block.thinking` 或 `event.content_block.text`: string

`content_block_delta`：
- `event.index`: integer
- `event.delta.type`: `"thinking_delta"` | `"text_delta"` | `"signature_delta"`
- `event.delta.thinking` / `event.delta.text` / `event.delta.signature`: string

`message_delta`：
- `event.delta.stop_reason`: string（实测 `"end_turn"`）
- `event.usage.*`: integer（实测：`input_tokens`/`output_tokens`/`cache_creation_input_tokens`/`cache_read_input_tokens`）

#### `assistant`（实测）

公共字段：
- `type`: `"assistant"`
- `message`: object
- `session_id`: string
- `parent_tool_use_id`: null | string
- `uuid`: string

`message`（实测字段）：
- `id`: string
- `type`: `"message"`
- `role`: `"assistant"`
- `content`: array（元素为 `{type:"thinking"| "text", thinking?/text?, signature?}`）
- `model`: string
- `stop_reason`: null | string
- `stop_sequence`: null | string
- `usage`: object（同 stream_event.message_start 里的结构）
- `service_tier`: string
- `context_management`: null | object（实测 null）

#### `assistant.message.content[*].type="tool_use"`（实测）

当模型决定调用工具时，会在 assistant 的 content 数组里产生工具调用块：

- `type`: `"tool_use"`
- `id`: string（tool_use_id，用于和 tool_result 关联）
- `name`: string（例如 `"Glob"` / `"Bash"` / `"Read"`）
- `input`: object（工具输入参数）

示例（实测）：

```jsonc
{"type":"tool_use","id":"call_function_xxx_1","name":"Bash","input":{"command":"cat sample2.txt | head -n 2 | tail -n 1","description":"Read line 2 from sample2.txt"}}
```

#### `type="user"` + `message.content[*].type="tool_result"`（实测）

工具返回值会以 **顶层 `type="user"`** 的对象出现（role 仍为 user），其 content 中包含 tool_result：

- `type`: `"tool_result"`
- `tool_use_id`: string（对应 tool_use.id）
- `content`: string（工具输出；可能是路径、stdout 文本、或错误文本）
- `is_error`: boolean（可选；实测在错误时出现 `true`，成功时可能省略或为 false）

示例（实测：Glob 返回文件路径）：

```jsonc
{"role":"user","content":[{"tool_use_id":"call_function_xxx_1","type":"tool_result","content":"/abs/path/to/sample2.txt"}]}
```

示例（实测：工具不可用）：

```jsonc
{"role":"user","content":[{"tool_use_id":"call_function_xxx_1","type":"tool_result","content":"<tool_use_error>Error: No such tool available: Read</tool_use_error>","is_error":true}]}
```

重要：在 `--output-format stream-json` 下，**tool_use/tool_result 不会作为 `stream_event` 出现**（至少在本机 2.1.29 的样例中如此）。它们体现在：
- `assistant.message.content[]` 里的 `tool_use`
- `type="user"` 的 `message.content[]` 里的 `tool_result`

#### `--disallowedTools` 的真实效果（实测）

以 `--disallowedTools "Read"` 为例：
- `system.init.tools` 中 **不会包含 `Read`**
- 若模型仍尝试调用 `Read`，会得到 `tool_result.is_error=true`，`content` 为 `No such tool available: Read`
- 但如果 `Bash` 仍可用，模型可能通过 `Bash(cat/sed/...)` 读取文件内容（因此想“禁止读取文件”不能只禁用 `Read`，还必须限制 `Bash` 的读/网络能力，或用权限规则/PreToolUse hook 强制约束）

### 4) CLI 参数校验错误（本机实测）

- 非法 `--output-format` 会直接在本地报错并退出（不会发起模型请求）：

```bash
claude -p --output-format nope "hi"
# error: option '--output-format <format>' argument 'nope' is invalid. Allowed choices are text, json, stream-json.
```

- `--print` + `--output-format stream-json` 未加 `--verbose` 会报错（本地校验）：

```bash
claude -p --output-format stream-json "hi"
# Error: When using --print, --output-format=stream-json requires --verbose
```

### 5) `--json-schema`（已实测）

用途：在 `--output-format json` 下要求模型输出满足 JSON Schema 的结构化对象。

#### 已实测（Claude Code 2.1.29）

当 `--json-schema` 校验通过时：
- 顶层会额外出现字段 `structured_output`（object），其内容满足你传入的 JSON Schema
- 同时 `result` 字段里仍可能包含一段可读的 JSON 代码块（markdown fence），但**程序应优先消费 `structured_output`**

实测样例文件：
- `tmp/claude-cli-lab/41_jsonschema_success.raw`（schema 要求 `line2: string`）
- `tmp/claude-cli-lab/42_jsonschema_fail.raw`（schema 要求 `line2: number`；注意这并不是“失败样例”，而是返回了数字并通过校验）

样例（节选，字段真实存在）：

```jsonc
{
  "type": "result",
  "result": "```json\\n{\\\"line2\\\": \\\"line2: UNIQUE_ABC_987654\\\"}\\n```",
  "structured_output": {
    "line2": "line2: UNIQUE_ABC_987654"
  }
}
```

#### “如何构造失败样例”（说明）

如果 schema 本身合法，模型**总能**输出一个满足 schema 的对象（哪怕语义不对），因此“失败样例”更可靠的做法是：
- 传入**非法 JSON** 的 `--json-schema` 参数（触发 CLI 解析错误），或
- 在 schema 中加入难以满足的约束并用 prompt 强制违反（不保证稳定）

参考：`https://code.claude.com/docs/zh-CN/headless`（“获取结构化输出”小节）

## CLI：已验证的可复现实验（建议作为集成回归用例）

> 实验目录：本仓库 `tmp/claude-cli-lab/`（隔离，不污染项目代码）

### 0) 版本确认

```bash
claude -v
# => 2.1.29 (Claude Code)
```

### 0.1) `claude doctor` 在无 TTY 环境会报 Raw mode 错误

**已验证**：在 stdin 不是终端的环境中运行 `claude doctor` 会报错（Ink raw mode）：
`ERROR Raw mode is not supported on the current process.stdin ...`

这再次佐证：若要在 CI/子进程管道中稳定运行，需要考虑 **PTY** 或确保有真实 TTY。

### 1) 纯文本输出（`-p`）在无 TTY 下会卡住；用 pseudo-tty 可稳定运行

```bash
# 可能卡住（stdin/stdout 为 pipe 的环境里）
timeout 60s claude -p "只回复 pong"

# 推荐：提供 pseudo-tty（稳定）
script -q -c 'claude -p "只回复 pong"' /dev/null
```

### 2) JSON 输出（`--output-format json`）

**实测输出是“第一行 JSON + 若干终端控制残留”**，程序解析时建议只取第一行。

```bash
script -q -c 'claude -p --output-format json "只回复 pong"' /dev/null
```

JSON 示例（第一行，已脱敏/截断展示字段结构）：

```jsonc
{
  "type": "result",
  "subtype": "success",
  "is_error": false,
  "result": "pong",
  "session_id": "64009275-d038-4f90-a735-744bcc787312",
  "usage": { "...": "..." },
  "modelUsage": { "...": "..." },
  "permission_denials": []
}
```

### 3) 会话恢复：`--resume` 与 `--continue`

**已验证**：
- `--resume <session_id>` 会在同一会话上继续（返回的 `session_id` 不变）
- `-c/--continue` 会继续“当前目录最近的对话”（同样复用上一次的 `session_id`）

```bash
# 先拿到一次 session_id（见上面 JSON 输出）

# resume：继续指定会话
script -q -c 'claude -p --output-format json --resume <session_id> "我们刚才的回复是什么？只回复一个词"' /dev/null

# continue：继续当前目录最近会话
script -q -c 'claude -c -p --output-format json "只回复 yes"' /dev/null
```

### 4) 流式 JSON（`--output-format stream-json`）

**已验证要点**：
- `--print` + `--output-format=stream-json` **必须**加 `--verbose`
- 输出会包含 `type=system` 初始化事件、`type=stream_event` 的增量事件、以及最终 `type=result`

```bash
script -q -c 'claude -p --verbose --output-format stream-json --include-partial-messages "写出 1 到 5，每个一行"' /dev/null
```

## 关于“工具 / 子代理 / 后台任务”的正确表述（避免混淆）

- `--agents` / `--agent`：**CLI 参数**，用于为当前会话动态定义或选择 subagent（参考 CLI 参考）。
- `Task/TaskOutput/TaskStop`：这是 **Claude Code 内置工具名**，会出现在 `stream-json` 的 `system.init.tools` 列表里，但它们**不是**你能在 shell 里直接当命令执行的东西。
- 后台任务：官方交互模式文档中主要通过 **交互命令 `/tasks`** 与快捷键实现（参考交互模式文档）。

参考：
- CLI 参考: `https://code.claude.com/docs/zh-CN/cli-reference`
- 交互模式: `https://code.claude.com/docs/zh-CN/interactive-mode`
