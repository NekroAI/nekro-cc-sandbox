# Nekro CC Sandbox - 架构与设计

> **基于 Claude Code 的持久化 Workspace Agent 沙盒**

---

## 核心理念

### 项目定位

为 Claude Code 提供持久化工作区的服务化封装，作为独立的深度能力层供外部机器人调用。

### 安全哲学

> **既然已经在容器中运行，就不需要过度的权限管理。大不了重建容器。**

- 容器 = 天然隔离边界（网络/文件/进程）
- AI 在容器内全权操作（无需权限询问）
- 专注**结果验收**而非**过程控制**
- 出问题 = 销毁重建（<1分钟）

**移除的复杂度：**
- ❌ Hooks（PreToolUse/PermissionRequest）
- ❌ 工具黑白名单（--tools/--disallowedTools）
- ❌ 权限询问（allow/ask/deny）

**简化的安全模型：**
```
容器隔离（唯一安全边界）
  ↓
AI 全权操作（--dangerously-skip-permissions）
  ↓
结果验收（测试/扫描/审核）
```

---

## 1. 架构设计

### 1.1 角色划分

| 角色 | 职责 | 说明 |
|------|------|------|
| 外部机器人 | 任务委托、结果融合 | 与用户交互，决定何时委托沙盒 |
| **Claude Code** | 任务执行 | Workspace Agent，自主决策和协调 |
| FastAPI Sandbox | 容器管理、结果验收 | 不参与任务决策 |

**外部系统只与一个 Agent 对话：Claude Code**

### 1.2 数据流

```
外部请求
    ↓
FastAPI (/api/v1/message)
    ↓
ClaudeRuntime
    ├─ PTY Wrapper (script -q -c ...)
    ├─ --dangerously-skip-permissions
    └─ --output-format stream-json
    ↓
WorkspaceManager (持久化 session_id)
    ↓
[可选] 结果验收
    ↓
返回给外部系统
```

### 1.3 职责矩阵

| 能力 | Sandbox | Claude Code |
|------|---------|-------------|
| 任务理解/拆解 | ❌ | ✅ 自主决策 |
| 工具/命令执行 | ❌ | ✅ 容器内全权 |
| Session 持久化 | ✅ | ❌ |
| Workspace 隔离 | ✅ | ❌ |
| 结果验收 | ✅ | ❌ |
| 容器生命周期 | ✅ | ❌ |

---

## 2. 容器隔离策略

### 2.1 网络隔离

- 自定义 DNS 服务器（域名白名单）
- 仅允许访问：GitHub/PyPI/NPM/Anthropic API
- 其他域名返回 NXDOMAIN

### 2.2 文件系统隔离

```yaml
volumes:
  - ./workspaces/${WORKSPACE_ID}:/workspace:rw
tmpfs:
  - /tmp:size=1G
read_only: true  # 根文件系统只读
```

**关键点：**
- AI 只能操作 `/workspace`
- 宿主机文件系统完全隔离
- 容器销毁 = 所有副作用消失

### 2.3 资源限制

```yaml
deploy:
  resources:
    limits:
      cpus: '2'
      memory: 4G
      pids: 100
```

**超时保护：** 10 分钟强制终止

### 2.4 风险缓解

| 风险 | 缓解措施 |
|------|---------|
| AI 删除重要文件 | 工作区定期快照 + 可恢复 |
| AI 执行危险命令 | 容器资源限制 + 超时终止 |
| AI 访问恶意网站 | DNS 白名单 + 网络隔离 |
| AI 生成错误代码 | 结果验收（测试/lint/审核） |
| AI 消耗大量资源 | CPU/内存限制 + 进程数限制 |

**核心思想：** 所有风险限制在容器内，最坏情况 = 重建容器（<1分钟）

---

## 3. 结果验收机制

### 3.1 设计原则

> **与其在执行过程中限制 AI，不如在结果层面验收质量。**

**传统方式（过度复杂）：**
```
AI 操作 → 询问权限 → 批准 → 执行 → 重复...
```

**简化方式（结果导向）：**
```
AI 全权执行 → 验收结果 → 接受/拒绝/重试
```

### 3.2 三层验收

#### 第一层：静态验收（无需执行）

