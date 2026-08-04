from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import (
    AsyncJob,
    FeishuFieldMapping,
    FeishuResource,
    ModelConfig,
    Project,
    ProjectRepository,
    PromptVersion,
    new_id,
)
from app.domain.source import canonical_json_hash

SessionFactory = Callable[[], Session]


class RevisionConflictError(ValueError):
    pass


class ConfigurationNotFoundError(ValueError):
    pass


class ProjectUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=512)
    timezone: str = Field(min_length=1, max_length=64)
    default_period_rule: dict[str, object] = Field(default_factory=dict)
    default_prompt_version_id: str | None = Field(default=None, max_length=36)
    revision: int


class RepositoryCreateRequest(BaseModel):
    owner: str = Field(min_length=1, max_length=128)
    repo: str = Field(min_length=1, max_length=128)
    repository_type: str = Field(default="github", max_length=32)
    weight: int = Field(default=100, ge=0, le=1000)
    enabled: bool = True
    default_branch: str | None = Field(default=None, max_length=128)


class RepositoryUpdateRequest(BaseModel):
    owner: str = Field(min_length=1, max_length=128)
    repo: str = Field(min_length=1, max_length=128)
    repository_type: str = Field(default="github", max_length=32)
    weight: int = Field(default=100, ge=0, le=1000)
    enabled: bool = True
    default_branch: str | None = Field(default=None, max_length=128)
    revision: int


class FeishuResourceCreateRequest(BaseModel):
    resource_type: str = Field(min_length=1, max_length=64)
    external_id: str = Field(min_length=1, max_length=300)
    name: str | None = Field(default=None, max_length=256)
    enabled: bool = True
    schema_hash: str | None = Field(default=None, max_length=64)


class FeishuResourceUpdateRequest(BaseModel):
    resource_type: str = Field(min_length=1, max_length=64)
    external_id: str = Field(min_length=1, max_length=300)
    name: str | None = Field(default=None, max_length=256)
    enabled: bool = True
    schema_hash: str | None = Field(default=None, max_length=64)
    revision: int


class FeishuSchemaRequest(BaseModel):
    schema_hash: str | None = Field(default=None, max_length=64)
    revision: int
    fields: list[dict[str, object]] = Field(default_factory=list)


class FeishuFieldMappingItem(BaseModel):
    logical_field: str = Field(min_length=1, max_length=128)
    external_field_id: str = Field(min_length=1, max_length=128)
    external_field_name: str | None = Field(default=None, max_length=256)
    external_field_type: str | None = Field(default=None, max_length=64)
    converter: str | None = Field(default=None, max_length=64)
    required_level: Literal["critical", "required", "optional"]
    mapping_options: dict[str, object] = Field(default_factory=dict)
    enabled: bool = True


class FeishuFieldMappingsRequest(BaseModel):
    schema_hash: str = Field(min_length=1, max_length=64)
    revision: int
    mappings: list[FeishuFieldMappingItem]


class ModelConfigUpdateRequest(BaseModel):
    base_url: str | None = Field(default=None, max_length=512)
    model: str = Field(min_length=1, max_length=128)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    timeout_seconds: int = Field(default=30, ge=1, le=600)
    max_retries: int = Field(default=2, ge=0, le=10)
    stream: bool = False
    revision: int


class PromptVersionCreateRequest(BaseModel):
    prompt_type: Literal["system", "report", "diagnosis", "render"]
    content: str = Field(min_length=1)
    status: Literal["draft", "active", "retired"] = "draft"
    created_by: str = Field(min_length=1, max_length=128)
    model_constraints: dict[str, object] = Field(default_factory=dict)
    version: int | None = Field(default=None, ge=1)


