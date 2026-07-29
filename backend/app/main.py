import re
from collections.abc import Awaitable, Callable, Mapping
from datetime import date
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.admin.run_detail import RunDetailNotFoundError, RunDetailService
from app.db.models import Project
from app.domain.runs import RunCreationService
from app.observability.context import request_id_context
from app.observability.logging import configure_json_logging

RequestCheck = Callable[[], bool]
SessionFactory = Callable[[], Session]
REQUEST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class RunCreateRequest(BaseModel):
    project_id: str
    period_key: str
    period_start: date
    period_end: date


class RunCreateResponse(BaseModel):
    run_id: str
    project_id: str
    period_key: str
    status: str


def create_app(
    readiness_checks: Mapping[str, RequestCheck] | None = None,
    settings: Settings | None = None,
    session_factory: SessionFactory | None = None,
) -> FastAPI:
    configure_json_logging()
    application = FastAPI(title="Feishu Project Weekly Agent", version="0.1.0")
    application.state.settings = settings or Settings()
    application.state.readiness_checks = dict(readiness_checks or {})
    application.state.session_factory = session_factory

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

    @application.post("/internal/v1/runs", response_model=RunCreateResponse, status_code=201)
    def create_internal_run(payload: RunCreateRequest) -> RunCreateResponse:
        if application.state.settings.app_profile != "local-demo":
            raise HTTPException(status_code=404, detail="Not found")
        factory = application.state.session_factory
        if factory is None:
            engine = create_engine(application.state.settings.database_url)
            factory = sessionmaker(engine, class_=Session, expire_on_commit=False)
        with factory() as session:
            if session.get(Project, payload.project_id) is None:
                raise HTTPException(status_code=404, detail="Project not found")
            run = RunCreationService(session).create_run(
                payload.project_id,
                payload.period_key,
                payload.period_start,
                payload.period_end,
            )
            session.commit()
            return RunCreateResponse(
                run_id=run.id,
                project_id=run.project_id,
                period_key=run.period_key,
                status=run.status,
            )

    @application.get("/api/v1/admin/runs/{run_id}")
    def get_admin_run_detail(run_id: str) -> JSONResponse:
        factory = _session_factory(application)
        request_id = request_id_context.get()
        try:
            envelope = RunDetailService(factory).load(run_id, request_id=request_id)
        except RunDetailNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return JSONResponse(content=envelope.model_dump(mode="json"))

    return application


app = create_app()


def _session_factory(application: FastAPI) -> SessionFactory:
    factory = application.state.session_factory
    if factory is not None:
        return factory
    engine = create_engine(application.state.settings.database_url)
    return sessionmaker(engine, class_=Session, expire_on_commit=False)