```python
class StaticValidator:
    def validate(self, code: str) -> ValidationResult:
        # 语法检查
        if not syntax_valid(code):
            return reject("语法错误")
        
        # 安全扫描
        dangerous = ["eval(", "exec(", "os.system(", "__import__"]
        if any(p in code for p in dangerous):
            return reject("包含危险模式")
        
        # 代码风格
        if not style_compliant(code):
            return warn("风格不符合规范")
        
        return accept()
```

#### 第二层：动态验收（容器内测试）

```python
async def dynamic_validate(workspace_id: str) -> ValidationResult:
    # 在同一容器内运行测试
    result = await run_in_sandbox(
        workspace_id=workspace_id,
        command="pytest tests/ --tb=short",
        timeout=60
    )
    
    if result.exit_code != 0:
        return reject(f"测试失败: {result.stderr}")
    
    if result.duration > 10:
        return warn("执行时间过长")
    
    return accept()
```

#### 第三层：人工审核（高风险操作，可选）

```python
def needs_approval(result: dict) -> bool:
    high_risk_actions = [
        "deleted_files",      # 删除了文件
        "modified_config",    # 修改了配置
        "external_requests"   # 发起了外部请求
    ]
    return any(action in result.get("actions", []) for action in high_risk_actions)
```

### 3.3 失败处理策略

```python
# 选项 1：重试（给 AI 反馈，让它修复）
await runtime.send_message(
    workspace_id,
    f"上次尝试失败：{error}。请修复问题后重试。"
)

# 选项 2：回滚快照（恢复到执行前）
await workspace_manager.restore_snapshot(
    workspace_id=workspace_id,
    snapshot_id="before_task"
)

# 选项 3：销毁重建（最简单粗暴）
await destroy_workspace(workspace_id)
await create_fresh_workspace(workspace_id)
```

### 3.4 优势对比

| 方案 | 过程控制（复杂） | 结果验收（简单） |
|------|----------------|----------------|
| AI 自由度 | 受限（每步询问） | 完全自由 |
| 执行效率 | 慢（等待批准） | 快（无阻塞） |
| 实现复杂度 | 高（hooks/权限系统） | 低（容器 + 验证器） |
| 安全性 | 细粒度但繁琐 | 粗粒度但有效 |
| 可维护性 | 难（规则复杂） | 易（容器重建） |

---

## 4. Session 管理与会话持久化

### 4.1 Session 生命周期

```python
# 1. 启动时加载已有 session_id
session = await runtime.start(workspace_id)

# 2. 仅在"成功结果"时持久化
if not is_error and new_session_id:
    await workspace_manager.update_session(workspace_id, new_session_id)

# 3. 自动降级重试（处理"No conversation found"）
if "No conversation found" in cli_errors:
    # 清空 session_id，不带 --resume 重试
    await workspace_manager.update_session(workspace_id, "")
```

### 4.2 多阶段任务交互

**核心认知：** Claude Code 的 `--print` 模式是**非交互的、一次性执行**。

**错误理解：**
- ❌ Claude 可以在执行中暂停等待用户输入
- ❌ Hooks 可以实现"用户确认"业务逻辑
- ❌ 一次调用可以多次往返交互

**正确理解：**
- ✅ `claude -p` 是一次性执行，完成后退出
- ✅ 通过多次调用 + `--resume` 实现多阶段
- ✅ 通过 workspace 文件系统传递中间结果

### 4.3 实现方式

**架构：**

```
阶段 1：分析但不执行（一次完整的 claude -p 调用）
  ↓ 返回 session_id + 分析结果（如 analysis.json）
  
机器人解析结果 → 询问用户 → 获取确认
  ↓ 用户确认"执行删除"
  
阶段 2：执行操作（新的 claude -p --resume session_id 调用）
```

**代码示例：**

