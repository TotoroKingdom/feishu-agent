from __future__ import annotations

import base64
import hashlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import (
    EncryptedCredential,
    FeishuFieldMapping,
    FeishuResource,
    OnboardingSession,
    PromptVersion,
    Project,
    ProjectRepository,
    new_id,
)
from app.domain.source import canonical_json_hash
from app.security import CredentialType, CredentialVault, SecretBox

SessionFactory = Callable[[], Session]

ACTIVE_ONBOARDING_STATUSES = {"in_progress", "pending_confirmation"}
TERMINAL_ONBOARDING_STATUSES = {"completed", "cancelled", "expired"}
DEFAULT_ONBOARDING_TTL = timedelta(days=7)
DEFAULT_SECRET_KEY_VERSION = "v1"


class OnboardingNotFoundError(ValueError):
    pass


class OnboardingAuthorizationError(ValueError):
    pass


class OnboardingConflictError(ValueError):
    pass


class OnboardingStartRequest(BaseModel):
    feishu_actor_id: str = Field(min_length=1, max_length=128)


class OnboardingDraftRequest(BaseModel):
    project: dict[str, object] = Field(default_factory=dict)
    repositories: list[dict[str, object]] = Field(default_factory=list)
    feishu_resources: list[dict[str, object]] = Field(default_factory=list)
    field_mappings: dict[str, list[dict[str, object]]] = Field(default_factory=dict)
    schedule: dict[str, object] = Field(default_factory=dict)
    publish_group: dict[str, object] = Field(default_factory=dict)
    recipients: list[str] = Field(default_factory=list)


class OnboardingCredentialRequest(BaseModel):
    label: str = Field(default="github-pat", max_length=128)
    secret: str = Field(min_length=1)
    created_by: str = Field(default="admin", max_length=128)


class OnboardingSessionView(BaseModel):
    id: str
    feishu_actor_id: str
    status: str
    current_step: str
    draft_config: dict[str, object]
    credential_ref: str | None = None
    card_message_id: str | None = None
    revision: int
    expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class OnboardingPreviewView(BaseModel):
    ready: bool
    status: str
    missing: list[str] = Field(default_factory=list)
    summary: dict[str, object] = Field(default_factory=dict)


