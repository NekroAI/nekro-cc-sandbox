"""交互式 Shell 会话管理（基于 PTY）。

设计目标：
- 每个浏览器会话对应一个可持续交互的 Shell（通过 WebSocket）
- 页面关闭/手动关闭时销毁 Shell（避免僵尸进程）
- 尽量只使用标准库能力，便于容器化交付
"""

from __future__ import annotations

import asyncio
import fcntl
import os
import signal
import struct
import termios
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from loguru import logger


@dataclass(slots=True)
class ShellSession:
    id: str
    workspace_id: str
    cwd: str
    argv: list[str]
    master_fd: int
    pid: int
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_active: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "cwd": self.cwd,
            "pid": self.pid,
            "argv": self.argv,
            "created_at": self.created_at.isoformat(),
            "last_active": self.last_active.isoformat(),
        }


class ShellManager:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._sessions: dict[str, ShellSession] = {}

    async def list_sessions(self) -> list[ShellSession]:
        async with self._lock:
            return list(self._sessions.values())

    async def get(self, session_id: str) -> ShellSession | None:
        async with self._lock:
            return self._sessions.get(session_id)

    async def create(
        self,
        *,
        session_id: str,
        workspace_id: str,
        cwd: str,
        argv: list[str],
        rows: int = 24,
        cols: int = 80,
        env: dict[str, str] | None = None,
    ) -> ShellSession:
        async with self._lock:
            if session_id in self._sessions:
                raise RuntimeError(f"Shell 会话已存在: {session_id}")

            pid, master_fd = os.forkpty()
            if pid == 0:
                # 子进程：进入工作目录并 exec shell
                try:
                    os.chdir(cwd)
                except Exception:
                    pass

                try:
                    # Set initial window size
                    winsz = struct.pack("HHHH", rows, cols, 0, 0)
                    fcntl.ioctl(0, termios.TIOCSWINSZ, winsz)
                except Exception:
                    pass

                child_env = os.environ.copy()
                if env:
                    child_env.update(env)

                # 为交互式程序设置 TERM
                child_env.setdefault("TERM", "xterm-256color")
                os.execvpe(argv[0], argv, child_env)

            sess = ShellSession(
                id=session_id,
                workspace_id=workspace_id,
                cwd=cwd,
                argv=argv,
                master_fd=master_fd,
                pid=pid,
            )
            self._sessions[session_id] = sess
            logger.info(f"[shell] created id={session_id} pid={pid} cwd={cwd!r} argv={argv!r}")
            return sess

    async def resize(self, session_id: str, *, rows: int, cols: int) -> None:
        sess = await self.get(session_id)
        if not sess:
            raise KeyError(session_id)
        winsz = struct.pack("HHHH", rows, cols, 0, 0)
        fcntl.ioctl(sess.master_fd, termios.TIOCSWINSZ, winsz)

    async def write(self, session_id: str, data: bytes) -> None:
        sess = await self.get(session_id)
        if not sess:
            raise KeyError(session_id)
        os.write(sess.master_fd, data)
        sess.last_active = datetime.now(UTC)

    async def read_chunk(self, session_id: str, n: int = 4096) -> bytes:
        sess = await self.get(session_id)
        if not sess:
            raise KeyError(session_id)
        # PTY read is blocking; run in thread to avoid blocking event loop.
        return await asyncio.to_thread(os.read, sess.master_fd, n)

    async def close(self, session_id: str) -> None:
        async with self._lock:
            sess = self._sessions.pop(session_id, None)
        if not sess:
            return
        try:
            os.kill(sess.pid, signal.SIGHUP)
        except ProcessLookupError:
            pass
        except Exception as e:
            logger.warning(f"[shell] kill failed id={session_id}: {e}")
        try:
            os.close(sess.master_fd)
        except Exception:
            pass
        logger.info(f"[shell] closed id={session_id}")

    async def close_all(self) -> None:
        sessions = await self.list_sessions()
        for s in sessions:
            await self.close(s.id)

