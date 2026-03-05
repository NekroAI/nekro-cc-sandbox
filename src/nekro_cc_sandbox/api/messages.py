"""消息 API：与 Claude Code 工作区进行交互。"""

import asyncio
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
        session = await runtime.start(workspace_id)
        response_chunks: list[str] = []
        from ..claude.runtime import QueueWaitEvent, ToolCallEvent, ToolResultEvent
        async for item in runtime.send_message_in_workspace(workspace_id, body.content, body.source_chat_key, extra_env=body.env_vars or None):
            if isinstance(item, (QueueWaitEvent, ToolCallEvent, ToolResultEvent)):
                continue
            response_chunks.append(item)

        response_text = "".join(response_chunks)

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
        sid = getattr(locals().get("session"), "session_id", "") or ""
        return MessageResponse(
            session_id=sid,
            message=f"Error({err_id}): {e.message}",
            success=False,
            error=_error_payload(err_id=err_id, code=e.code, message=e.message, retryable=e.retryable, details=e.details),
        )
    except Exception as e:
        err_id = new_err_id()
        logger.exception(f"[messages] /message failed err_id={err_id} code=INTERNAL_ERROR workspace_id={workspace_id}")
        sid = getattr(locals().get("session"), "session_id", "") or ""
        return MessageResponse(
            session_id=sid,
            message=f"Error({err_id}): Internal error",
            success=False,
            error=_error_payload(err_id=err_id, code=ErrorCode.INTERNAL_ERROR, message=str(e), retryable=True),
        )


