"""MCP (Model Context Protocol) extension support"""

from dataclasses import dataclass, field


@dataclass
class MCPExtension:
    """Manages MCP server connections for the workspace"""

    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)

    async def start(self) -> bool:
        """Start the MCP server"""
        return True

    async def stop(self) -> None:
        """Stop the MCP server"""
        pass

    async def health_check(self) -> bool:
        """Check if MCP server is healthy"""
        return True


class MCPManager:
    """Manages multiple MCP extensions"""

    def __init__(self) -> None:
        self._servers: dict[str, MCPExtension] = {}

    def add_server(
        self,
        name: str,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> MCPExtension:
        """Add an MCP server"""
        server = MCPExtension(
            name=name,
            command=command,
            args=args or [],
            env=env or {},
        )
        self._servers[name] = server
        return server

    async def start_all(self) -> None:
        """Start all configured MCP servers"""
        for server in self._servers.values():
            await server.start()

    async def stop_all(self) -> None:
        """Stop all MCP servers"""
        for server in self._servers.values():
            await server.stop()
