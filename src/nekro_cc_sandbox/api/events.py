"""Events API for real-time updates"""

from collections.abc import AsyncGenerator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

router = APIRouter()


async def event_generator(request: Request) -> AsyncGenerator[str]:
    """Generate SSE events for client"""
    # Would implement actual event streaming here
    while True:
        if await request.is_disconnected():
            break
        yield "data: ping\n\n"
        break  # Remove for real implementation


@router.get("/events")
async def subscribe_events(request: Request) -> StreamingResponse:
    """
    Subscribe to workspace events via Server-Sent Events (SSE).

    Events include:
    - agent_tool_use
    - agent_thought
    - session_update
    - workspace_change
    """
    # This endpoint was previously a stub that returned a single "ping".
    # To avoid misleading clients, we explicitly return 501 and recommend the supported stream API.
    raise HTTPException(
        status_code=501,
        detail="Not implemented. Use POST /api/v1/message/stream for streaming responses.",
    )


@router.get("/events/{workspace_id}")
async def subscribe_workspace_events(workspace_id: str, request: Request) -> StreamingResponse:
    """Subscribe to events for a specific workspace"""
    raise HTTPException(
        status_code=501,
        detail="Not implemented. Use POST /api/v1/message/stream for streaming responses.",
    )
