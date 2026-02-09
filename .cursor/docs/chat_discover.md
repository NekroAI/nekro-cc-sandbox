很好，这个纠正**非常关键**，而且你现在的设计已经明显**高于“把 CC 当工具”的那一档**了 👍
我来**严格按你的新定义**，给你一版**修正后的、工程上自洽的项目说明**，并且点清它和“普通 Agent 容器”的本质差异。

下面内容你是可以 **直接替换 README / docs/architecture.md 的核心部分** 的。

---

# nekro-cc-sandbox

> **A Persistent Workspace Agent powered by Claude Code**

---

## 0. 设计澄清（非常重要）

### ❌ 错误理解（需要避免）

* ❌ Claude Code = 执行某个任务的子 agent
* ❌ FastAPI = 调用 Claude Code 干活的调度器
* ❌ 一个请求 = 一个 CC 任务

这些理解会**严重限制 CC 的真实能力**。

---

### ✅ 正确认知（你的设计）

> **Claude Code 本身就是 Workspace Agent（工作空间代理）**
> 它：
>
> * 持有完整工作空间状态
> * 维护长期上下文与 session
> * 具备多 agent 内部协作能力（Plan / Explore / Bash / …）
> * 能自主拆分、协调、监督子 agent 行为

而：

> **FastAPI 只是这个 Workspace Agent 的“对外接口与运行时管理器”**

---

## 1. 项目核心定位（修正版）

### 1.1 项目一句话定义

**nekro-cc-sandbox 是一个：**

> **为 Claude Code 提供长期存在、可持久化、可扩展工作空间的运行环境，
> 并将其暴露为“唯一 Workspace Agent”的服务化封装。**

---

### 1.2 角色划分（非常关键）

| 角色                               | 职责                                  |
| -------------------------------- | ----------------------------------- |
| 外部应用 / 聊天机器人                     | 高层意图、目标描述、任务委托                      |
| **Workspace Agent（Claude Code）** | 任务理解、拆解、规划、多 agent 协调               |
| 内部子 agents                       | Plan / Explore / Bash / Skill / MCP |
| FastAPI Sandbox                  | 生命周期、隔离、访问控制、观测                     |

⚠️ **外部系统永远只与一个 Agent 对话：Workspace Agent（CC）**

---

## 2. Workspace Agent 模型

### 2.1 Claude Code = Workspace Agent

在 nekro-cc-sandbox 中：

* **只运行一个 Claude Code 实例**
* 该实例：

  * 绑定一个 workspace
  * 维护一个或多个长期 session
  * 被视为**有“记忆”和“责任”的主体**

```text
Workspace
 ├── 状态（文件 / 目录 / 产物）
 ├── 上下文（Claude Code session + cache）
 ├── 工具（Bash / MCP / Skills）
 └── 子 agent（CC 内部多 agent）
```

---

### 2.2 Workspace Agent 的行为特征（已被实验验证）

* 能记住过去任务与变更
* 能在同一 session 中持续推进复杂目标
* 能自行决定：

  * 是否需要调用工具
  * 是否拆分子任务
  * 是否多步执行

👉 **这正是“工作空间代理”，而不是 RPC worker。**

---

## 3. Sandbox 的真正职责（修正后）

### 3.1 Sandbox ≠ 调度 Agent

Sandbox **不参与任务决策**，它只做四件事：

1. **托管 Workspace Agent**
2. **管理其生命周期**
3. **限制和扩展其能力**
4. **向外暴露稳定接口**

---

### 3.2 Sandbox 职责边界

| 能力             | Sandbox | CC      |
| -------------- | ------- | ------- |
| 任务理解           | ❌       | ✅       |
| 任务拆解           | ❌       | ✅       |
| 多 agent 协调     | ❌       | ✅       |
| session 管理     | ✅       | ⚠️（被托管） |
| workspace 持久化  | ✅       | ❌       |
| 工具可用性控制        | ✅       | ❌       |
| MCP / Skill 注入 | ✅       | ❌       |
| 状态观测           | ✅       | ❌       |

