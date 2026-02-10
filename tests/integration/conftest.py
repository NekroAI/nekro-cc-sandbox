import pytest
from fastapi import FastAPI

from nekro_cc_sandbox.api import events_router, messages_router, settings_router, shells_router, status_router
from nekro_cc_sandbox.api.schemas import HealthResponse


@pytest.fixture
def test_app() -> FastAPI:
    """Create a lightweight test app without production lifespan or middleware."""
    app = FastAPI()

    app.include_router(messages_router, prefix="/api/v1")
    app.include_router(status_router, prefix="/api/v1")
    app.include_router(events_router, prefix="/api/v1")
    app.include_router(settings_router, prefix="/api/v1")
    app.include_router(shells_router, prefix="/api/v1")

    @app.get("/health", response_model=HealthResponse)
    async def health_check() -> HealthResponse:
        return HealthResponse(version="0.1.0")

    return app
