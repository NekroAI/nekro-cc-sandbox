"""Unit tests for runtime policy"""

from nekro_cc_sandbox.claude.policy import RuntimePolicy


class TestRuntimePolicy:
    """Tests for RuntimePolicy class"""

    def test_relaxed_policy_allows_all(self):
        """Test that relaxed policy allows all tools"""
        policy = RuntimePolicy.relaxed()

        assert policy.can_use_tool("Bash") is True
        assert policy.can_use_tool("Write") is True
        assert policy.can_use_tool("Task") is True
        assert policy.can_use_tool("Read") is True

    def test_strict_policy_blocks_commands(self):
        """Test that strict policy blocks dangerous tools"""
        policy = RuntimePolicy.strict()

        assert policy.can_use_tool("Bash") is False
        assert policy.can_use_tool("Write") is False
        assert policy.can_use_tool("Edit") is False
        assert policy.can_use_tool("Task") is False

    def test_strict_policy_allows_read_only(self):
        """Test that strict policy allows read operations"""
        policy = RuntimePolicy.strict()

        assert policy.can_use_tool("Read") is True
        assert policy.can_use_tool("Glob") is True
        assert policy.can_use_tool("Grep") is True

    def test_custom_blocked_tools(self):
        """Test policy with custom blocked tools"""
        policy = RuntimePolicy(
            blocked_tools={"Delete", "Exec"},
        )

        assert policy.can_use_tool("Delete") is False
        assert policy.can_use_tool("Exec") is False
        assert policy.can_use_tool("Read") is True

    def test_custom_allowed_tools(self):
        """Test policy with custom allowed tools"""
        policy = RuntimePolicy(
            allowed_tools={"Read", "Glob"},
            blocked_tools=set(),
        )

        assert policy.can_use_tool("Read") is True
        assert policy.can_use_tool("Glob") is True
        assert policy.can_use_tool("Grep") is False