```python
# ===== 阶段 1：分析 =====
task1_prompt = """
任务：分析项目中的冗余代码

约束：
1. 不要直接删除任何代码
2. 将发现的问题保存到 analysis.json
3. 格式要求：
{
  "findings": [
    {"file": "utils.py", "function": "unused_helper", "reason": "未被调用"}
  ],
  "safe_to_delete": true/false,
  "risk_assessment": "low/medium/high"
}
"""

# 执行分析
result1 = await runtime.send_message_in_workspace(workspace_id, task1_prompt)
session_id = result1["session_id"]  # 保存 session_id

# ===== 中间：用户确认 =====
# 机器人读取分析结果
analysis_content = await read_workspace_file(workspace_id, "analysis.json")
analysis = json.loads(analysis_content)

# 展示给用户并询问
user_response = await bot.ask_user(f"""
发现 {len(analysis["findings"])} 个未使用的函数：
{format_findings(analysis["findings"])}

风险评估：{analysis["risk_assessment"]}

是否删除这些冗余代码？
""")

# ===== 阶段 2：执行 =====
if user_response == "confirm":
    task2_prompt = """
用户已确认删除操作。

请根据 analysis.json 中的建议执行以下操作：
1. 删除标记为"未使用"的函数
2. 运行测试确保没有破坏功能
3. 报告执行结果
"""
    
    # 关键：使用相同 workspace + 继续 session
    result2 = await runtime.send_message_in_workspace(
        workspace_id=workspace_id,
        message=task2_prompt,
        resume_session_id=session_id  # 继续之前的上下文
    )
    
    # result2 中 Claude "记得"它刚才做的分析
```

**关键机制：**

1. **Session 连续性**：通过 `--resume session_id` 让 Claude "记得"之前的工作
2. **Workspace 文件**：`analysis.json` 既是结果，也是下阶段的输入
3. **Prompt 约束**：明确指示每个阶段该做什么、不该做什么

**为什么这样设计有效：**
- Claude 通过 session 记忆知道"我刚才分析过这个项目"
- Claude 信任自己写的 `analysis.json`
- 用户确认环节在"机器人层"完成，而非 Claude 内部

---

## 5. 作为独立 Agent 沙盒的扩展设计

### 5.1 应用场景

外部机器人（直接与用户交互）将"深度能力"任务委托给 CC 沙盒：

```
用户 ←→ 机器人（对话理解、意图识别）
          ↓ 委托深度任务
     CC 沙盒（代码操作、文件处理、复杂推理）
          ↓ 返回结构化结果
      机器人（融合结果、保持对话连贯性）
          ↓
       用户
```

### 5.2 核心挑战

#### 挑战 1：异步协作（不阻塞主交互）

**问题：** CC 任务可能耗时很长（几分钟到十几分钟），机器人不能阻塞等待。

**解决方案：** 任务异步化 + 事件驱动通知

```
机器人 → POST /tasks（立即返回 task_id）
       ↓
机器人告知用户："正在分析，预计3分钟，稍后通知你"
       ↓
沙盒后台执行 → 通过 WebHook/SSE 推送进度
       ↓
任务完成 → 机器人主动通知用户
```

#### 挑战 2：文件资源传输

**问题：** 用户上传的文件、沙盒生成的产物如何高效传递？

**解决方案：** 文件生命周期管理

```
上传：POST /workspaces/{id}/files（multipart）
处理：沙盒内 CC 直接访问工作区文件
下载：GET /workspaces/{id}/files/{path}
批量：POST /workspaces/{id}/files/archive（zip打包）
清理：自动过期 + 手动删除
```

#### 挑战 3：上下文传递（保持连贯性）

**问题：** 沙盒需要知道"用户是谁、对话历史、当前意图"才能给出合理结果。

**解决方案：** 结构化上下文注入

```json
{
  "task": "分析这个 Python 项目的性能瓶颈",
  "context": {
    "user_id": "user_123",
    "conversation_summary": "用户报告网站响应慢，怀疑数据库查询问题",
    "previous_findings": ["已排查网络延迟", "CPU 使用率正常"],
    "user_expertise": "初级开发者（需要详细解释）"
  },
  "files": ["app.py", "database.py"],
  "constraints": {
    "max_time_minutes": 5,
    "output_format": "markdown_report"
  }
}
```

#### 挑战 4：统一智能体体验

**问题：** 用户不应该感觉到"两个系统"的存在。

**解决方案：** 透明代理模式

**机器人职责：**
1. **智能路由**：判断哪些任务需要委托沙盒
2. **任务翻译**：将自然语言转换为结构化任务
3. **结果融合**：将技术报告融入自然对话
4. **进度转述**：将技术事件转换为用户友好描述

**示例：**