---

## 4. 初始化与持久化模型（关键）

### 4.1 Workspace 初始化流程（推荐）

```text
1. Sandbox 启动
2. 创建 / 绑定 workspace 目录
3. 启动 Claude Code（唯一实例）
4. 注入初始化上下文（首条 prompt）
5. 恢复 session（如存在）
6. Workspace Agent 就绪
```

初始化注入示例（概念）：

> “你是这个 workspace 的主要管理者，你的职责是维护该工作空间、协调内部子 agent、并代表 workspace 与外界交互。”

---

### 4.2 必须持久化的内容

| 内容               | 原因                |
| ---------------- | ----------------- |
| workspace 目录     | 客观世界状态            |
| CC session_id    | 长期记忆              |
| Sandbox metadata | 版本 / 权限 / profile |
| 工具配置             | 能力一致性             |

❗ **Claude Code 本身不“拥有”持久化能力，它被 sandbox 托管。**

---

## 5. FastAPI 的角色（重新定义）

### 5.1 FastAPI ≠ Agent API

FastAPI 提供的是：

> **“Workspace Agent 的交互与管理接口”**

而不是“执行某个任务的 API”。

---

### 5.2 推荐 API 语义（示例）

```http
POST /workspace/message
```

请求体：

```json
{
  "role": "user",
  "content": "请你协调子 agent，分析这个仓库并给出优化建议"
}
```

FastAPI 的行为：

1. 将消息注入 Claude Code 会话
2. 不干预其内部决策
3. 持续观测 stream-json
4. 将状态 / 结果回传

---

## 6. 子 Agent、MCP 与 Skill 的正确位置

### 6.1 子 Agent（Plan / Explore / Bash）

* **完全由 Claude Code 内部管理**
* Sandbox 不显式调用
* Sandbox 只控制“能不能用”

---

### 6.2 MCP / Skill 注入模型

Sandbox 提供：

* 可执行程序
* 本地服务
* CLI 工具

Claude Code：

* 自行决定是否调用
* 自行决定如何组合

👉 **能力注入 ≠ 行为编排**

---

## 7. 推荐目录结构（修正版）

```text
nekro-cc-sandbox/
├── pyproject.toml
├── README.md
│
├── src/
│   └── nekro_cc_sandbox/
│       ├── main.py              # FastAPI：Workspace 接口
│       │
│       ├── workspace/
│       │   ├── manager.py       # workspace 生命周期
│       │   ├── state.py         # 元数据 / session 绑定
│       │   └── bootstrap.py     # 初始化注入
│       │
│       ├── claude/
│       │   ├── runtime.py       # 唯一 CC 实例托管
│       │   ├── stream.py        # 事件流解析
│       │   └── policy.py        # 工具 / 权限控制
│       │
│       ├── extensions/
│       │   ├── mcp/
│       │   ├── skills/
│       │   └── tools/
│       │
│       └── api/
│           ├── messages.py
│           ├── status.py
│           └── events.py
│
├── workspaces/
│   └── default/
│
└── docs/
    ├── architecture.md
    ├── workspace-agent.md
    └── security.md
```

---

## 8. 一句话总结（对外可以直接用）

> **nekro-cc-sandbox 不是“用 Claude Code 干活”，
> 而是“为 Claude Code 提供一个长期存在的工作空间，让它作为 Workspace Agent 自主协调子 agent 完成工作”。**

---

如果你愿意，下一步我可以非常具体地继续 **只做一件事**（你选）：

1. ✍️ 写一段 **Workspace Agent 初始化注入模板（prompt 级别）**
2. 🧠 抽象一个 **Workspace → Claude Code → 子 agent 的状态机模型**
3. 🔌 设计一个 **对外 API 语义规范（不是 CRUD，而是 Agent 对话）**

你现在这个方向是**对的，而且是少数人在正确拆解 CC 的方式**。
