"""Workspace state management"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class WorkspaceState:
    """Represents a workspace state"""

    id: str
    path: Path
    name: str = "default"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    session_id: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary"""
        data: dict[str, object] = asdict(self)
        data["path"] = str(self.path)
        # Convert datetime to ISO format string
        data["created_at"] = self.created_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "WorkspaceState":
        """Create from dictionary"""
        # Extract values with proper type annotations
        path_str = data["path"]
        assert isinstance(path_str, str)
        path = Path(path_str)

        created_at_str = data.get("created_at")
        if isinstance(created_at_str, str):
            created_at = datetime.fromisoformat(created_at_str)
        else:
            created_at = datetime.now()

        updated_at_str = data.get("updated_at")
        if isinstance(updated_at_str, str):
            updated_at = datetime.fromisoformat(updated_at_str)
        else:
            updated_at = datetime.now()

        name = data.get("name", "default")
        assert isinstance(name, str)

        session_id_raw = data.get("session_id")
        session_id: str | None = None
        if isinstance(session_id_raw, str):
            session_id = session_id_raw

        metadata_raw = data.get("metadata")
        metadata: dict[str, object] = {}
        if isinstance(metadata_raw, dict):
            metadata = metadata_raw

        id_raw = data["id"]
        assert isinstance(id_raw, str)
        id_str = id_raw

        return cls(
            id=id_str,
            path=path,
            name=name,
            created_at=created_at,
            updated_at=updated_at,
            session_id=session_id,
            metadata=metadata,
        )

    def save(self, path: Path) -> None:
        """Save state to file"""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: Path) -> "WorkspaceState":
        """Load state from file"""
        with open(path, encoding="utf-8") as f:
            return cls.from_dict(json.load(f))
