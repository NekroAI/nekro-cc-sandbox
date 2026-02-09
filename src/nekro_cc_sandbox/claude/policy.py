"""Runtime policy and permissions management"""

from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class RuntimePolicy:
    """
    Defines what capabilities Claude Code can use in this workspace.

    Sandbox controls WHAT tools are available, not HOW they're used.
    """

    # Tool whitelist/blacklist
    allowed_tools: set[str] = field(default_factory=set)
    blocked_tools: set[str] = field(default_factory=set)

    # Capability flags
    allow_network: bool = True
    allow_file_modification: bool = True
    allow_command_execution: bool = True

    # MCP servers
    enabled_mcp_servers: list[str] = field(default_factory=list)

    # Custom tool evaluator - Callable[[str], bool] takes a tool name and returns bool
    tool_evaluator: Callable[[str], bool] | None = None

    def can_use_tool(self, tool_name: str) -> bool:
        """Check if a tool is allowed"""
        if self.blocked_tools and tool_name in self.blocked_tools:
            return False

        if self.allowed_tools and tool_name not in self.allowed_tools:
            return False

        return True

    @classmethod
    def relaxed(cls) -> "RuntimePolicy":
        """Permissive policy for development"""
        return cls(
            allowed_tools=set(),
            blocked_tools=set(),
            allow_network=True,
            allow_file_modification=True,
            allow_command_execution=True,
        )

    @classmethod
    def strict(cls) -> "RuntimePolicy":
        """Restrictive policy for production"""
        return cls(
            allowed_tools={
                "Read",
                "Glob",
                "Grep",
            },
            blocked_tools={
                "Bash",
                "Write",
                "Edit",
                "Task",
            },
            allow_network=False,
            allow_file_modification=False,
            allow_command_execution=False,
        )

    @classmethod
    def agent(cls) -> "RuntimePolicy":
        """面向“非交互自动运行”的对外沙盒 Agent 策略。"""
        return cls(
            # 明确白名单：避免把“交互型工具”带入导致卡住
            allowed_tools={
                "Read",
                "Glob",
                "Grep",
                "Write",
                "Edit",
                "Bash",
                "Task",
                "WebFetch",
                "WebSearch",
            },
            # 交互型/只在交互 UI 里才有意义的工具，默认全部禁用
            blocked_tools={
                "AskUserQuestion",
                "EnterPlanMode",
                "ExitPlanMode",
                "Skill",
                "TaskOutput",
                "TaskStop",
                "ToolSearch",
                "TodoWrite",
                "NotebookEdit",
            },
            allow_network=True,
            allow_file_modification=True,
            allow_command_execution=True,
        )
