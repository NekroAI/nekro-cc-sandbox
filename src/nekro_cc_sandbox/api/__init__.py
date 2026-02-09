"""API module"""

from .events import router as events_router
from .messages import router as messages_router
from .settings import router as settings_router
from .shells import router as shells_router
from .status import router as status_router

__all__ = ["messages_router", "status_router", "events_router", "settings_router", "shells_router"]
