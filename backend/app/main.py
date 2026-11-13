import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.exceptions import HTTPException

from app.api import analyses, auth, cases, conversations, files
from app.config import Settings, get_settings
from app.db import Database
from app.services.ai import AI
from app.services.storage import Storage

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None):
  settings = settings or get_settings()

  @asynccontextmanager
  async def lifespan(app):
    app.state.settings = settings
    app.state.db = Database(settings)
    app.state.ai = AI(settings)
    app.state.storage = Storage(settings)
    try:
      await app.state.db.connect()
      async with app.state.db.engine.connect() as conn:
        version = (await conn.execute(text("SELECT version_num FROM public.alembic_version"))).scalar_one()
        if version != "0004":
          raise RuntimeError("数据库迁移版本不匹配，请运行 alembic upgrade head")
      yield
    finally:
      await app.state.ai.close()
      await app.state.db.close()

  app = FastAPI(title="律法 AI 后端", version="0.1.0", lifespan=lifespan,
    description="一期：PostgreSQL 显式 RAG、私有文档解析与 DeepSeek 流式问答。外部服务缺失时不会回退 Mock。")
  app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"], expose_headers=["X-Request-ID"])

  @app.middleware("http")
  async def request_context(request: Request, call_next):
    request.state.request_id = uuid.uuid4().hex
    started = time.monotonic()
    try:
      response = await call_next(request)
    except Exception as error:
      response = await unexpected_error(request, error)
    response.headers["X-Request-ID"] = request.state.request_id
    logger.info("request id=%s method=%s status=%s latency_ms=%d", request.state.request_id,
      request.method, response.status_code, int((time.monotonic() - started) * 1000))
    return response

  @app.exception_handler(HTTPException)
  async def http_error(request: Request, error: HTTPException):
    detail = error.detail if isinstance(error.detail, dict) else {"code": "http_error", "message": str(error.detail)}
    return JSONResponse({"error": detail, "request_id": getattr(request.state, "request_id", None)}, status_code=error.status_code, headers=error.headers)

  @app.exception_handler(RequestValidationError)
  async def validation_error(request: Request, error: RequestValidationError):
    # Pydantic's raw errors contain original input, possibly credentials or case text.
    return JSONResponse({"error": {"code": "validation_error", "message": "请求参数不符合要求",
      "fields": [{"loc": list(e["loc"]), "type": e["type"]} for e in error.errors()]},
      "request_id": getattr(request.state, "request_id", None)}, status_code=422)

  @app.exception_handler(Exception)
  async def unexpected_error(request: Request, error: Exception):
    logger.error("request_failed id=%s type=%s", getattr(request.state, "request_id", None), type(error).__name__)
    return JSONResponse({"error": {"code": "internal_error", "message": "服务暂不可用"},
      "request_id": getattr(request.state, "request_id", None)}, status_code=500)

  @app.get("/health/live", tags=["health"])
  async def live():
    return {"status": "ok"}

  @app.get("/health/ready", tags=["health"])
  async def ready(request: Request):
    async with request.app.state.db.engine.connect() as conn:
      await conn.execute(text("SELECT 1"))
    return {"status": "ok", "database": "postgresql", "ai_configured": bool(settings.deepseek_api_key.get_secret_value()),
      "embedding_configured": bool(settings.embedding_api_key.get_secret_value())}

  for router, tag in [(auth.router, "auth"), (cases.router, "cases"),
                       (files.router, "files"), (conversations.router, "conversations"), (analyses.router, "analyses")]:
    app.include_router(router, prefix="/api/v1", tags=[tag])
  return app


app = create_app()