@router.post("/message/stream")
async def send_message_stream(request: Request, body: MessageRequest):
    """
    Send a message and stream the response (SSE).

    容灾设计：CC 执行期间若客户端（NA）断开连接（如服务重启），CC 子进程仍会在后台
    完成执行，结果暂存至 PendingResultStore（TTL 1 小时）。NA 重新上线后可通过
    GET /api/v1/workspaces/{workspace_id}/pending-results 取回并推送到对应频道。
    """
    runtime = getattr(request.app.state, "claude_runtime", None)
    pending_store = getattr(request.app.state, "pending_store", None)
    workspace_id = body.workspace_id or "default"
    source_chat_key = body.source_chat_key

    # 无界队列在后台 CC Task 与 SSE 流之间传递事件；None 为结束哨兵
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    # CC Task 完成后等待客户端确认收到的信号
    # event_generator 读到哨兵后设置；超时说明客户端已断开
    client_received_all: asyncio.Event = asyncio.Event()

    async def run_cc() -> None:
        """在独立 asyncio.Task 中执行 CC，生命周期与 HTTP 连接解耦。"""
        chunks: list[str] = []
        error_message: str = ""
        error_code: str = ""

        logger.info(
            f"[messages] SSE stream started: workspace={workspace_id!r} "
            f"source_chat_key={source_chat_key!r} "
            f"content_len={len(body.content)}"
        )

        if runtime is None:
            err_id = new_err_id()
            logger.error(f"[messages] runtime missing err_id={err_id} workspace_id={workspace_id}")
            await queue.put(json.dumps({
                "type": "error",
                "message": f"Error({err_id}): runtime not available",
                "error": _error_payload(
                    err_id=err_id,
                    code=ErrorCode.RUNTIME_UNAVAILABLE,
                    message="claude_runtime not initialized",
                    retryable=True,
                ).model_dump(),
            }, ensure_ascii=False))
            await queue.put(None)
            return

        try:
            await runtime.start(workspace_id)
            from ..claude.runtime import QueueWaitEvent, ToolCallEvent, ToolResultEvent

            async for item in runtime.send_message_in_workspace(
                workspace_id,
                body.content,
                source_chat_key,
                extra_env=body.env_vars or None,
            ):
                if isinstance(item, QueueWaitEvent):
                    event_data = json.dumps({
                        "type": "queued",
                        "position": item.position,
                        "queued_count": item.queued_count,
                        "current_task": item.current_task.to_dict(),
                    }, ensure_ascii=False)
                elif isinstance(item, ToolCallEvent):
                    event_data = json.dumps({
                        "type": "tool_call",
                        "tool_use_id": item.tool_use_id,
                        "name": item.name,
                        "input": item.input,
                    }, ensure_ascii=False)
                elif isinstance(item, ToolResultEvent):
                    event_data = json.dumps({
                        "type": "tool_result",
                        "tool_use_id": item.tool_use_id,
                        "content": item.content,
                        "is_error": item.is_error,
                    }, ensure_ascii=False)
                else:
                    # 文本 chunk：累积以备暂存，同时推入队列
                    chunks.append(item)
                    event_data = json.dumps({"type": "chunk", "chunk": item}, ensure_ascii=False)

                await queue.put(event_data)

        except AppError as e:
            err_id = e.err_id or new_err_id()
            logger.exception(
                f"[messages] stream CC task AppError err_id={err_id} code={e.code} workspace={workspace_id}"
            )
            error_message = f"Error({err_id}): {e.message}"
            error_code = str(e.code.value) if hasattr(e.code, "value") else str(e.code)
            await queue.put(json.dumps({
                "type": "error",
                "message": error_message,
                "error": _error_payload(
                    err_id=err_id, code=e.code, message=e.message,
                    retryable=e.retryable, details=e.details,
                ).model_dump(),
            }, ensure_ascii=False))

        except Exception as e:
            err_id = new_err_id()
            logger.exception(
                f"[messages] stream CC task Exception err_id={err_id} workspace={workspace_id}"
            )
            error_message = f"Error({err_id}): Internal error"
            error_code = str(ErrorCode.INTERNAL_ERROR.value) if hasattr(ErrorCode.INTERNAL_ERROR, "value") else str(ErrorCode.INTERNAL_ERROR)
            await queue.put(json.dumps({
                "type": "error",
                "message": error_message,
                "error": _error_payload(
                    err_id=err_id, code=ErrorCode.INTERNAL_ERROR, message=str(e), retryable=True,
                ).model_dump(),
            }, ensure_ascii=False))

        finally:
            # 放入哨兵，通知 event_generator CC 已结束
            await queue.put(None)
            total_chars = sum(len(c) for c in chunks)
            logger.info(
                f"[messages] SSE CC task finished: workspace={workspace_id!r} "
                f"source_chat_key={source_chat_key!r} "
                f"chunks={len(chunks)} total_chars={total_chars} "
                f"has_error={bool(error_message)}"
            )

        # 等待客户端确认收到（最多 5 秒）
        # 若超时说明客户端在流完成前已断开，将结果暂存供 NA 重启后恢复
        try:
            await asyncio.wait_for(client_received_all.wait(), timeout=5.0)
        except TimeoutError:
            full_result = "".join(chunks)
            # 正常结果暂存
            if full_result.strip() and source_chat_key and pending_store is not None:
                pending_store.add(workspace_id, source_chat_key, full_result)
                logger.warning(
                    f"[messages] 客户端已断开，CC 结果已暂存: "
                    f"workspace={workspace_id!r} source_chat_key={source_chat_key!r} "
                    f"chars={len(full_result)}"
                )
            # 错误结果暂存（标记 is_error），让 NA Watcher 能感知到错误。
            # 例外：TASK_CANCELLED 是 NA 主动发起的取消，NA 侧已通过 SSE 流实时感知，
            # 无需再通过 PendingResultStore 二次投递，避免 NA 收到重复的"任务失败"通知。
            elif (
                error_message
                and source_chat_key
                and pending_store is not None
                and error_code != "TASK_CANCELLED"
            ):
                pending_store.add(
                    workspace_id, source_chat_key, error_message,
                    is_error=True, error_code=error_code,
                )
                logger.warning(
                    f"[messages] 客户端已断开，CC 错误已暂存: "
                    f"workspace={workspace_id!r} source_chat_key={source_chat_key!r} "
                    f"error_code={error_code!r}"
                )
            elif error_message and error_code == "TASK_CANCELLED":
                logger.debug(
                    f"[messages] TASK_CANCELLED 不暂存（NA 已通过 SSE 实时感知）: "
                    f"workspace={workspace_id!r} source_chat_key={source_chat_key!r}"
                )
            else:
                logger.debug(
                    f"[messages] 客户端断开但无需暂存（无结果或无 chat_key）: "
                    f"workspace={workspace_id!r} has_result={bool(chunks)} "
                    f"has_chat_key={bool(source_chat_key)}"
                )

    # 独立 Task：不受 HTTP 请求取消的影响
    asyncio.create_task(run_cc())

    async def event_generator():
        try:
            while True:
                item = await queue.get()
                if item is None:
                    # 哨兵：通知 run_cc 任务数据已全部投递
                    client_received_all.set()
                    return
                yield f"data: {item}\n\n"
        except (asyncio.CancelledError, GeneratorExit):
            # 客户端断开：不设置 client_received_all，让 run_cc 超时后暂存结果
            logger.warning(
                f"[messages] SSE client disconnected: workspace={workspace_id!r} "
                f"source_chat_key={source_chat_key!r}"
            )
            raise

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


@router.get("/workspaces/{workspace_id}/pending-results")
async def get_pending_results(workspace_id: str, request: Request):
    """取出并消费指定工作区的所有待投递结果（读后即删）。

    NA 重启后调用此接口获取 CC 在断线期间完成的任务结果，
    再投递到对应聊天频道触发 Agent 响应，实现无感重启。
    """
    from ..api.schemas import PendingResultItem, PendingResultsResponse

    pending_store = getattr(request.app.state, "pending_store", None)
    if pending_store is None:
        return PendingResultsResponse(workspace_id=workspace_id, results=[], count=0)

    results = pending_store.pop_all(workspace_id)
    return PendingResultsResponse(
        workspace_id=workspace_id,
        results=[
            PendingResultItem(
                id=r.id,
                workspace_id=r.workspace_id,
                source_chat_key=r.source_chat_key,
                result=r.result,
                created_at=r.created_at.isoformat(),
                expires_at=r.expires_at.isoformat(),
                is_error=r.is_error,
                error_code=r.error_code,
            )
            for r in results
        ],
        count=len(results),
    )