```python
# 用户输入
user: "这个项目跑起来好慢，能帮我看看吗？"

# 机器人翻译为结构化任务
task = {
    "type": "performance_analysis",
    "description": "分析项目性能瓶颈并给出优化建议",
    "context": {
        "user_complaint": "运行缓慢",
        "project_type": "web application",
        "expertise_level": "beginner"
    },
    "expected_output": {
        "format": "markdown_report",
        "sections": ["问题诊断", "优化建议", "预期提升"],
        "include_code_examples": true
    }
}

# 沙盒返回（结构化）
sandbox_result = {
    "findings": [
        {"issue": "N+1 查询", "severity": "high", "file": "views.py:45"}
    ],
    "estimated_improvement": "响应时间减少 60%"
}

# 机器人融合为自然回复
bot_response = """
我帮你分析了项目，发现了主要问题：

**核心问题**：数据库查询存在 N+1 问题（在 views.py 第 45 行）

这会导致每次请求触发大量重复查询。我已经生成了优化版本的代码，
预计可以让响应速度提升 60%。

需要我帮你应用这些优化吗？
"""
```

### 5.3 API 设计扩展

#### 任务管理 API

```http
# 创建异步任务
POST /api/v1/tasks
{
  "workspace_id": "bot_user_123",
  "task": "分析项目性能瓶颈并给出优化建议",
  "context": {
    "user_conversation": "...",
    "project_type": "Django web app"
  },
  "files": ["uploaded_file_1.py"],
  "callback_url": "https://bot.example.com/webhook/task_completed",
  "max_duration_minutes": 10
}

响应：
{
  "task_id": "task_abc123",
  "status": "pending",
  "estimated_duration_seconds": 120,
  "workspace_id": "bot_user_123"
}

# 查询任务状态
GET /api/v1/tasks/{task_id}

响应：
{
  "task_id": "task_abc123",
  "status": "running",  # pending/running/completed/failed/cancelled
  "progress": {
    "current_step": "正在分析数据库查询模式",
    "completed_percentage": 45
  },
  "created_at": "2026-02-05T10:30:00Z",
  "started_at": "2026-02-05T10:30:02Z",
  "estimated_completion_at": "2026-02-05T10:32:00Z"
}

# 实时事件流（SSE）
GET /api/v1/tasks/{task_id}/events

事件流示例：
data: {"type": "progress", "step": "读取文件", "percentage": 10}
data: {"type": "progress", "step": "分析依赖", "percentage": 30}
data: {"type": "tool_use", "tool": "Bash", "command": "pytest --profile"}
data: {"type": "thinking", "content": "发现 N+1 查询问题..."}
data: {"type": "completed", "result_id": "result_xyz789"}

# 取消任务
POST /api/v1/tasks/{task_id}/cancel

# 获取任务结果
GET /api/v1/tasks/{task_id}/result

响应：
{
  "task_id": "task_abc123",
  "status": "completed",
  "result": {
    "summary": "发现 3 个主要性能瓶颈",
    "findings": [...],
    "generated_files": ["performance_report.md", "optimized_views.py"]
  },
  "execution_log": "...",
  "duration_seconds": 45
}
```

#### 文件管理 API

```http
# 上传文件到工作区
POST /api/v1/workspaces/{workspace_id}/files
Content-Type: multipart/form-data

参数：
files: [file1.py, file2.py]
path: "uploaded/"  # 可选：目标子目录

响应：
{
  "uploaded_files": [
    {
      "name": "file1.py",
      "path": "/workspaces/bot_user_123/uploaded/file1.py",
      "size": 1024,
      "checksum": "sha256:abc123..."
    }
  ]
}

# 列出工作区文件
GET /api/v1/workspaces/{workspace_id}/files?path=/&recursive=true

响应：
{
  "files": [
    {
      "name": "app.py",
      "path": "/workspaces/bot_user_123/app.py",
      "size": 2048,
      "modified_at": "2026-02-05T10:30:00Z",
      "type": "file"
    }
  ]
}

# 下载单个文件
GET /api/v1/workspaces/{workspace_id}/files/path/to/file.py

# 批量下载（打包为 zip）
POST /api/v1/workspaces/{workspace_id}/files/archive
{
  "files": ["report.md", "code/optimized.py"],
  "format": "zip"
}

响应：
Content-Type: application/zip
Content-Disposition: attachment; filename="workspace_files.zip"

# 删除文件
DELETE /api/v1/workspaces/{workspace_id}/files/path/to/file.py
```

