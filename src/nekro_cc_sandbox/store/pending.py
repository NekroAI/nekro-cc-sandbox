"""待投递结果暂存（内存，带 TTL）

用途：NA 与 CC 之间的流式连接断开（NA 重启）时，CC 完成的结果先暂存在此；
NA 重新启动后主动来取，保证结果不丢失。

设计约束：
- 纯内存，不写磁盘（CC sandbox 重启后 pending 结果也视为过期，NA 需重新委托）
- 每个 workspace 只保留同一 source_chat_key 的最后一条结果（重复调用覆盖旧值）
- TTL 默认 3600 秒，可在 add() 时覆盖
- 后台清理任务每 60 秒运行一次
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import ClassVar

from loguru import logger


@dataclass
class PendingResult:
    """一条未投递的 CC 结果。"""

    id: str
    workspace_id: str
    source_chat_key: str
    result: str
    created_at: datetime
    expires_at: datetime

    def is_expired(self) -> bool:
        return datetime.now(UTC) >= self.expires_at

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "source_chat_key": self.source_chat_key,
            "result": self.result,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
        }


class PendingResultStore:
    """待投递结果内存存储，全局单例。"""

    _instance: ClassVar[PendingResultStore | None] = None

    def __new__(cls) -> PendingResultStore:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False  # noqa: SLF001
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        # workspace_id -> list[PendingResult]
        self._store: dict[str, list[PendingResult]] = {}
        self._cleanup_task: asyncio.Task | None = None
        self._initialized = True

    # ------------------------------------------------------------------
    # 写入
    # ------------------------------------------------------------------

    def add(
        self,
        workspace_id: str,
        source_chat_key: str,
        result: str,
        ttl_seconds: int = 3600,
    ) -> PendingResult:
        """新增一条待投递结果。同一 (workspace_id, source_chat_key) 会覆盖旧值。"""
        now = datetime.now(UTC)
        entry = PendingResult(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            source_chat_key=source_chat_key,
            result=result,
            created_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
        )
        bucket = self._store.setdefault(workspace_id, [])
        # 覆盖同 source_chat_key 的旧条目（避免重复推送）
        self._store[workspace_id] = [
            r for r in bucket if r.source_chat_key != source_chat_key
        ]
        self._store[workspace_id].append(entry)
        logger.info(
            f"[PendingResultStore] 暂存结果: workspace={workspace_id!r} "
            f"source_chat_key={source_chat_key!r} id={entry.id} ttl={ttl_seconds}s"
        )
        return entry

    # ------------------------------------------------------------------
    # 读取（消费语义：读后即删）
    # ------------------------------------------------------------------

    def pop_all(self, workspace_id: str) -> list[PendingResult]:
        """取出并移除指定工作区的所有未过期待投递结果。"""
        bucket = self._store.get(workspace_id, [])
        valid = [r for r in bucket if not r.is_expired()]
        if valid:
            self._store[workspace_id] = []
            logger.info(
                f"[PendingResultStore] 消费 {len(valid)} 条结果: workspace={workspace_id!r}"
            )
        return valid

    def count(self, workspace_id: str | None = None) -> int:
        """返回待投递结果数量（可按工作区过滤）。"""
        if workspace_id is not None:
            return len([r for r in self._store.get(workspace_id, []) if not r.is_expired()])
        return sum(
            len([r for r in entries if not r.is_expired()])
            for entries in self._store.values()
        )

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    def start_cleanup_task(self) -> None:
        """启动后台过期清理任务（应在 lifespan 中调用）。"""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.debug("[PendingResultStore] 清理任务已启动")

    def stop_cleanup_task(self) -> None:
        """停止后台清理任务（应在 lifespan shutdown 中调用）。"""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            logger.debug("[PendingResultStore] 清理任务已停止")

    async def _cleanup_loop(self) -> None:
        """每 60 秒清理一次过期条目。"""
        while True:
            try:
                await asyncio.sleep(60)
                removed = 0
                for ws_id in list(self._store.keys()):
                    before = len(self._store[ws_id])
                    self._store[ws_id] = [
                        r for r in self._store[ws_id] if not r.is_expired()
                    ]
                    removed += before - len(self._store[ws_id])
                if removed:
                    logger.debug(f"[PendingResultStore] 清理过期条目: {removed} 条")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"[PendingResultStore] 清理任务异常: {e}")
