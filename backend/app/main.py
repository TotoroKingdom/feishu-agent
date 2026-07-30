import re
from collections.abc import Awaitable, Callable, Mapping
from datetime import date
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.admin.run_detail import RunDetailNotFoundError, RunDetailService
from app.agent.runtime import WorkflowRuntime
from app.admin.configuration import (
    AdminConfigurationService,
    ConfigurationNotFoundError,
    FeishuFieldMappingsRequest,
    FeishuResourceCreateRequest,
    FeishuResourceUpdateRequest,
    FeishuSchemaRequest,
    ModelConfigUpdateRequest,
    PromptVersionCreateRequest,
    ProjectUpdateRequest,
    RepositoryCreateRequest,
    RepositoryUpdateRequest,
    RevisionConflictError,
)
from app.core.config import Settings
from app.db.models import Project
from app.domain.runs import RunCreationService
from app.observability.context import request_id_context
from app.observability.logging import configure_json_logging
from app.providers.feishu import (
    FeishuAuthError,
    FeishuCallbackConflictError,
    FeishuCallbackService,
    FeishuCallbackValidationError,
    FeishuCardActionRequest,
    FeishuEventRequest,
)

RequestCheck = Callable[[], bool]
SessionFactory = Callable[[], Session]
REQUEST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
FEISHU_VERIFICATION_HEADER = "X-Feishu-Verification-Token"


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


class RunCancelRequest(BaseModel):
    reason: str
    expected_status: str | None = None


class RunSafeRetryRequest(BaseModel):
    reason: str
    expected_status: str | None = None