#### 能力发现 API

```http
# 获取沙盒能力清单
GET /api/v1/capabilities

响应：
{
  "version": "0.1.0",
  "tools": [
    {
      "name": "code_analysis",
      "description": "分析代码质量、性能瓶颈、安全漏洞",
      "supported_languages": ["python", "javascript", "java"],
      "estimated_time": "30s-5min"
    },
    {
      "name": "code_generation",
      "description": "根据需求生成代码（函数/类/模块）",
      "supported_languages": ["python", "javascript"],
      "estimated_time": "10s-2min"
    }
  ],
  "constraints": {
    "max_file_size_mb": 100,
    "max_workspace_size_gb": 1,
    "max_concurrent_tasks": 5
  }
}

# 评估任务可行性
POST /api/v1/capabilities/evaluate
{
  "task_description": "分析一个 50 万行的 Python 项目",
  "files": [{"name": "large_project.zip", "size_mb": 200}]
}

响应：
{
  "feasible": false,
  "reason": "文件大小超过限制（200MB > 100MB）",
  "suggestions": [
    "考虑分批上传",
    "先上传核心模块进行分析"
  ]
}
```

### 5.4 三种交互模式

#### 模式 1：同步简单任务（当前已支持）

**适用场景：** 耗时短（<30s）、无需中间反馈

```
机器人识别意图 → POST /api/v1/message（同步等待）
                → 沙盒执行（CC 分析代码）
                → 返回结果（Markdown 报告）
                → 机器人格式化后回复用户
```

**优点：** 简单、实时、无需轮询  
**缺点：** 长任务会超时

#### 模式 2：异步任务 + 轮询（推荐）

**适用场景：** 耗时长（>30s）、可预测完成时间

```
机器人 → POST /tasks（立即返回 task_id）
       ↓
机器人回复用户："收到！正在分析项目，预计需要 3 分钟，我会主动通知你。"
       ↓
机器人启动后台轮询：每 10 秒查询 GET /tasks/{task_id}
       ↓
任务完成 → 机器人拉取结果 → 主动通知用户
```

#### 模式 3：事件流 + WebHook（最优体验）

**适用场景：** 需要实时进度反馈

```
机器人 → POST /tasks（带 callback_url）
       ↓
机器人订阅 SSE：GET /tasks/{task_id}/events
       ↓
沙盒执行并推送事件：
  - progress: "正在读取文件..."
  - tool_use: "执行 pytest 测试..."
  - thinking: "发现潜在问题..."
       ↓
机器人实时转述给用户（可选，避免信息过载）
       ↓
任务完成 → 沙盒调用 WebHook → 机器人获得完整结果
```

### 5.5 资源配额管理

#### 工作区绑定策略

**方案 1：一个用户 = 一个持久工作区**
- 优点：上下文连续、文件持久化
- 缺点：需要定期清理、占用存储

**方案 2：一个任务 = 一个临时工作区**
- 优点：隔离性强、自动清理
- 缺点：无法利用历史上下文

**推荐：混合策略**
- 简单任务：临时工作区（用完即删）
- 持续协作：持久工作区（定期归档）

#### 配额限制

```yaml
per_user:
  max_concurrent_tasks: 3
  max_workspace_size_mb: 500
  max_task_duration_minutes: 30

per_workspace:
  max_files: 1000
  auto_cleanup_after_days: 7

global:
  max_concurrent_workspaces: 100
  rate_limit_requests_per_minute: 60
```

### 5.6 安全与审计

#### 沙盒隔离
- 每个工作区运行在独立目录
- 禁止访问其他工作区文件
- 限制网络访问（仅允许特定域名）
- 禁用危险命令（通过容器配置，而非 hooks）

#### 审计日志

```json
{
  "event": "task_created",
  "timestamp": "2026-02-05T10:30:00Z",
  "user_id": "bot_user_123",
  "task_id": "task_abc123",
  "task_description": "分析项目性能",
  "files_accessed": ["app.py", "database.py"],
  "tools_used": ["Bash", "Read", "Grep"],
  "outcome": "completed",
  "execution_time_seconds": 45
}
```

---