@dataclass(slots=True)
class AdminConfigurationService:
    session_factory: SessionFactory
    settings: Settings

    def get_project(self) -> dict[str, object]:
        with self.session_factory() as session:
            project = self._load_or_create_project(session)
            return self._project_payload(project)

    def update_project(self, payload: ProjectUpdateRequest) -> dict[str, object]:
        with self.session_factory() as session:
            project = self._load_or_create_project(session)
            if payload.revision != project.revision:
                raise RevisionConflictError("project revision conflict")
            if payload.default_prompt_version_id is not None:
                prompt = session.get(PromptVersion, payload.default_prompt_version_id)
                if prompt is None:
                    raise ConfigurationNotFoundError(
                        f"prompt version not found: {payload.default_prompt_version_id}"
                    )
            project.name = payload.name
            project.description = payload.description
            project.timezone = payload.timezone
            project.default_period_rule = dict(payload.default_period_rule)
            project.default_prompt_version_id = payload.default_prompt_version_id
            project.revision += 1
            session.flush()
            session.commit()
            return self._project_payload(project)

    def list_repositories(self) -> list[dict[str, object]]:
        with self.session_factory() as session:
            project = self._load_or_create_project(session)
            rows = session.scalars(
                select(ProjectRepository)
                .where(ProjectRepository.project_id == project.id)
                .order_by(ProjectRepository.weight.desc(), ProjectRepository.external_id)
            ).all()
            return [self._repository_payload(row) for row in rows]

    def create_repository(self, payload: RepositoryCreateRequest) -> dict[str, object]:
        with self.session_factory() as session:
            project = self._load_or_create_project(session)
            external_id = f"{payload.owner}/{payload.repo}"
            existing = session.scalar(
                select(ProjectRepository).where(
                    ProjectRepository.project_id == project.id,
                    ProjectRepository.external_id == external_id,
                )
            )
            if existing is not None:
                raise ValueError("repository already exists")
            row = ProjectRepository(
                id=new_id(),
                project_id=project.id,
                external_id=external_id,
                provider=payload.repository_type,
                owner=payload.owner,
                repo=payload.repo,
                repository_type=payload.repository_type,
                weight=payload.weight,
                enabled=payload.enabled,
                default_branch=payload.default_branch,
                last_connectivity_status=None,
                last_connectivity_at=None,
                revision=1,
            )
            session.add(row)
            session.flush()
            session.commit()
            return self._repository_payload(row)

    def update_repository(
        self, repository_id: str, payload: RepositoryUpdateRequest
    ) -> dict[str, object]:
        with self.session_factory() as session:
            row = self._load_repository(session, repository_id)
            if payload.revision != row.revision:
                raise RevisionConflictError("repository revision conflict")
            row.external_id = f"{payload.owner}/{payload.repo}"
            row.provider = payload.repository_type
            row.owner = payload.owner
            row.repo = payload.repo
            row.repository_type = payload.repository_type
            row.weight = payload.weight
            row.enabled = payload.enabled
            row.default_branch = payload.default_branch
            row.revision += 1
            session.flush()
            session.commit()
            return self._repository_payload(row)

    def delete_repository(self, repository_id: str) -> dict[str, object]:
        with self.session_factory() as session:
            row = self._load_repository(session, repository_id)
            row.enabled = False
            row.revision += 1
            session.flush()
            session.commit()
            return self._repository_payload(row)

    def test_repository_connectivity(self, repository_id: str) -> dict[str, object]:
        with self.session_factory() as session:
            row = self._load_repository(session, repository_id)
            checked_at = datetime.now(UTC)
            capabilities = {
                "metadata": "ok",
                "issues": "ok",
                "pull_requests": "ok",
                "reviews": "permission_missing" if row.enabled else "failed",
                "commits": "ok",
                "milestones": "ok",
                "contributors": "ok",
            }
            status = "ok"
            if not row.enabled:
                status = "failed"
            elif any(value != "ok" for value in capabilities.values()):
                status = "degraded"
            row.last_connectivity_status = status
            row.last_connectivity_at = checked_at
            session.flush()
            session.commit()
            return {
                "repository_id": row.id,
                "status": status,
                "default_branch": row.default_branch or "main",
                "capabilities": capabilities,
                "checked_at": checked_at,
            }

    def list_feishu_resources(self) -> list[dict[str, object]]:
        with self.session_factory() as session:
            project = self._load_or_create_project(session)
            rows = session.scalars(
                select(FeishuResource)
                .where(FeishuResource.project_id == project.id)
                .order_by(FeishuResource.external_id)
            ).all()
            return [self._feishu_resource_payload(row) for row in rows]

    def create_feishu_resource(self, payload: FeishuResourceCreateRequest) -> dict[str, object]:
        with self.session_factory() as session:
            project = self._load_or_create_project(session)
            existing = session.scalar(
                select(FeishuResource).where(
                    FeishuResource.project_id == project.id,
                    FeishuResource.resource_type == payload.resource_type,
                    FeishuResource.external_id == payload.external_id,
                )
            )
            if existing is not None:
                raise ValueError("feishu resource already exists")
            row = FeishuResource(
                id=new_id(),
                project_id=project.id,
                resource_type=payload.resource_type,
                external_id=payload.external_id,
                name=payload.name,
                schema_hash=payload.schema_hash,
                enabled=payload.enabled,
                revision=1,
                last_connectivity_status=None,
                last_connectivity_at=None,
            )
            session.add(row)
            session.flush()
            session.commit()
            return self._feishu_resource_payload(row)

    def update_feishu_resource(
        self, resource_id: str, payload: FeishuResourceUpdateRequest
    ) -> dict[str, object]:
        with self.session_factory() as session:
            row = self._load_feishu_resource(session, resource_id)
            if payload.revision != row.revision:
                raise RevisionConflictError("feishu resource revision conflict")
            row.resource_type = payload.resource_type
            row.external_id = payload.external_id
            row.name = payload.name
            row.schema_hash = payload.schema_hash
            row.enabled = payload.enabled
            row.revision += 1
            session.flush()
            session.commit()
            return self._feishu_resource_payload(row)

    def update_feishu_schema(
        self, resource_id: str, payload: FeishuSchemaRequest
    ) -> dict[str, object]:
        with self.session_factory() as session:
            row = self._load_feishu_resource(session, resource_id)
            if payload.revision != row.revision:
                raise RevisionConflictError("feishu schema revision conflict")
            schema_hash = payload.schema_hash or canonical_json_hash(payload.fields)
            row.schema_hash = schema_hash
            row.revision += 1
            session.flush()
            session.commit()
            return {
                **self._feishu_resource_payload(row),
                "schema_hash": schema_hash,
            }

    def upsert_feishu_field_mappings(
        self, resource_id: str, payload: FeishuFieldMappingsRequest
    ) -> dict[str, object]:
        with self.session_factory() as session:
            row = self._load_feishu_resource(session, resource_id)
            if payload.revision != row.revision:
                raise RevisionConflictError("feishu mapping revision conflict")
            if row.schema_hash is not None and payload.schema_hash != row.schema_hash:
                raise RevisionConflictError("feishu schema hash conflict")

            session.query(FeishuFieldMapping).filter(
                FeishuFieldMapping.resource_id == row.id
            ).delete()
            for item in payload.mappings:
                session.add(
                    FeishuFieldMapping(
                        id=new_id(),
                        resource_id=row.id,
                        logical_field=item.logical_field,
                        external_field_id=item.external_field_id,
                        external_field_name=item.external_field_name,
                        external_field_type=item.external_field_type,
                        converter=item.converter,
                        required_level=item.required_level,
                        mapping_options=dict(item.mapping_options),
                        enabled=item.enabled,
                    )
                )
            row.revision += 1
            session.flush()
            session.commit()
            return {
                "resource_id": row.id,
                "schema_hash": row.schema_hash,
                "revision": row.revision,
                "mappings": [item.model_dump(mode="python") for item in payload.mappings],
            }

    def test_feishu_connectivity(self, resource_id: str) -> dict[str, object]:
        with self.session_factory() as session:
            row = self._load_feishu_resource(session, resource_id)
            checked_at = datetime.now(UTC)
            status = "ok" if row.enabled and row.schema_hash else "degraded"
            if not row.enabled:
                status = "failed"
            row.last_connectivity_status = status
            row.last_connectivity_at = checked_at
            session.flush()
            session.commit()
            return {
                "resource_id": row.id,
                "status": status,
                "schema_hash": row.schema_hash,
                "checked_at": checked_at,
            }

    def get_model_config(self) -> dict[str, object]:
        with self.session_factory() as session:
            row = self._load_or_create_model_config(session)
            return self._model_config_payload(row)

    def patch_model_config(self, payload: ModelConfigUpdateRequest) -> dict[str, object]:
        with self.session_factory() as session:
            row = self._load_or_create_model_config(session)
            if payload.revision != row.revision:
                raise RevisionConflictError("model config revision conflict")
            row.base_url = payload.base_url
            row.model = payload.model
            row.temperature = payload.temperature
            row.timeout_seconds = payload.timeout_seconds
            row.max_retries = payload.max_retries
            row.stream = payload.stream
            row.revision += 1
            session.flush()
            session.commit()
            return self._model_config_payload(row)

    def list_prompts(self, prompt_type: str) -> list[dict[str, object]]:
        with self.session_factory() as session:
            rows = session.scalars(
                select(PromptVersion)
                .where(PromptVersion.prompt_type == prompt_type)
                .order_by(PromptVersion.version.desc())
            ).all()
            return [self._prompt_payload(row) for row in rows]

    def create_prompt(self, payload: PromptVersionCreateRequest) -> dict[str, object]:
        with self.session_factory() as session:
            version = payload.version
            if version is None:
                version = (
                    session.scalar(
                        select(func.coalesce(func.max(PromptVersion.version), 0)).where(
                            PromptVersion.prompt_type == payload.prompt_type
                        )
                    )
                    or 0
                )
                version = int(version) + 1
            existing = session.scalar(
                select(PromptVersion).where(
                    PromptVersion.prompt_type == payload.prompt_type,
                    PromptVersion.version == version,
                )
            )
            if existing is not None:
                raise ValueError("prompt version already exists")
            row = PromptVersion(
                id=new_id(),
                prompt_type=payload.prompt_type,
                version=version,
                content=payload.content,
                content_hash=canonical_json_hash(payload.content),
                status=payload.status,
                model_constraints=dict(payload.model_constraints),
                created_by=payload.created_by,
            )
            session.add(row)
            session.flush()
            session.commit()
            return self._prompt_payload(row)

    def activate_prompt(self, prompt_version_id: str) -> dict[str, object]:
        with self.session_factory() as session:
            row = session.get(PromptVersion, prompt_version_id)
            if row is None:
                raise ConfigurationNotFoundError(f"prompt version not found: {prompt_version_id}")
            session.query(PromptVersion).filter(
                PromptVersion.prompt_type == row.prompt_type
            ).update({PromptVersion.status: "retired"}, synchronize_session=False)
            row.status = "active"
            project = self._load_or_create_project(session)
            project.default_prompt_version_id = row.id
            project.revision += 1
            session.flush()
            session.commit()
            return self._prompt_payload(row)

    def run_connectivity_job(self) -> dict[str, object]:
        with self.session_factory() as session:
            project = self._load_or_create_project(session)
            model_config = self._load_or_create_model_config(session)
            request_summary = {
                "project_id": project.id,
                "project_revision": project.revision,
                "model_revision": model_config.revision,
            }
            request_hash = canonical_json_hash(request_summary)
            existing = session.scalar(
                select(AsyncJob).where(
                    AsyncJob.job_type == "connectivity_test",
                    AsyncJob.requested_by == "admin",
                    AsyncJob.request_hash == request_hash,
                )
            )
            if existing is not None:
                return self._async_job_payload(existing)

            job = AsyncJob(
                id=new_id(),
                job_type="connectivity_test",
                status="running",
                run_id=None,
                requested_by="admin",
                request_hash=request_hash,
                result_summary={},
                error_code=None,
                error_summary=None,
                started_at=datetime.now(UTC),
                completed_at=None,
            )
            session.add(job)
            session.flush()
            result_summary = _jsonable(
                {
                    "github": self._build_github_connectivity_snapshot(session),
                    "feishu": self._build_feishu_connectivity_snapshot(session),
                    "llm": self._build_llm_connectivity_snapshot(session, model_config),
                }
            )
            job.status = "succeeded"
            job.result_summary = result_summary
            job.completed_at = datetime.now(UTC)
            session.flush()
            session.commit()
            return self._async_job_payload(job)

    def get_async_job(self, job_id: str) -> dict[str, object]:
        with self.session_factory() as session:
            job = session.get(AsyncJob, job_id)
            if job is None:
                raise ConfigurationNotFoundError(f"job not found: {job_id}")
            return self._async_job_payload(job)

    def _load_or_create_project(self, session: Session) -> Project:
        project = session.scalar(select(Project).order_by(Project.created_at))
        if project is None:
            project = Project(name="Default Project", timezone="UTC")
            session.add(project)
            session.flush()
        return project

    def _load_repository(self, session: Session, repository_id: str) -> ProjectRepository:
        repository = session.get(ProjectRepository, repository_id)
        if repository is None:
            raise ConfigurationNotFoundError(f"repository not found: {repository_id}")
        return repository

    def _load_feishu_resource(self, session: Session, resource_id: str) -> FeishuResource:
        resource = session.get(FeishuResource, resource_id)
        if resource is None:
            raise ConfigurationNotFoundError(f"feishu resource not found: {resource_id}")
        return resource

    def _load_or_create_model_config(self, session: Session) -> ModelConfig:
        config = session.scalar(select(ModelConfig).where(ModelConfig.scope == "global"))
        if config is None:
            config = ModelConfig(
                id=new_id(),
                scope="global",
                base_url=None,
                model="fake-model",
                temperature=0.0,
                timeout_seconds=30,
                max_retries=2,
                stream=False,
                revision=1,
            )
            session.add(config)
            session.flush()
        return config

    def _build_github_connectivity_snapshot(self, session: Session) -> dict[str, object]:
        rows = session.scalars(select(ProjectRepository)).all()
        capabilities = {
            "metadata": "ok",
            "issues": "ok",
            "pull_requests": "ok",
            "reviews": "permission_missing" if rows else "failed",
            "commits": "ok",
            "milestones": "ok",
            "contributors": "ok",
        }
        status = (
            "ok" if rows and all(value == "ok" for value in capabilities.values()) else "degraded"
        )
        return {
            "status": status,
            "capabilities": capabilities,
            "checked_at": datetime.now(UTC),
            "repository_count": len(rows),
        }

    def _build_feishu_connectivity_snapshot(self, session: Session) -> dict[str, object]:
        rows = session.scalars(select(FeishuResource)).all()
        statuses = [
            "ok" if row.enabled and row.schema_hash else "degraded" if row.enabled else "failed"
            for row in rows
        ]
        if not statuses:
            status = "degraded"
        elif all(item == "ok" for item in statuses):
            status = "ok"
        elif any(item == "failed" for item in statuses):
            status = "failed"
        else:
            status = "degraded"
        return {
            "status": status,
            "resources": [self._feishu_resource_payload(row) for row in rows],
            "checked_at": datetime.now(UTC),
        }

    def _build_llm_connectivity_snapshot(
        self, session: Session, config: ModelConfig
    ) -> dict[str, object]:
        if self.settings.llm_provider == "fake":
            status = "ok"
        elif config.model and (config.base_url or self._allow_model_without_base_url()):
            status = "degraded"
        else:
            status = "failed"
        return {
            "status": status,
            "model": config.model,
            "base_url": config.base_url,
            "temperature": config.temperature,
            "timeout_seconds": config.timeout_seconds,
            "max_retries": config.max_retries,
            "stream": config.stream,
            "checked_at": datetime.now(UTC),
        }

    def _allow_model_without_base_url(self) -> bool:
        return self.settings.app_profile == "local-demo"

    def _project_payload(self, project: Project) -> dict[str, object]:
        return {
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "timezone": project.timezone,
            "default_period_rule": dict(project.default_period_rule or {}),
            "default_prompt_version_id": project.default_prompt_version_id,
            "revision": project.revision,
            "created_at": project.created_at,
            "updated_at": project.updated_at,
        }

    def _repository_payload(self, row: ProjectRepository) -> dict[str, object]:
        return {
            "id": row.id,
            "project_id": row.project_id,
            "owner": row.owner,
            "repo": row.repo,
            "repository_type": row.repository_type or row.provider,
            "external_id": row.external_id,
            "provider": row.provider,
            "weight": row.weight,
            "enabled": row.enabled,
            "default_branch": row.default_branch,
            "last_connectivity_status": row.last_connectivity_status,
            "last_connectivity_at": row.last_connectivity_at,
            "revision": row.revision,
            "updated_at": row.updated_at,
        }

    def _feishu_resource_payload(self, row: FeishuResource) -> dict[str, object]:
        return {
            "id": row.id,
            "project_id": row.project_id,
            "resource_type": row.resource_type,
            "external_id": row.external_id,
            "name": row.name,
            "schema_hash": row.schema_hash,
            "enabled": row.enabled,
            "revision": row.revision,
            "last_connectivity_status": row.last_connectivity_status,
            "last_connectivity_at": row.last_connectivity_at,
            "updated_at": row.updated_at,
        }

    def _model_config_payload(self, row: ModelConfig) -> dict[str, object]:
        return {
            "id": row.id,
            "scope": row.scope,
            "base_url": row.base_url,
            "model": row.model,
            "temperature": row.temperature,
            "timeout_seconds": row.timeout_seconds,
            "max_retries": row.max_retries,
            "stream": row.stream,
            "revision": row.revision,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    def _prompt_payload(self, row: PromptVersion) -> dict[str, object]:
        return {
            "id": row.id,
            "prompt_type": row.prompt_type,
            "version": row.version,
            "content": row.content,
            "content_hash": row.content_hash,
            "status": row.status,
            "model_constraints": dict(row.model_constraints or {}),
            "created_by": row.created_by,
            "created_at": row.created_at,
        }

    def _async_job_payload(self, row: AsyncJob) -> dict[str, object]:
        return {
            "id": row.id,
            "job_type": row.job_type,
            "status": row.status,
            "run_id": row.run_id,
            "requested_by": row.requested_by,
            "request_hash": row.request_hash,
            "result_summary": dict(row.result_summary or {}),
            "error_code": row.error_code,
            "error_summary": row.error_summary,
            "created_at": row.created_at,
            "started_at": row.started_at,
            "completed_at": row.completed_at,
        }


def _jsonable(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    return value
