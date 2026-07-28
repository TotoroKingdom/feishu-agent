import re
from collections.abc import Awaitable, Callable, Mapping
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from app.core.config import Settings
from app.observability.context import request_id_context
from app.observability.logging import configure_json_logging

RequestCheck = Callable[[], bool]
REQUEST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def create_app(
    readiness_checks: Mapping[str, RequestCheck] | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    configure_json_logging()
    application = FastAPI(title="Feishu Project Weekly Agent", version="0.1.0")
    application.state.settings = settings or Settings()
    application.state.readiness_checks = dict(readiness_checks or {})

    @application.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        candidate = request.headers.get("X-Request-ID", "")
        request_id = candidate if REQUEST_ID.fullmatch(candidate) else f"req_{uuid4().hex}"
        token = request_id_context.set(request_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            request_id_context.reset(token)

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/ready", response_model=None)
    def ready() -> JSONResponse | dict[str, str]:
        for check in application.state.readiness_checks.values():
            try:
                if not check():
                    return JSONResponse(
                        status_code=503,
                        content={
                            "error": {
                                "code": "DEPENDENCY_UNAVAILABLE",
                                "message": "Service is not ready",
                            }
                        },
                    )
            except Exception:
                return JSONResponse(
                    status_code=503,
                    content={
                        "error": {
                            "code": "DEPENDENCY_UNAVAILABLE",
                            "message": "Service is not ready",
                        }
                    },
                )
        return {"status": "ok"}

    return application


app = create_app()