## 6. 技术实现细节

### 6.1 Claude Code 启动配置（简化）

```bash
# 核心启动命令
claude -p \
  --dangerously-skip-permissions \  # 跳过所有权限询问
  --verbose \
  --output-format stream-json \
  --include-partial-messages \
  -- "{prompt}"

# 不需要的配置：
# - --tools / --disallowedTools（工具白名单/黑名单）
# - .claude/settings.json 中的 hooks 配置
# - .claude/settings.json 中的 permissions 规则
```

**为什么可以这样做：**
1. 容器已提供物理隔离
2. AI 最多破坏容器内的文件（可重建）
3. 结果验收会在外层拦截错误输出
4. 开发效率优先，减少等待时间

### 6.2 PTY Wrapper（解决卡死问题）

**问题：** `claude -p` 在无 TTY 环境（stdin/stdout 为 pipe）可能卡住无输出

**已验证现象：**
```bash
# ❌ 直接管道模式会卡住
claude -p "ping"  # 无输出，长期挂起

# ✅ PTY 包装稳定可用
script -q -c 'claude -p "ping"' /dev/null  # 正常返回
```

**实现：**

```python
def _build_pseudotty_wrapper_cmd(self, claude_cmd: list[str]) -> list[str]:
    """用 pseudo-tty 包装 claude 命令，避免管道模式下卡住"""
    shell_cmd = shlex.join(claude_cmd)
    return ["script", "-q", "-c", shell_cmd, "/dev/null"]
```

### 6.3 Stream-JSON 解析协议

**事件类型：**

| 事件类型 | 用途 | 提取字段 |
|---------|------|---------|
| `stream_event.content_block_delta` | 增量文本 | `delta.text` → yield |
| `system.init` | 工具列表 | `tools[]` → 缓存 |
| `assistant.message` | Message 快照 | `content[].text` → 兜底 |
| `result.result` | 最终文本 | `result` → 最终兜底 |
| `result.errors[]` | CLI 错误 | 识别特定错误自动重试 |

**实现：**

```python
async def _iter_stream_json_objects(self, stdout):
    while True:
        line = await stdout.readline()
        if not line:
            break
        
        # 清洗 ANSI 控制序列
        line = self._strip_ansi(line.decode("utf-8"))
        
        # 解析 JSON
        try:
            obj = json.loads(line.strip())
            
            if obj["type"] == "stream_event":
                if obj["event"]["type"] == "content_block_delta":
                    text = obj["event"]["delta"].get("text", "")
                    if text:
                        yield text
        except json.JSONDecodeError:
            continue
```

**智能兜底机制：**

```python
# 优先级：增量 delta > final_result > assistant_snapshot
if not yielded_any_text and final_result_text:
    yield final_result_text
elif not yielded_any_text and last_assistant_text:
    yield last_assistant_text
```

### 6.4 错误处理协议

**统一错误结构：**

```python
{
  "success": false,
  "error": {
    "err_id": "a3b4c5d6e7",      # 短追踪 ID（日志检索）
    "code": "CLAUDE_CLI_ERROR",   # 稳定错误码
    "message": "...",             # 用户友好描述
    "retryable": true,            # 是否可重试
    "details": {...}              # 调试信息
  }
}
```

**错误码枚举：**

```python
class ErrorCode(StrEnum):
    RUNTIME_UNAVAILABLE = "RUNTIME_UNAVAILABLE"
    WORKSPACE_NOT_FOUND = "WORKSPACE_NOT_FOUND"
    CLAUDE_CLI_ERROR_RESULT = "CLAUDE_CLI_ERROR_RESULT"
    CLAUDE_CLI_NO_PARSEABLE_OUTPUT = "CLAUDE_CLI_NO_PARSEABLE_OUTPUT"
    SHELL_SESSION_NOT_FOUND = "SHELL_SESSION_NOT_FOUND"
    INTERNAL_ERROR = "INTERNAL_ERROR"
```

---

## 7. 目录结构

