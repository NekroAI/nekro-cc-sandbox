"""应用错误类型（用于稳定错误协议）。

目标：
- 后端响应可诊断（err_id、code、details）
- 前端可按 code 做分流展示与恢复提示
- 避免散落字符串导致协议漂移，确保 OpenAPI 能输出稳定 schema
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import uuid4


def new_err_id() -> str:
    """生成短追踪 ID（用于日志检索与客户端提示）。"""
    return uuid4().hex[:10]


class ErrorCode(StrEnum):
    """稳定错误码枚举（前后端契约）。"""

    RUNTIME_UNAVAILABLE = "RUNTIME_UNAVAILABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    WORKSPACE_NOT_FOUND = "WORKSPACE_NOT_FOUND"
    CLAUDE_CLI_ERROR_RESULT = "CLAUDE_CLI_ERROR_RESULT"
    CLAUDE_CLI_NO_PARSEABLE_OUTPUT = "CLAUDE_CLI_NO_PARSEABLE_OUTPUT"
    SHELL_MANAGER_UNAVAILABLE = "SHELL_MANAGER_UNAVAILABLE"
    SHELL_SESSION_NOT_FOUND = "SHELL_SESSION_NOT_FOUND"
    TASK_CANCELLED = "TASK_CANCELLED"


@dataclass(frozen=True, slots=True)
class AppError(Exception):
    """带稳定错误码的应用异常基类。"""

    code: ErrorCode
    message: str
    retryable: bool = False
    details: dict[str, Any] | None = None
    err_id: str | None = None

    def __str__(self) -> str:  # pragma: no cover
        return self.message


class ClaudeCliError(AppError):
    """Claude CLI 调用/输出导致的失败。"""
