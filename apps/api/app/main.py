from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import config, consent, events, health, participants, session, signal
from app.config import get_settings
from app.core.exceptions import ApiError


def create_app() -> FastAPI:
    settings = get_settings()
    settings.validate_deployment_security()
    app = FastAPI(title="CalibrAI API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.middleware("http")
    async def request_size_limit(request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                body_size = int(content_length)
            except ValueError:
                return JSONResponse(status_code=400, content={"detail": "Invalid Content-Length header"})
            if body_size > settings.max_request_bytes:
                return JSONResponse(status_code=413, content={"detail": "Request body too large"})
        return await call_next(request)

    @app.exception_handler(ApiError)
    async def api_error_handler(_: Request, error: ApiError):
        return JSONResponse(status_code=error.status_code, content={"detail": error.detail})

    app.include_router(health.router)
    app.include_router(signal.router)
    app.include_router(events.router)
    app.include_router(consent.router)
    app.include_router(config.router)
    app.include_router(participants.router)
    app.include_router(session.router)
    return app


app = create_app()