def create_app(
    readiness_checks: Mapping[str, RequestCheck] | None = None,
    settings: Settings | None = None,
    session_factory: SessionFactory | None = None,
    workflow_runtime: WorkflowRuntime | None = None,
) -> FastAPI:
    configure_json_logging()
    application = FastAPI(title="Feishu Project Weekly Agent", version="0.1.0")
    application.state.settings = settings or Settings()
    application.state.readiness_checks = dict(readiness_checks or {})
    application.state.session_factory = session_factory
    application.state.workflow_runtime = workflow_runtime
    application.state.feishu_callback_service = None

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

    @application.post("/api/v1/admin/runs/{run_id}/cancel", status_code=202)
    def cancel_admin_run(run_id: str, payload: RunCancelRequest) -> JSONResponse:
        runtime = _workflow_runtime(application)
        try:
            result = runtime.cancel_run(
                run_id,
                reason=payload.reason,
                expected_status=payload.expected_status,
            )
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return JSONResponse(content={"status": "accepted", "data": result}, status_code=202)

    @application.post("/api/v1/admin/runs/{run_id}/safe-retry", status_code=202)
    def safe_retry_admin_run(run_id: str, payload: RunSafeRetryRequest) -> JSONResponse:
        runtime = _workflow_runtime(application)
        try:
            result = runtime.safe_retry_run(
                run_id,
                reason=payload.reason,
                expected_status=payload.expected_status,
            )
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return JSONResponse(content={"status": "accepted", "data": result}, status_code=202)

    @application.get("/api/v1/admin/project")
    def get_admin_project() -> dict[str, object]:
        return {"data": _configuration_service(application).get_project()}

    @application.put("/api/v1/admin/project")
    def update_admin_project(payload: ProjectUpdateRequest) -> dict[str, object]:
        try:
            data = _configuration_service(application).update_project(payload)
        except RevisionConflictError as error:
            raise HTTPException(
                status_code=409,
                detail={"code": "REVISION_CONFLICT", "message": str(error)},
            ) from error
        except ConfigurationNotFoundError as error:
            raise HTTPException(
                status_code=404,
                detail={"code": "NOT_FOUND", "message": str(error)},
            ) from error
        return {"data": data}

    @application.get("/api/v1/admin/project/repositories")
    def list_admin_project_repositories() -> dict[str, object]:
        return {"data": _configuration_service(application).list_repositories()}

    @application.post("/api/v1/admin/project/repositories", status_code=201)
    def create_admin_project_repository(payload: RepositoryCreateRequest) -> dict[str, object]:
        try:
            data = _configuration_service(application).create_repository(payload)
        except ValueError as error:
            raise HTTPException(
                status_code=409,
                detail={"code": "CONFLICT", "message": str(error)},
            ) from error
        return {"data": data}

    @application.patch("/api/v1/admin/project/repositories/{repository_id}")
    def update_admin_project_repository(
        repository_id: str, payload: RepositoryUpdateRequest
    ) -> dict[str, object]:
        try:
            data = _configuration_service(application).update_repository(repository_id, payload)
        except RevisionConflictError as error:
            raise HTTPException(
                status_code=409,
                detail={"code": "REVISION_CONFLICT", "message": str(error)},
            ) from error
        except ConfigurationNotFoundError as error:
            raise HTTPException(
                status_code=404,
                detail={"code": "NOT_FOUND", "message": str(error)},
            ) from error
        return {"data": data}

    @application.delete("/api/v1/admin/project/repositories/{repository_id}")
    def delete_admin_project_repository(repository_id: str) -> dict[str, object]:
        try:
            data = _configuration_service(application).delete_repository(repository_id)
        except ConfigurationNotFoundError as error:
            raise HTTPException(
                status_code=404,
                detail={"code": "NOT_FOUND", "message": str(error)},
            ) from error
        return {"data": data}

    @application.post("/api/v1/admin/project/repositories/{repository_id}/connectivity-test")
    def test_admin_project_repository_connectivity(repository_id: str) -> dict[str, object]:
        try:
            data = _configuration_service(application).test_repository_connectivity(repository_id)
        except ConfigurationNotFoundError as error:
            raise HTTPException(
                status_code=404,
                detail={"code": "NOT_FOUND", "message": str(error)},
            ) from error
        return {"data": data}

    @application.get("/api/v1/admin/project/feishu-resources")
    def list_admin_feishu_resources() -> dict[str, object]:
        return {"data": _configuration_service(application).list_feishu_resources()}

    @application.post("/api/v1/admin/project/feishu-resources", status_code=201)
    def create_admin_feishu_resource(payload: FeishuResourceCreateRequest) -> dict[str, object]:
        try:
            data = _configuration_service(application).create_feishu_resource(payload)
        except ValueError as error:
            raise HTTPException(
                status_code=409,
                detail={"code": "CONFLICT", "message": str(error)},
            ) from error
        return {"data": data}

    @application.patch("/api/v1/admin/project/feishu-resources/{resource_id}")
    def update_admin_feishu_resource(
        resource_id: str, payload: FeishuResourceUpdateRequest
    ) -> dict[str, object]:
        try:
            data = _configuration_service(application).update_feishu_resource(resource_id, payload)
        except RevisionConflictError as error:
            raise HTTPException(
                status_code=409,
                detail={"code": "REVISION_CONFLICT", "message": str(error)},
            ) from error
        except ConfigurationNotFoundError as error:
            raise HTTPException(
                status_code=404,
                detail={"code": "NOT_FOUND", "message": str(error)},
            ) from error
        return {"data": data}

    @application.post("/api/v1/admin/project/feishu-resources/{resource_id}/schema")
    def update_admin_feishu_resource_schema(
        resource_id: str, payload: FeishuSchemaRequest
    ) -> dict[str, object]:
        try:
            data = _configuration_service(application).update_feishu_schema(resource_id, payload)
        except RevisionConflictError as error:
            raise HTTPException(
                status_code=409,
                detail={"code": "REVISION_CONFLICT", "message": str(error)},
            ) from error
        except ConfigurationNotFoundError as error:
            raise HTTPException(
                status_code=404,
                detail={"code": "NOT_FOUND", "message": str(error)},
            ) from error
        return {"data": data}

    @application.put("/api/v1/admin/project/feishu-resources/{resource_id}/field-mappings")
    def upsert_admin_feishu_field_mappings(
        resource_id: str, payload: FeishuFieldMappingsRequest
    ) -> dict[str, object]:
        try:
            data = _configuration_service(application).upsert_feishu_field_mappings(
                resource_id, payload
            )
        except RevisionConflictError as error:
            raise HTTPException(
                status_code=409,
                detail={"code": "REVISION_CONFLICT", "message": str(error)},
            ) from error
        except ConfigurationNotFoundError as error:
            raise HTTPException(
                status_code=404,
                detail={"code": "NOT_FOUND", "message": str(error)},
            ) from error
        return {"data": data}

    @application.post("/api/v1/admin/project/feishu-resources/{resource_id}/connectivity-test")
    def test_admin_feishu_resource_connectivity(resource_id: str) -> dict[str, object]:
        try:
            data = _configuration_service(application).test_feishu_connectivity(resource_id)
        except ConfigurationNotFoundError as error:
            raise HTTPException(
                status_code=404,
                detail={"code": "NOT_FOUND", "message": str(error)},
            ) from error
        return {"data": data}

    @application.get("/api/v1/admin/model-config")
    def get_admin_model_config() -> dict[str, object]:
        return {"data": _configuration_service(application).get_model_config()}

    @application.patch("/api/v1/admin/model-config")
    def patch_admin_model_config(payload: ModelConfigUpdateRequest) -> dict[str, object]:
        try:
            data = _configuration_service(application).patch_model_config(payload)
        except RevisionConflictError as error:
            raise HTTPException(
                status_code=409,
                detail={"code": "REVISION_CONFLICT", "message": str(error)},
            ) from error
        return {"data": data}

    @application.get("/api/v1/admin/prompts")
    def list_admin_prompts(type: str) -> dict[str, object]:
        return {"data": _configuration_service(application).list_prompts(type)}

    @application.post("/api/v1/admin/prompts", status_code=201)
    def create_admin_prompt(payload: PromptVersionCreateRequest) -> dict[str, object]:
        try:
            data = _configuration_service(application).create_prompt(payload)
        except ValueError as error:
            raise HTTPException(
                status_code=409,
                detail={"code": "CONFLICT", "message": str(error)},
            ) from error
        return {"data": data}

    @application.post("/api/v1/admin/prompts/{prompt_version_id}/activate")
    def activate_admin_prompt(prompt_version_id: str) -> dict[str, object]:
        try:
            data = _configuration_service(application).activate_prompt(prompt_version_id)
        except ConfigurationNotFoundError as error:
            raise HTTPException(
                status_code=404,
                detail={"code": "NOT_FOUND", "message": str(error)},
            ) from error
        return {"data": data}

    @application.post("/api/v1/admin/project/connectivity-test", status_code=202)
    def run_admin_connectivity_test() -> dict[str, object]:
        return {"data": _configuration_service(application).run_connectivity_job()}

    @application.get("/api/v1/admin/connectivity-jobs/{job_id}")
    def get_admin_connectivity_job(job_id: str) -> dict[str, object]:
        try:
            data = _configuration_service(application).get_async_job(job_id)
        except ConfigurationNotFoundError as error:
            raise HTTPException(
                status_code=404,
                detail={"code": "NOT_FOUND", "message": str(error)},
            ) from error
        return {"data": data}

    @application.post("/api/v1/feishu/events")
    def feishu_events(request: Request, payload: FeishuEventRequest) -> JSONResponse:
        service = _feishu_callback_service(application)
        token = _feishu_verification_token(request)
        try:
            result = service.handle_event(payload, verification_token=token)
        except FeishuCallbackValidationError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        except FeishuCallbackConflictError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except FeishuAuthError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        return JSONResponse(content=result)

    @application.post("/api/v1/feishu/card-actions")
    def feishu_card_actions(request: Request, payload: FeishuCardActionRequest) -> JSONResponse:
        service = _feishu_callback_service(application)
        token = _feishu_verification_token(request)
        try:
            result = service.handle_card_action(payload, verification_token=token)
        except FeishuCallbackValidationError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        except FeishuCallbackConflictError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except FeishuAuthError as error:
            raise HTTPException(status_code=403, detail=str(error)) from error
        return JSONResponse(content=result)

    return application