```
nekro-cc-sandbox/
├── src/nekro_cc_sandbox/
│   ├── main.py              # FastAPI 入口
│   ├── api/                 # API 路由
│   │   ├── messages.py      # 消息 API
│   │   ├── status.py        # 状态查询
│   │   ├── shells.py        # Shell 面板
│   │   └── schemas.py       # 数据模型
│   ├── claude/
│   │   ├── runtime.py       # Claude Code 托管
│   │   └── policy.py        # 运行时策略
│   ├── workspace/
│   │   ├── manager.py       # 工作区管理
│   │   └── state.py         # 状态持久化
│   ├── shell/
│   │   └── manager.py       # PTY Shell 管理
│   ├── settings.py          # 配置管理
│   └── errors.py            # 错误类型
├── workspaces/              # 工作区数据
│   └── default/
│       └── .workspace_state.json
├── frontend/                # Web UI
│   ├── src/
│   │   ├── App.tsx
│   │   ├── api/client.ts
│   │   └── components/
│   └── dist/
├── tests/                   # 测试
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   └── providers/
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

---

## 8. 实现优先级

### Phase 1：基础功能（MVP）

- [x] 基础消息 API（`/api/v1/message`）
- [x] Session 持久化（`--resume`）
- [x] PTY Wrapper（解决卡死）
- [x] Stream-JSON 解析
- [x] Shell 面板（PTY + WebSocket）
- [ ] 任务异步化（`/api/v1/tasks`）
- [ ] 容器配置（docker-compose 完善）

### Phase 2：增强体验

- [ ] SSE 事件流（`/tasks/{id}/events`）
- [ ] WebHook 回调（任务完成通知）
- [ ] 文件批量管理（上传/下载/zip）
- [ ] 上下文管理 API
- [ ] 结果验收机制

### Phase 3：高级功能

- [ ] 工作区快照/恢复
- [ ] 能力评估 API
- [ ] 任务链/依赖（Pipeline）
- [ ] 性能监控
- [ ] 审计日志

---

## 9. 容器安全配置示例

```yaml
# docker-compose.yml
version: '3.8'

services:
  sandbox:
    image: nekro-cc-sandbox:latest
    container_name: sandbox_${WORKSPACE_ID}
    
    # 网络隔离
    networks:
      - sandbox_internal
    dns: 10.0.0.53  # 自定义 DNS（域名白名单）
    
    # 文件系统隔离
    volumes:
      - ./workspaces/${WORKSPACE_ID}:/workspace:rw
    tmpfs:
      - /tmp:size=1G
    read_only: true  # 根文件系统只读
    
    # 资源限制
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
          pids: 100
    
    # 安全选项
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    cap_add:
      - CHOWN
      - SETGID
      - SETUID
    
    # 超时
    stop_grace_period: 10s
    
    environment:
      - WORKSPACE_ROOT=/workspace
      - CLAUDE_SKIP_PERMISSIONS=1

networks:
  sandbox_internal:
    internal: true  # 无互联网访问
```

---

## 10. 总结

### 核心定位

> **nekro-cc-sandbox 是外部智能体的"深度能力层"，通过简化的容器隔离 + 结果验收模型，安全高效地提供 Claude Code 能力。**

### 设计哲学

| 原则 | 说明 |
|------|------|
| **简单 > 复杂** | 容器隔离是唯一安全边界 |
| **务实 > 理论** | 不需要 hooks 和细粒度权限管理 |
| **快速迭代 > 谨慎** | 出问题就重建容器（<1分钟） |

### 关键技术决策

| 决策 | 理由 |
|------|------|
| **容器隔离** | 天然安全边界，无需额外权限管理 |
| **结果验收** | 比过程控制更简单有效 |
| **--dangerously-skip-permissions** | 容器已提供隔离，无需 CC 层权限询问 |
| **PTY Wrapper** | 解决无 TTY 环境卡住问题 |
| **Session 持久化** | 实现多轮对话和多阶段任务 |
| **异步任务** | 支持长时间运行的任务 |

### 与传统方案对比

| 传统方案 | 本项目 |
|---------|--------|
| 细粒度权限控制 | 容器隔离（粗粒度但有效） |
| Hooks + 询问 | 结果验收（事后检查） |
| 过程控制 | 结果导向 |
| 复杂难维护 | 简单可重建 |

**核心观点：** 我们已经有容器了，为什么还要在容器里再做一层权限管理？大不了重建容器。

---

**文档版本：** 2.0  
**最后更新：** 2026-02-05  
**核心理念：** 容器隔离 + 结果验收 > 细粒度过程控制