@dataclass(slots=True)
class AdminOnboardingService:
    session_factory: SessionFactory
    settings: Settings

    def start(self, feishu_actor_id: str) -> tuple[OnboardingSessionView, bool]:
        self._authorize(feishu_actor_id)
        with self.session_factory() as session:
            active = self._load_active_session(session, feishu_actor_id)
            if active is not None and not self._is_expired(active):
                return self._session_payload(active), False
            if active is not None and self._is_expired(active):
                self._expire_session(session, active)
                session.flush()

            latest = self._load_latest_session(session, feishu_actor_id)
            if latest is not None and latest.status in ACTIVE_ONBOARDING_STATUSES and self._is_expired(latest):
                self._expire_session(session, latest)
                session.flush()

            row = OnboardingSession(
                id=new_id(),
                feishu_actor_id=feishu_actor_id,
                status="in_progress",
                current_step="permissions",
                draft_config=_seed_draft(),
                credential_ref=None,
                card_message_id=None,
                revision=1,
                expires_at=datetime.now(UTC) + DEFAULT_ONBOARDING_TTL,
            )
            session.add(row)
            session.flush()
            session.commit()
            session.refresh(row)
            return self._session_payload(row), True

    def get(self, feishu_actor_id: str) -> OnboardingSessionView:
        self._authorize(feishu_actor_id)
        with self.session_factory() as session:
            row = self._load_latest_session(session, feishu_actor_id)
            if row is None:
                raise OnboardingNotFoundError(f"onboarding session not found for {feishu_actor_id}")
            if self._is_expired(row):
                row.status = "expired"
                row.current_step = "expired"
                row.revision += 1
                session.flush()
                session.commit()
            return self._session_payload(row)

    def update_draft(self, session_id: str, payload: OnboardingDraftRequest) -> OnboardingSessionView:
        with self.session_factory() as session:
            row = self._load_session(session, session_id)
            if row.status in TERMINAL_ONBOARDING_STATUSES:
                return self._session_payload(row)

            row.draft_config = _merge_draft(row.draft_config or {}, payload.model_dump(mode="python"))
            row.current_step = "resources"
            row.status = "in_progress"
            row.revision += 1
            session.flush()
            session.commit()
            session.refresh(row)
            return self._session_payload(row)

    def store_github_pat(
        self, session_id: str, payload: OnboardingCredentialRequest
    ) -> OnboardingSessionView:
        vault = self._credential_vault()
        with self.session_factory() as session:
            row = self._load_session(session, session_id)
            if row.status in TERMINAL_ONBOARDING_STATUSES:
                return self._session_payload(row)

            credential = vault.store(
                project_id=None,
                credential_type=CredentialType.GITHUB_PAT,
                label=payload.label,
                plaintext=payload.secret,
                key_version=DEFAULT_SECRET_KEY_VERSION,
                created_by=payload.created_by,
            )
            row.credential_ref = credential.id
            draft = dict(row.draft_config or {})
            credentials = dict(draft.get("credentials") or {})
            credentials["github_pat_ref"] = credential.id
            credentials["github_pat_label"] = payload.label
            draft["credentials"] = credentials
            row.draft_config = draft
            row.current_step = "review"
            row.status = "in_progress"
            row.revision += 1
            session.flush()
            session.commit()
            session.refresh(row)
            return self._session_payload(row)

    def preview(self, session_id: str) -> OnboardingPreviewView:
        with self.session_factory() as session:
            row = self._load_session(session, session_id)
            if row.status in TERMINAL_ONBOARDING_STATUSES:
                return OnboardingPreviewView(
                    ready=row.status == "completed",
                    status=row.status,
                    missing=[],
                    summary=_preview_summary(row),
                )

            missing = self._missing_fields(row)
            ready = not missing
            row.status = "pending_confirmation" if ready else "in_progress"
            row.current_step = "pending_confirmation" if ready else self._progress_step(row)
            row.revision += 1
            session.flush()
            session.commit()
            return OnboardingPreviewView(
                ready=ready,
                status=row.status,
                missing=missing,
                summary=_preview_summary(row),
            )

    def complete(self, session_id: str) -> OnboardingSessionView:
        with self.session_factory() as session:
            row = self._load_session(session, session_id)
            if row.status == "completed":
                return self._session_payload(row)
            missing = self._missing_fields(row)
            if missing:
                raise OnboardingConflictError(
                    f"onboarding session is not ready: {', '.join(missing)}"
                )

            self._apply_draft(session, row)
            row.status = "completed"
            row.current_step = "completed"
            row.revision += 1
            session.flush()
            session.commit()
            session.refresh(row)
            return self._session_payload(row)

    def cancel(self, session_id: str) -> OnboardingSessionView:
        with self.session_factory() as session:
            row = self._load_session(session, session_id)
            if row.status == "completed":
                return self._session_payload(row)
            row.status = "cancelled"
            row.current_step = "cancelled"
            row.revision += 1
            session.flush()
            session.commit()
            session.refresh(row)
            return self._session_payload(row)

    def _apply_draft(self, session: Session, row: OnboardingSession) -> None:
        config = row.draft_config or {}
        project = self._load_or_create_project(session)

        project_data = _as_mapping(config.get("project"))
        if project_data:
            project.name = str(project_data.get("name") or project.name)
            project.description = _optional_string(project_data.get("description"))
            project.timezone = str(project_data.get("timezone") or project.timezone)
            project.default_period_rule = _as_mapping(project_data.get("default_period_rule"))

        repositories = _as_list(config.get("repositories"))
        for repository_data in repositories:
            owner = _required_string(repository_data.get("owner"), "owner")
            repo = _required_string(repository_data.get("repo"), "repo")
            repository_type = _optional_string(repository_data.get("repository_type")) or "github"
            external_id = f"{owner}/{repo}"
            row_data = session.scalar(
                select(ProjectRepository).where(
                    ProjectRepository.project_id == project.id,
                    ProjectRepository.external_id == external_id,
                )
            )
            if row_data is None:
                row_data = ProjectRepository(
                    id=new_id(),
                    project_id=project.id,
                    external_id=external_id,
                    provider=repository_type,
                    owner=owner,
                    repo=repo,
                    repository_type=repository_type,
                    weight=int(repository_data.get("weight") or 100),
                    enabled=bool(repository_data.get("enabled", True)),
                    default_branch=_optional_string(repository_data.get("default_branch")),
                    last_connectivity_status=None,
                    last_connectivity_at=None,
                    revision=1,
                )
                session.add(row_data)
            else:
                row_data.provider = repository_type
                row_data.owner = owner
                row_data.repo = repo
                row_data.repository_type = repository_type
                row_data.weight = int(repository_data.get("weight") or row_data.weight)
                row_data.enabled = bool(repository_data.get("enabled", row_data.enabled))
                row_data.default_branch = _optional_string(repository_data.get("default_branch"))
                row_data.revision += 1

        resources = _as_list(config.get("feishu_resources"))
        for resource_data in resources:
            resource_type = _required_string(resource_data.get("resource_type"), "resource_type")
            external_id = _required_string(resource_data.get("external_id"), "external_id")
            row_data = session.scalar(
                select(FeishuResource).where(
                    FeishuResource.project_id == project.id,
                    FeishuResource.resource_type == resource_type,
                    FeishuResource.external_id == external_id,
                )
            )
            if row_data is None:
                row_data = FeishuResource(
                    id=new_id(),
                    project_id=project.id,
                    resource_type=resource_type,
                    external_id=external_id,
                    name=_optional_string(resource_data.get("name")),
                    schema_hash=_optional_string(resource_data.get("schema_hash")),
                    enabled=bool(resource_data.get("enabled", True)),
                    revision=1,
                    last_connectivity_status=None,
                    last_connectivity_at=None,
                )
                session.add(row_data)
            else:
                row_data.resource_type = resource_type
                row_data.external_id = external_id
                row_data.name = _optional_string(resource_data.get("name"))
                row_data.schema_hash = _optional_string(resource_data.get("schema_hash"))
                row_data.enabled = bool(resource_data.get("enabled", row_data.enabled))
                row_data.revision += 1

            mappings = _as_list((config.get("field_mappings") or {}).get(external_id))
            session.query(FeishuFieldMapping).filter(
                FeishuFieldMapping.resource_id == row_data.id
            ).delete(synchronize_session=False)
            for item in mappings:
                session.add(
                    FeishuFieldMapping(
                        id=new_id(),
                        resource_id=row_data.id,
                        logical_field=_required_string(item.get("logical_field"), "logical_field"),
                        external_field_id=_required_string(
                            item.get("external_field_id"), "external_field_id"
                        ),
                        external_field_name=_optional_string(item.get("external_field_name")),
                        external_field_type=_optional_string(item.get("external_field_type")),
                        converter=_optional_string(item.get("converter")),
                        required_level=str(item.get("required_level") or "optional"),
                        mapping_options=_as_mapping(item.get("mapping_options")),
                        enabled=bool(item.get("enabled", True)),
                    )
                )
            row_data.revision += 1

        prompt_data = _as_mapping(project_data.get("default_prompt"))
        if prompt_data:
            prompt_type = str(prompt_data.get("prompt_type") or "report")
            version = prompt_data.get("version")
            if version is None:
                version = (
                    session.scalar(
                        select(func.coalesce(func.max(PromptVersion.version), 0)).where(
                            PromptVersion.prompt_type == prompt_type
                        )
                    )
                    or 0
                )
                version = int(version) + 1
            existing_prompt = session.scalar(
                select(PromptVersion).where(
                    PromptVersion.prompt_type == prompt_type,
                    PromptVersion.version == int(version),
                )
            )
            content = str(prompt_data.get("content") or "")
            model_constraints = _as_mapping(prompt_data.get("model_constraints"))
            if existing_prompt is None:
                existing_prompt = PromptVersion(
                    id=new_id(),
                    prompt_type=prompt_type,
                    version=int(version),
                    content=content,
                    content_hash=canonical_json_hash(content),
                    status="active",
                    model_constraints=model_constraints,
                    created_by=str(prompt_data.get("created_by") or "admin"),
                )
                session.add(existing_prompt)
            else:
                existing_prompt.content = content
                existing_prompt.content_hash = canonical_json_hash(content)
                existing_prompt.status = "active"
                existing_prompt.model_constraints = model_constraints
                existing_prompt.created_by = str(prompt_data.get("created_by") or existing_prompt.created_by)
            session.query(PromptVersion).filter(
                PromptVersion.prompt_type == prompt_type,
                PromptVersion.id != existing_prompt.id,
            ).update({PromptVersion.status: "retired"}, synchronize_session=False)
            project.default_prompt_version_id = existing_prompt.id
            project.revision += 1

    def _load_or_create_project(self, session: Session) -> Project:
        project = session.scalar(select(Project).order_by(Project.created_at))
        if project is None:
            project = Project(name="Default Project", timezone="UTC")
            session.add(project)
            session.flush()
        return project

    def _refresh_progress(self, row: OnboardingSession) -> None:
        missing = self._missing_fields(row)
        if row.status in TERMINAL_ONBOARDING_STATUSES:
            return
        if missing:
            row.status = "in_progress"
            row.current_step = self._progress_step(row)
            return
        row.status = "pending_confirmation"
        row.current_step = "pending_confirmation"

    def _progress_step(self, row: OnboardingSession) -> str:
        draft = row.draft_config or {}
        if not _as_list(draft.get("repositories")) or not _as_list(draft.get("feishu_resources")):
            return "resources"
        if self._missing_mappings(draft):
            return "field_mappings"
        if not _as_mapping(draft.get("schedule")):
            return "schedule"
        if not _as_mapping(_as_mapping(draft.get("project")).get("default_prompt")):
            return "prompt"
        return "review"

    def _missing_fields(self, row: OnboardingSession) -> list[str]:
        draft = row.draft_config or {}
        missing: list[str] = []
        project = _as_mapping(draft.get("project"))
        if not _required_string(project.get("name"), "name"):
            missing.append("project.name")
        if not _required_string(project.get("timezone"), "timezone"):
            missing.append("project.timezone")
        if row.credential_ref is None:
            missing.append("github_pat")
        if not _as_list(draft.get("repositories")):
            missing.append("repositories")
        if not _as_list(draft.get("feishu_resources")):
            missing.append("feishu_resources")
        if self._missing_mappings(draft):
            missing.append("field_mappings")
        schedule = _as_mapping(draft.get("schedule"))
        if not _required_string(schedule.get("cron_expression"), "cron_expression"):
            missing.append("schedule.cron_expression")
        if not _required_string(schedule.get("timezone"), "timezone"):
            missing.append("schedule.timezone")
        publish_group = _as_mapping(draft.get("publish_group"))
        if not _required_string(publish_group.get("group_id"), "group_id"):
            missing.append("publish_group.group_id")
        if not _as_string_list(draft.get("recipients")):
            missing.append("recipients")
        prompt = _as_mapping(project.get("default_prompt"))
        if not _required_string(prompt.get("content"), "content"):
            missing.append("project.default_prompt.content")
        return missing

    def _missing_mappings(self, draft: Mapping[str, object]) -> bool:
        resources = _as_list(draft.get("feishu_resources"))
        mappings = _as_mapping(draft.get("field_mappings"))
        if not resources:
            return True
        for resource in resources:
            external_id = _optional_string(resource.get("external_id"))
            if not external_id or not _as_list(mappings.get(external_id)):
                return True
        return False

    def _session_payload(self, row: OnboardingSession) -> OnboardingSessionView:
        return OnboardingSessionView(
            id=row.id,
            feishu_actor_id=row.feishu_actor_id,
            status=row.status,
            current_step=row.current_step,
            draft_config=dict(row.draft_config or {}),
            credential_ref=row.credential_ref,
            card_message_id=row.card_message_id,
            revision=row.revision,
            expires_at=row.expires_at,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _load_session(self, session: Session, session_id: str) -> OnboardingSession:
        row = session.get(OnboardingSession, session_id)
        if row is None:
            raise OnboardingNotFoundError(f"onboarding session not found: {session_id}")
        if self._is_expired(row):
            self._expire_session(session, row)
            session.flush()
        return row

    def _load_latest_session(self, session: Session, feishu_actor_id: str) -> OnboardingSession | None:
        return session.scalar(
            select(OnboardingSession)
            .where(OnboardingSession.feishu_actor_id == feishu_actor_id)
            .order_by(OnboardingSession.updated_at.desc(), OnboardingSession.created_at.desc())
        )

    def _load_active_session(self, session: Session, feishu_actor_id: str) -> OnboardingSession | None:
        return session.scalar(
            select(OnboardingSession)
            .where(
                OnboardingSession.feishu_actor_id == feishu_actor_id,
                OnboardingSession.status.in_(ACTIVE_ONBOARDING_STATUSES),
            )
            .order_by(OnboardingSession.updated_at.desc(), OnboardingSession.created_at.desc())
        )

    def _is_expired(self, row: OnboardingSession) -> bool:
        if row.expires_at is None:
            return False
        current = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=UTC)
        return current <= datetime.now(UTC)

    def _authorize(self, feishu_actor_id: str) -> None:
        allowed = [str(ref) for ref in self.settings.feishu_allowed_actor_refs if str(ref)]
        if allowed and feishu_actor_id not in allowed:
            raise OnboardingAuthorizationError("actor is not allowed to use onboarding")

    def _expire_session(self, session: Session, row: OnboardingSession) -> None:
        if row.status != "completed" and row.credential_ref:
            credential = session.get(EncryptedCredential, row.credential_ref)
            if credential is not None:
                session.delete(credential)
            row.credential_ref = None
            draft = dict(row.draft_config or {})
            draft.pop("credentials", None)
            row.draft_config = draft
        row.status = "expired"
        row.current_step = "expired"
        row.revision += 1

    def _credential_vault(self) -> CredentialVault:
        return CredentialVault(
            self.session_factory,
            SecretBox({DEFAULT_SECRET_KEY_VERSION: self._encryption_key()}),
        )

    def _encryption_key(self) -> str:
        if self.settings.app_encryption_key is not None:
            return self.settings.app_encryption_key.get_secret_value()
        digest = hashlib.sha256(b"local-demo-onboarding-key").digest()
        return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _seed_draft() -> dict[str, object]:
    return {
        "project": {},
        "repositories": [],
        "feishu_resources": [],
        "field_mappings": {},
        "schedule": {},
        "publish_group": {},
        "recipients": [],
    }