app = create_app()


def _session_factory(application: FastAPI) -> SessionFactory:
    factory = application.state.session_factory
    if factory is not None:
        return factory
    engine = create_engine(application.state.settings.database_url)
    return sessionmaker(engine, class_=Session, expire_on_commit=False)


def _feishu_callback_service(application: FastAPI) -> FeishuCallbackService:
    service = application.state.feishu_callback_service
    if service is None:

        def runtime_factory() -> WorkflowRuntime:
            return _workflow_runtime(application)

        service = FeishuCallbackService(
            _session_factory(application),
            application.state.settings,
            runtime_factory=runtime_factory,
        )
        application.state.feishu_callback_service = service
    return service


def _workflow_runtime(application: FastAPI) -> WorkflowRuntime:
    runtime = application.state.workflow_runtime
    if runtime is None:
        runtime = WorkflowRuntime(_session_factory(application), MemorySaver())
        application.state.workflow_runtime = runtime
    return runtime


def _configuration_service(application: FastAPI) -> AdminConfigurationService:
    return AdminConfigurationService(_session_factory(application), application.state.settings)


def _feishu_verification_token(request: Request) -> str | None:
    return (
        request.headers.get(FEISHU_VERIFICATION_HEADER)
        or request.headers.get("X-Lark-Verification-Token")
        or request.headers.get("X-Feishu-Token")
    )
