"""消息 API：与 Claude Code 工作区进行交互。"""

import json
from typing import Any

from fastapi import APIRouter, Request
from loguru import logger
from pydantic import BaseModel

from ..errors import AppError, ErrorCode, new_err_id
from .schemas import ErrorInfo

router = APIRouter()


class MessageRequest(BaseModel):
    """发送消息请求。"""

    role: str = "user"
    content: str
    workspace_id: str = "default"
    source_chat_key: str = ""
    env_vars: dict[str, str] = {}


class MessageResponse(BaseModel):
    """发送消息响应。"""

    session_id: str
    message: str
    success: bool
    error: ErrorInfo | None = None


def _error_payload(
    *,
    err_id: str,
    code: ErrorCode,
    message: str,
    retryable: bool = False,
    details: dict[str, Any] | None = None,
) -> ErrorInfo:
    return ErrorInfo(
        err_id=err_id,
        code=code,
        message=message,
        retryable=retryable,
        details=details,
    )


@router.post("/message", response_model=MessageResponse)
async def send_message(request: Request, body: MessageRequest) -> MessageResponse:
    """
    Send a message to the Workspace Agent (Claude Code).

    The sandbox forwards this message to Claude Code and streams the response.
    """
    # Use request.app.state to access app-scoped state
    runtime = getattr(request.app.state, "claude_runtime", None)
    workspace_id = body.workspace_id or "default"

    if runtime is None:
        err_id = new_err_id()
        logger.error(f"[messages] runtime missing err_id={err_id} workspace_id={workspace_id}")
        return MessageResponse(
            session_id="",
            message="Claude runtime not available. Make sure the server is running with proper lifespan context.",
            success=False,
            error=_error_payload(
                err_id=err_id,
                code=ErrorCode.RUNTIME_UNAVAILABLE,
                message="claude_runtime not initialized (lifespan not running?)",
                retryable=True,
            ),
        )

    try:
        # Ensure runtime is started for the workspace
        session = await runtime.start(workspace_id)

        # Collect response chunks
        response_chunks = []
        from ..claude.runtime import QueueWaitEvent
        async for item in runtime.send_message_in_workspace(workspace_id, body.content, body.source_chat_key, extra_env=body.env_vars or None):
            if isinstance(item, QueueWaitEvent):
                continue  # 同步接口静默等待，不展示排队事件
            response_chunks.append(item)

        # Parse the final response
        response_text = "".join(response_chunks)

        # 约束：空文本响应视为失败（避免“success=true 但 message 为空”的虚假成功）
        if not response_text.strip():
            err_id = new_err_id()
            logger.error(
                f"[messages] empty response err_id={err_id} workspace_id={workspace_id} session_id={session.session_id!r}"
            )
            return MessageResponse(
                session_id=session.session_id,
                message=f"Error({err_id}): Claude returned empty response",
                success=False,
                error=_error_payload(
                    err_id=err_id,
                    code=ErrorCode.CLAUDE_CLI_NO_PARSEABLE_OUTPUT,
                    message="Claude returned empty response text",
                    retryable=True,
                    details={"workspace_id": workspace_id, "session_id": session.session_id},
                ),
            )

        return MessageResponse(session_id=session.session_id, message=response_text, success=True)
    except AppError as e:
        err_id = e.err_id or new_err_id()
        logger.exception(f"[messages] /message failed err_id={err_id} code={e.code} workspace_id={workspace_id}")
        sid = ""
        maybe_session = locals().get("session")
        if maybe_session is not None:
            sid = getattr(maybe_session, "session_id", "") or ""
        return MessageResponse(
            session_id=sid,
            message=f"Error({err_id}): {e.message}",
            success=False,
            error=_error_payload(
                err_id=err_id,
                code=e.code,
                message=e.message,
                retryable=e.retryable,
                details=e.details,
            ),
        )
    except Exception as e:
        err_id = new_err_id()
        logger.exception(f"[messages] /message failed err_id={err_id} code=INTERNAL_ERROR workspace_id={workspace_id}")
        sid = ""
        maybe_session = locals().get("session")
        if maybe_session is not None:
            sid = getattr(maybe_session, "session_id", "") or ""
        return MessageResponse(
            session_id=sid,
            message=f"Error({err_id}): Internal error",
            success=False,
            error=_error_payload(
                err_id=err_id,
                code=ErrorCode.INTERNAL_ERROR,
                message=str(e),
                retryable=True,
            ),
        )


