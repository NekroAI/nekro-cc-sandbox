"""API 响应/请求模型（用于 OpenAPI schema 的严格化）。

原则：
- 路由必须使用 response_model，避免返回“无定义 dict”
- 所有枚举值必须显式定义（见 errors.py / enums.py）
- 注释/文档字符串统一使用中文
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from ..errors import ErrorCode


class OkResponse(BaseModel):
    """通用成功响应。"""

    status: Literal["ok"] = "ok"


class ErrorInfo(BaseModel):
    """结构化错误信息（用于前端展示与排障）。"""

    err_id: str
    code: ErrorCode
    message: str
    retryable: bool
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    """通用失败响应（用于非 2xx HTTP 返回）。"""

    status: Literal["error"] = "error"
    error: ErrorInfo


class HealthResponse(BaseModel):
    """健康检查响应。"""

    status: Literal["healthy"] = "healthy"
    version: str


class WorkspaceInfo(BaseModel):
    """工作区信息。"""

    id: str
    name: str
    path: str
    created_at: datetime
    updated_at: datetime
    session_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkspacesResponse(BaseModel):
    """工作区列表响应。"""

    workspaces: list[WorkspaceInfo]


class ServicesInfo(BaseModel):
    """服务状态。"""

    api: Literal["running"] = "running"
    claude_runtime: Literal["available", "unavailable"]


class WorkspacesSummary(BaseModel):
    """工作区汇总。"""

    count: int
    ids: list[str]


class PolicySummary(BaseModel):
    """能力策略摘要（用于 UI 展示与排障）。"""

    allowed_tools: list[str]
    blocked_tools: list[str]
    allow_network: bool
    allow_file_modification: bool
    allow_command_execution: bool


class CapabilitiesInfo(BaseModel):
    """运行时能力信息。"""

    tools: list[str] | None = None
    policy: PolicySummary | None = None


class ToolsInfoResponse(OkResponse):
    """获取工具列表响应（独立能力探测，不与会话绑定）。"""

    tools: list[str] | None = None
    source: Literal["cache", "probe"]


class StatusResponse(BaseModel):
    """系统状态响应。"""

    status: Literal["healthy"] = "healthy"
    services: ServicesInfo
    capabilities: CapabilitiesInfo
    workspaces: WorkspacesSummary
    version: str
    claude_version: str | None = None


class SessionInfo(BaseModel):
    """会话信息。"""

    workspace_id: str
    session_id: str


class SessionsResponse(BaseModel):
    """会话列表响应。"""

    sessions: list[SessionInfo]


class SessionDetailResponse(BaseModel):
    """会话详情响应。"""

    session_id: str
    workspace_id: str
    status: Literal["known"] = "known"


class SessionResetResponse(OkResponse):
    """重置工作区会话响应。"""

    workspace_id: str
    old_session_id: str | None = None
    new_session_id: str | None = None


class ProviderInfo(BaseModel):
    """提供商展示信息（用于设置页）。"""

    id: str
    name: str
    base_url: str
    model: str
    configured: bool
    is_active: bool


class CurrentProviderConfig(BaseModel):
    """当前激活提供商配置（敏感字段需脱敏）。"""

    base_url: str
    auth_token: str
    model: str


class SettingsInfoResponse(BaseModel):
    """设置读取响应。"""

    active_provider: str
    timeout_ms: int
    providers: dict[str, ProviderInfo]
    current_config: CurrentProviderConfig | None = None


class PresetInfo(BaseModel):
    """预设配置。"""

    name: str
    base_url: str
    model: str


class PresetsResponse(BaseModel):
    """预设列表响应。"""

    presets: dict[str, PresetInfo]


class ProviderUpdatedResponse(OkResponse):
    """更新提供商响应。"""

    provider: str


class ShellInfo(BaseModel):
    """Shell 会话信息。"""

    id: str
    workspace_id: str
    cwd: str
    pid: int
    argv: list[str]
    created_at: datetime
    last_active: datetime


class ShellListResponse(BaseModel):
    """Shell 会话列表响应。"""

    shells: list[ShellInfo]


class ShellCreateResponse(BaseModel):
    """创建 Shell 会话响应。"""

    id: str


class WorkspaceTaskInfoSchema(BaseModel):
    """工作区任务信息（用于队列状态展示）。"""

    source_chat_key: str
    prompt_preview: str
    enqueued_at: str
    started_at: str | None = None
    elapsed_seconds: float
    wait_seconds: float


class WorkspaceQueueResponse(BaseModel):
    """工作区任务队列状态响应。"""

    workspace_id: str
    current_task: WorkspaceTaskInfoSchema | None = None
    queued_tasks: list[WorkspaceTaskInfoSchema] = Field(default_factory=list)
    queue_length: int


class PendingResultItem(BaseModel):
    """单条待投递结果。"""

    id: str
    workspace_id: str
    source_chat_key: str
    result: str
    created_at: str
    expires_at: str
    is_error: bool = False
    error_code: str = ""


class PendingResultsResponse(BaseModel):
    """待投递结果列表响应（消费语义：返回后即从暂存区移除）。"""

    workspace_id: str
    results: list[PendingResultItem] = Field(default_factory=list)
    count: int
