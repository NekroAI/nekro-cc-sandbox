"""FastAPI 入口：nekro-cc-sandbox。"""

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from .api import events_router, messages_router, settings_router, shells_router, status_router
from .api.schemas import ErrorInfo, ErrorResponse, HealthResponse
from .claude import ClaudeRuntime, RuntimePolicy
from .enums import RuntimePolicyMode
from .errors import AppError, ErrorCode, new_err_id
from .settings import Settings
from .shell import ShellManager
from .workspace import WorkspaceManager

# 日志配置
LOG_DIR = Path("./data/logs")


def setup_logging():
    """配置 loguru 日志"""
    # 创建 logs 目录
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # 移除默认的控制台处理器
    logger.remove()

    # 添加文件处理器
    log_file = LOG_DIR / "app.log"
    logger.add(
        str(log_file),
        rotation="10 MB",           # 文件达到 10MB 时截断
        retention=10,               # 保留 10 个归档文件
        compression="gz",           # gzip 压缩
        encoding="utf-8",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss,SSS} [{level}] {message}",
    )

    # 添加控制台处理器
    logger.add(
        sys.stderr,
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} [{level}] {message}",
    )


setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    logger.info("Starting nekro-cc-sandbox...")

    # Startup
    workspace_root = Path(os.getenv("WORKSPACE_ROOT", "./workspaces"))
    app.state.workspace_manager = WorkspaceManager(workspace_root)

    # Initialize default workspace
    await app.state.workspace_manager.create_default_workspace()

    # Load settings
    settings_path = Path(os.getenv("SETTINGS_PATH", "./data/settings.json"))
    app.state.settings = Settings.load(settings_path)

    # Get env overrides from settings
    env_overrides = app.state.settings.get_env_vars()

    # Initialize Claude Code runtime
    # 产品默认：对外提供“非交互自动运行”的沙盒 agent
    policy_mode_raw = os.getenv("RUNTIME_POLICY", RuntimePolicyMode.AGENT.value).lower().strip()
    if policy_mode_raw == RuntimePolicyMode.STRICT.value:
        policy = RuntimePolicy.strict()
    elif policy_mode_raw == RuntimePolicyMode.AGENT.value:
        policy = RuntimePolicy.agent()
    elif policy_mode_raw == RuntimePolicyMode.RELAXED.value:
        policy = RuntimePolicy.relaxed()
    else:
        logger.warning(f"Unknown RUNTIME_POLICY={policy_mode_raw!r}; falling back to relaxed")
        policy = RuntimePolicy.relaxed()

    app.state.claude_runtime = ClaudeRuntime(
        workspace_manager=app.state.workspace_manager,
        skip_permissions=os.getenv("SKIP_PERMISSIONS", "false").lower() == "true",
        env_overrides=env_overrides,
        policy=policy,
    )

    # Interactive shell manager (PTY-backed)
    app.state.shell_manager = ShellManager()

    logger.success("nekro-cc-sandbox started successfully")

    yield

    # Shutdown
    logger.info("Shutting down nekro-cc-sandbox...")
    await app.state.shell_manager.close_all()
    await app.state.claude_runtime.shutdown()
    logger.success("Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="nekro-cc-sandbox",
    description="A Persistent Workspace Agent powered by Claude Code",
    version="0.1.0",
    lifespan=lifespan,
)

# 统一异常处理（避免中间件返回“无 schema dict”）
@app.exception_handler(AppError)
async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
    """将 AppError 转换为稳定的错误协议。"""
    err_id = exc.err_id or new_err_id()
    status_code = {
        ErrorCode.WORKSPACE_NOT_FOUND: 404,
        ErrorCode.RUNTIME_UNAVAILABLE: 503,
    }.get(exc.code, 500)
    payload = ErrorResponse(
        error=ErrorInfo(
            err_id=err_id,
            code=exc.code,
            message=exc.message,
            retryable=exc.retryable,
            details=exc.details,
        )
    )
    logger.error(f"[error] err_id={err_id} code={exc.code} status={status_code} message={exc.message}")
    return JSONResponse(status_code=status_code, content=payload.model_dump())


@app.exception_handler(Exception)
async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
    """兜底异常：返回 INTERNAL_ERROR，附带 err_id 便于日志检索。"""
    err_id = new_err_id()
    payload = ErrorResponse(
        error=ErrorInfo(
            err_id=err_id,
            code=ErrorCode.INTERNAL_ERROR,
            message=str(exc),
            retryable=True,
        )
    )
    logger.exception(f"[error] err_id={err_id} code=INTERNAL_ERROR message={exc}")
    return JSONResponse(status_code=500, content=payload.model_dump())

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """记录所有请求"""
    logger.info(f"→ {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"← {request.method} {request.url.path} - {response.status_code}")
    return response


# Include API routers FIRST (before catch-all frontend route)
app.include_router(messages_router, prefix="/api/v1")
app.include_router(status_router, prefix="/api/v1")
app.include_router(events_router, prefix="/api/v1")
app.include_router(settings_router, prefix="/api/v1")
app.include_router(shells_router, prefix="/api/v1")


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """健康检查接口。"""
    return HealthResponse(version="0.1.0")


# Mount frontend if exists (catch-all route must be last)
frontend_path = Path(__file__).parent.parent.parent / "frontend" / "dist"
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")

    @app.get("/{path:path}")
    async def serve_frontend(path: str):
        from fastapi.responses import FileResponse

        # Empty path means root "/"
        if not path:
            index_path = frontend_path / "index.html"
            if index_path.exists():
                return FileResponse(index_path)
            return {"error": "Frontend not built", "hint": "Run 'poe frontend-build'"}

        file_path = frontend_path / path
        if file_path.is_file():
            return FileResponse(file_path)

        index_path = frontend_path / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        return {"error": "Frontend not built", "hint": "Run 'poe frontend-build'"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "nekro_cc_sandbox.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "7021")),
        reload=os.getenv("DEBUG", "false").lower() == "true",
    )
