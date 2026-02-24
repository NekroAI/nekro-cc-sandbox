"""状态 API：用于监控工作区与运行时能力。"""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

from fastapi import APIRouter, HTTPException, Request

from ..errors import AppError, ErrorCode, new_err_id
from .schemas import (
    CapabilitiesInfo,
    PolicySummary,
    ServicesInfo,
    SessionDetailResponse,
    SessionInfo,
    SessionResetResponse,
    SessionsResponse,
    StatusResponse,
    ToolsInfoResponse,
    WorkspaceInfo,
    WorkspacesResponse,
    WorkspacesSummary,
)

router = APIRouter()


@router.get("/workspaces", response_model=WorkspacesResponse)
async def list_workspaces(request: Request) -> WorkspacesResponse:
    """列出所有工作区。"""
    wm = getattr(request.app.state, "workspace_manager", None)
    if wm is None:
        return WorkspacesResponse(workspaces=[])
    workspaces = await wm.list_workspaces()
    return WorkspacesResponse(
        workspaces=[
            WorkspaceInfo(
                id=ws.id,
                name=ws.name,
                path=str(ws.path),
                created_at=ws.created_at,
                updated_at=ws.updated_at,
                session_id=ws.session_id,
                metadata=ws.metadata,
            )
            for ws in workspaces
        ]
    )


@router.get("/workspaces/{workspace_id}", response_model=WorkspaceInfo)
async def get_workspace(workspace_id: str, request: Request) -> WorkspaceInfo:
    """获取单个工作区详情。"""
    wm = getattr(request.app.state, "workspace_manager", None)
    if wm is None:
        raise HTTPException(status_code=503, detail="Workspace manager not available")
    ws = await wm.get_workspace(workspace_id)
    if ws is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return WorkspaceInfo(
        id=ws.id,
        name=ws.name,
        path=str(ws.path),
        created_at=ws.created_at,
        updated_at=ws.updated_at,
        session_id=ws.session_id,
        metadata=ws.metadata,
    )


@router.post("/workspaces/{workspace_id}/session/reset", response_model=SessionResetResponse)
async def reset_workspace_session(workspace_id: str, request: Request) -> SessionResetResponse:
    """重置指定工作区的 Claude Code 会话（清空 session_id）。"""
    wm = getattr(request.app.state, "workspace_manager", None)
    if wm is None:
        raise HTTPException(status_code=503, detail="Workspace manager not available")

    ws = await wm.get_workspace(workspace_id)
    if ws is None:
        raise HTTPException(status_code=404, detail="Workspace not found")

    old_sid = ws.session_id
    await wm.update_session(workspace_id, "")

    runtime = getattr(request.app.state, "claude_runtime", None)
    if runtime is not None and hasattr(runtime, "reset_workspace_session"):
        await runtime.reset_workspace_session(workspace_id)

    return SessionResetResponse(workspace_id=workspace_id, old_session_id=old_sid, new_session_id=None)


@router.get("/status", response_model=StatusResponse)
async def get_status(request: Request) -> StatusResponse:
    """获取系统状态（含运行时能力与工作区汇总）。"""
    wm = getattr(request.app.state, "workspace_manager", None)
    runtime = getattr(request.app.state, "claude_runtime", None)
    workspaces = await wm.list_workspaces() if wm else []

    default_ws_id = "default"
    last_tools: list[str] | None = None
    policy_summary: PolicySummary | None = None
    if runtime is not None:
        last_tools = runtime.get_last_tools(default_ws_id) if hasattr(runtime, "get_last_tools") else None
        policy = getattr(runtime, "policy", None)
        if policy is not None:
            policy_summary = PolicySummary(
                allowed_tools=sorted(getattr(policy, "allowed_tools", set()) or []),
                blocked_tools=sorted(getattr(policy, "blocked_tools", set()) or []),
                allow_network=bool(getattr(policy, "allow_network", True)),
                allow_file_modification=bool(getattr(policy, "allow_file_modification", True)),
                allow_command_execution=bool(getattr(policy, "allow_command_execution", True)),
            )

    try:
        _version = _pkg_version("nekro-cc-sandbox")
    except PackageNotFoundError:
        _version = "unknown"

    claude_version: str | None = getattr(request.app.state, "claude_code_version", None)

    return StatusResponse(
        services=ServicesInfo(
            claude_runtime="available" if runtime is not None else "unavailable",
        ),
        capabilities=CapabilitiesInfo(
            tools=last_tools,
            policy=policy_summary,
        ),
        workspaces=WorkspacesSummary(
            count=len(workspaces),
            ids=[ws.id for ws in workspaces],
        ),
        version=_version,
        claude_version=claude_version,
    )


@router.get("/capabilities/tools", response_model=ToolsInfoResponse)
async def get_tools(request: Request) -> ToolsInfoResponse:
    """获取工具列表（缓存）。"""
    runtime = getattr(request.app.state, "claude_runtime", None)
    if runtime is None:
        return ToolsInfoResponse(tools=None, source="cache")
    tools = runtime.get_last_tools("default") if hasattr(runtime, "get_last_tools") else None
    return ToolsInfoResponse(tools=tools, source="cache")


@router.post("/capabilities/tools/refresh", response_model=ToolsInfoResponse)
async def refresh_tools(request: Request) -> ToolsInfoResponse:
    """刷新工具列表（独立探测，不与会话绑定）。"""
    runtime = getattr(request.app.state, "claude_runtime", None)
    if runtime is None:
        raise AppError(
            code=ErrorCode.RUNTIME_UNAVAILABLE,
            message="Claude runtime not available",
            retryable=True,
            details={"hint": "检查 lifespan 是否正常启动", "path": "/api/v1/capabilities/tools/refresh"},
            err_id=new_err_id(),
        )
    if not hasattr(runtime, "probe_tools"):
        raise AppError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Claude runtime does not support tool probing",
            retryable=False,
            details={"hint": "运行时缺少 probe_tools()", "path": "/api/v1/capabilities/tools/refresh"},
            err_id=new_err_id(),
        )
    tools = await runtime.probe_tools(workspace_id="default")
    return ToolsInfoResponse(tools=tools, source="probe")


@router.get("/sessions", response_model=SessionsResponse)
async def list_sessions(request: Request) -> SessionsResponse:
    """列出当前已知会话（来自工作区持久化 session_id）。"""
    wm = getattr(request.app.state, "workspace_manager", None)
    if wm is None:
        return SessionsResponse(sessions=[])
    workspaces = await wm.list_workspaces()
    sessions: list[SessionInfo] = []
    for ws in workspaces:
        if ws.session_id:
            sessions.append(SessionInfo(workspace_id=ws.id, session_id=ws.session_id))
    return SessionsResponse(sessions=sessions)


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def get_session(session_id: str, request: Request) -> SessionDetailResponse:
    """获取会话详情（在本项目中仅能判断是否被某工作区引用）。"""
    wm = getattr(request.app.state, "workspace_manager", None)
    if wm is None:
        raise HTTPException(status_code=503, detail="Workspace manager not available")
    workspaces = await wm.list_workspaces()
    for ws in workspaces:
        if ws.session_id == session_id:
            return SessionDetailResponse(session_id=session_id, workspace_id=ws.id)
    raise HTTPException(status_code=404, detail="Session not found")
