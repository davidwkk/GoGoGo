from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger

from app.api.routes import auth, chat, chat_sessions, health, trips, users
from app.core.logging import setup_logging
from app.core.middleware import setup_middleware

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    yield


app = FastAPI(title="gogogo", version="0.1.0", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    logger.bind(
        event="validation_error", path=request.url.path, errors=exc.errors()
    ).error(f"Validation error on {request.method} {request.url.path}: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()},
    )


setup_middleware(app)

app.include_router(health.router, prefix="/api/v1/health", tags=["health"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["chat"])
app.include_router(chat_sessions.router, prefix="/api/v1/chat", tags=["chat-sessions"])
app.include_router(trips.router, prefix="/api/v1/trips", tags=["trips"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
