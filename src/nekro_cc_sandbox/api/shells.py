"""Shell API：用于容器内交互式检查与操作（持久会话）。"""

from __future__ import annotations

import asyncio
import json
import secrets

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from loguru import logger
from pydantic import BaseModel, Field

from ..errors import new_err_id
from .schemas import OkResponse, ShellCreateResponse, ShellInfo, ShellListResponse

router = APIRouter()


def _is_authorized_websocket(websocket: WebSocket) -> bool:
    expected_token = getattr(websocket.app.state, "internal_api_token", "")
    if not expected_token:
        return False

    auth_header = websocket.headers.get("authorization", "")
    prefix = "Bearer "
    if auth_header.startswith(prefix):
        provided_token = auth_header[len(prefix):].strip()
        return bool(provided_token) and secrets.compare_digest(provided_token, expected_token)

    query_token = (websocket.query_params.get("token") or "").strip()
    return bool(query_token) and secrets.compare_digest(query_token, expected_token)


class CreateShellRequest(BaseModel):
    """创建 Shell 会话请求。"""

    workspace_id: str = "default"
    argv: list[str] = Field(default_factory=lambda: ["/bin/bash", "-l"])
    rows: int = 24
    cols: int = 80


@router.get("/shells", response_model=ShellListResponse)
async def list_shells(request: Request) -> ShellListResponse:
    """列出当前 Shell 会话。"""
    mgr = getattr(request.app.state, "shell_manager", None)
    if mgr is None:
        return ShellListResponse(shells=[])
    sessions = await mgr.list_sessions()
    return ShellListResponse(
        shells=[
            ShellInfo(
                id=s.id,
                workspace_id=s.workspace_id,
                cwd=s.cwd,
                pid=s.pid,
                argv=s.argv,
                created_at=s.created_at,
                last_active=s.last_active,
            )
            for s in sessions
        ]
    )


@router.post("/shells", response_model=ShellCreateResponse)
async def create_shell(request: Request, body: CreateShellRequest) -> ShellCreateResponse:
    """创建一个交互式 Shell 会话。"""
    mgr = getattr(request.app.state, "shell_manager", None)
    wm = getattr(request.app.state, "workspace_manager", None)
    if mgr is None or wm is None:
        raise HTTPException(status_code=503, detail="Shell manager not available")

    ws = await wm.get_workspace(body.workspace_id)
    if ws is None:
        ws = await wm.create_default_workspace(body.workspace_id)

    shell_id = new_err_id()
    try:
        await mgr.create(
            session_id=shell_id,
            workspace_id=body.workspace_id,
            cwd=str(ws.path),
            argv=body.argv,
            rows=body.rows,
            cols=body.cols,
        )
    except Exception as e:
        logger.exception(f"[shell] create failed id={shell_id} workspace_id={body.workspace_id}")
        raise HTTPException(status_code=500, detail=str(e))

    return ShellCreateResponse(id=shell_id)


@router.delete("/shells/{shell_id}", response_model=OkResponse)
async def close_shell(shell_id: str, request: Request) -> OkResponse:
    """关闭并销毁 Shell 会话。"""
    mgr = getattr(request.app.state, "shell_manager", None)
    if mgr is None:
        raise HTTPException(status_code=503, detail="Shell manager not available")
    await mgr.close(shell_id)
    return OkResponse()


@router.websocket("/shells/{shell_id}/ws")
async def shell_ws(websocket: WebSocket, shell_id: str):
    """Shell 交互 WebSocket。"""
    if not _is_authorized_websocket(websocket):
        await websocket.close(code=1008)
        return

    await websocket.accept()

    mgr = getattr(websocket.app.state, "shell_manager", None)
    if mgr is None:
        await websocket.send_text(json.dumps({"type": "error", "message": "Shell manager not available"}))
        await websocket.close(code=1011)
        return

    sess = await mgr.get(shell_id)
    if sess is None:
        await websocket.send_text(json.dumps({"type": "error", "message": "Shell session not found"}))
        await websocket.close(code=1008)
        return

    async def reader():
        try:
            while True:
                data = await mgr.read_chunk(shell_id)
                if not data:
                    await websocket.send_text(json.dumps({"type": "exit"}))
                    return
                await websocket.send_text(json.dumps({"type": "output", "data": data.decode("utf-8", errors="replace")}))
        except Exception as e:
            logger.warning(f"[shell] reader stopped id={shell_id}: {e}")

    reader_task = None
    try:
        await websocket.send_text(json.dumps({"type": "ready", "id": shell_id}))
        reader_task = asyncio.create_task(reader())
        while True:
            msg = await websocket.receive_text()
            try:
                obj = json.loads(msg)
            except Exception:
                continue
            t = obj.get("type")
            if t == "input":
                s = obj.get("data", "")
                if isinstance(s, str) and s:
                    await mgr.write(shell_id, s.encode("utf-8", errors="replace"))
            elif t == "resize":
                cols = int(obj.get("cols", 80))
                rows = int(obj.get("rows", 24))
                await mgr.resize(shell_id, rows=rows, cols=cols)
            elif t == "close":
                break
    except WebSocketDisconnect:
        pass
    finally:
        if reader_task is not None:
            reader_task.cancel()
        # 约束：页面关闭（WS 断开）或手动关闭时，必须销毁会话。
        await mgr.close(shell_id)
        try:
            await websocket.close()
        except Exception:
            pass
