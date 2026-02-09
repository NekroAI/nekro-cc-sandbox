import asyncio
import sys
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--enable-provider-tests",
        action="store_true",
        default=False,
        help="Enable real provider tests (marked with: @pytest.mark.provider).",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip real provider tests unless explicitly enabled.

    Rationale:
    - Provider tests require real API credentials and may make network calls.
    - `poe check` must be deterministic and pass without secrets by default.
    """
    if config.getoption("--enable-provider-tests"):
        return

    skip_marker = pytest.mark.skip(reason="Provider tests disabled (pass --enable-provider-tests to run).")
    for item in items:
        if "provider" in item.keywords:
            item.add_marker(skip_marker)


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop]:
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_workspace() -> Generator[Path]:
    """Create a temporary workspace directory"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_claude_session():
    """Mock Claude Code session"""
    return {
        "session_id": "test-session-123",
        "workspace_id": "default",
        "is_active": True,
    }


@pytest.fixture
def sample_message():
    """Sample message for testing"""
    return {
        "role": "user",
        "content": "Analyze the codebase and suggest improvements",
        "workspace_id": "default",
    }


@pytest.fixture
def env_vars():
    """Test environment variables"""
    return {
        "ANTHROPIC_AUTH_TOKEN": "test-token",
        "ANTHROPIC_BASE_URL": "https://api.anthropic.com",
        "WORKSPACE_ROOT": "./workspaces",
        "SKIP_PERMISSIONS": "true",
        "DEBUG": "true",
    }


@pytest.fixture
def mock_policy():
    """Create a mock runtime policy"""
    from nekro_cc_sandbox.claude.policy import RuntimePolicy

    return RuntimePolicy.relaxed()