@router.post("/message/stream")
async def send_message_stream(request: Request, body: MessageRequest):
    """
    Send a message and stream the response.

    Returns a Server-Sent Events (SSE) stream of Claude Code output.
    """
    # Use request.app.state to access app-scoped state
    runtime = getattr(request.app.state, "claude_runtime", None)
    workspace_id = body.workspace_id or "default"

    async def event_generator():
        if runtime is None:
            err_id = new_err_id()
            logger.error(f"[messages] runtime missing err_id={err_id} workspace_id={workspace_id}")
            yield f"data: {json.dumps({'type': 'error', 'message': f'Error({err_id}): runtime not available', 'error': _error_payload(err_id=err_id, code=ErrorCode.RUNTIME_UNAVAILABLE, message='claude_runtime not initialized', retryable=True).model_dump()}, ensure_ascii=False)}\n\n"
            return

        try:
            # Start runtime if not already running
            await runtime.start(workspace_id)

            from ..claude.runtime import QueueWaitEvent, ToolCallEvent, ToolResultEvent
            async for item in runtime.send_message_in_workspace(workspace_id, body.content, body.source_chat_key, extra_env=body.env_vars or None):
                if isinstance(item, QueueWaitEvent):
                    queued_data = {
                        "type": "queued",
                        "position": item.position,
                        "queued_count": item.queued_count,
                        "current_task": item.current_task.to_dict(),
                    }
                    yield f"data: {json.dumps(queued_data, ensure_ascii=False)}\n\n"
                elif isinstance(item, ToolCallEvent):
                    yield f"data: {json.dumps({'type': 'tool_call', 'tool_use_id': item.tool_use_id, 'name': item.name, 'input': item.input}, ensure_ascii=False)}\n\n"
                elif isinstance(item, ToolResultEvent):
                    yield f"data: {json.dumps({'type': 'tool_result', 'tool_use_id': item.tool_use_id, 'content': item.content, 'is_error': item.is_error}, ensure_ascii=False)}\n\n"
                else:
                    yield f"data: {json.dumps({'type': 'chunk', 'chunk': item}, ensure_ascii=False)}\n\n"
        except AppError as e:
            err_id = e.err_id or new_err_id()
            logger.exception(f"[messages] /message/stream failed err_id={err_id} code={e.code} workspace_id={workspace_id}")
            yield f"data: {json.dumps({'type': 'error', 'message': f'Error({err_id}): {e.message}', 'error': _error_payload(err_id=err_id, code=e.code, message=e.message, retryable=e.retryable, details=e.details).model_dump()}, ensure_ascii=False)}\n\n"
        except Exception as e:
            err_id = new_err_id()
            logger.exception(f"[messages] /message/stream failed err_id={err_id} code=INTERNAL_ERROR workspace_id={workspace_id}")
            yield f"data: {json.dumps({'type': 'error', 'message': f'Error({err_id}): Internal error', 'error': _error_payload(err_id=err_id, code=ErrorCode.INTERNAL_ERROR, message=str(e), retryable=True).model_dump()}, ensure_ascii=False)}\n\n"

    from fastapi.responses import StreamingResponse
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/workspaces/{workspace_id}/queue")
async def get_workspace_queue(workspace_id: str, request: Request):
    """获取工作区任务队列状态（当前任务 + 等待队列）。"""
    from ..api.schemas import WorkspaceQueueResponse, WorkspaceTaskInfoSchema

    runtime = getattr(request.app.state, "claude_runtime", None)
    if runtime is None:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=503, content={"error": "runtime not available"})

    status = runtime.get_workspace_queue_status(workspace_id)
    current = status["current_task"]
    queued = status["queued_tasks"]
    return WorkspaceQueueResponse(
        workspace_id=workspace_id,
        current_task=WorkspaceTaskInfoSchema(**current) if current else None,
        queued_tasks=[WorkspaceTaskInfoSchema(**t) for t in queued],
        queue_length=status["queue_length"],
    )


@router.delete("/workspaces/{workspace_id}/queue/current")
async def force_cancel_workspace_task(workspace_id: str, request: Request):
    """强制取消工作区当前正在运行的任务。"""
    runtime = getattr(request.app.state, "claude_runtime", None)
    if runtime is None:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=503, content={"error": "runtime not available"})

    cancelled = await runtime.force_cancel_workspace_task(workspace_id)
    return {"cancelled": cancelled, "workspace_id": workspace_id}
