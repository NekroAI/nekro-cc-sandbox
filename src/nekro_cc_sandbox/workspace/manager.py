"""Workspace lifecycle management"""

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from .state import WorkspaceState


class WorkspaceManager:
    """Manages workspace lifecycle and state"""

    def __init__(self, root_path: Path):
        self.root_path = Path(root_path)
        self._states: dict[str, WorkspaceState] = {}
        self._lock = asyncio.Lock()

    async def create_default_workspace(self, name: str = "default") -> WorkspaceState:
        """Create or get the default workspace"""
        async with self._lock:
            if name in self._states:
                return self._states[name]

            workspace_path = self.root_path / name
            state_path = workspace_path / ".workspace_state.json"

            # Create workspace directory
            workspace_path.mkdir(parents=True, exist_ok=True)

            # Load existing state or create new one
            if state_path.exists():
                state = WorkspaceState.load(state_path)
            else:
                state = WorkspaceState(
                    id=name,
                    path=workspace_path,
                    name=name,
                )
                state.save(state_path)

            self._states[name] = state
            return state

    async def get_workspace(self, name: str = "default") -> WorkspaceState | None:
        """Get workspace by name"""
        return self._states.get(name)

    async def update_session(self, name: str, session_id: str) -> None:
        """Update workspace session ID"""
        async with self._lock:
            if name in self._states:
                state = self._states[name]
                state.session_id = session_id
                state.updated_at = datetime.now(UTC)
                state.save(state.path / ".workspace_state.json")

    async def list_workspaces(self) -> list[WorkspaceState]:
        """List all workspaces"""
        return list(self._states.values())

    async def delete_workspace(self, name: str) -> bool:
        """Delete a workspace (mark as inactive)"""
        async with self._lock:
            if name in self._states:
                del self._states[name]
                return True
            return False