def _merge_draft(current: Mapping[str, object], update: Mapping[str, object]) -> dict[str, object]:
    merged = dict(current)
    for key in (
        "project",
        "repositories",
        "feishu_resources",
        "field_mappings",
        "schedule",
        "publish_group",
        "recipients",
    ):
        if key in update:
            value = update[key]
            if key in {"repositories", "feishu_resources", "recipients"}:
                merged[key] = (
                    list(value)
                    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))
                    else []
                )
            elif key == "field_mappings":
                merged[key] = dict(value) if isinstance(value, Mapping) else {}
            elif isinstance(value, Mapping):
                merged[key] = dict(value)
            else:
                merged[key] = {}
    return merged


def _preview_summary(row: OnboardingSession) -> dict[str, object]:
    draft = row.draft_config or {}
    return {
        "current_step": row.current_step,
        "project": _as_mapping(draft.get("project")),
        "repositories": _as_list(draft.get("repositories")),
        "feishu_resources": _as_list(draft.get("feishu_resources")),
        "field_mappings": _as_mapping(draft.get("field_mappings")),
        "schedule": _as_mapping(draft.get("schedule")),
        "publish_group": _as_mapping(draft.get("publish_group")),
        "recipients": _as_string_list(draft.get("recipients")),
    }


def _as_mapping(value: object) -> dict[str, object]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _as_list(value: object) -> list[dict[str, object]]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [dict(item) for item in value if isinstance(item, Mapping)]
    return []


def _as_string_list(value: object) -> list[str]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [str(item) for item in value if isinstance(item, str) and item.strip()]
    return []


def _optional_string(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _required_string(value: object, field_name: str) -> str:
    text = _optional_string(value)
    if not text:
        raise ValueError(f"{field_name} is required")
    return text
