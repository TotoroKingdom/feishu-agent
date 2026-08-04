from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, date, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import HumanApproval, new_id

SessionFactory = Callable[[], Session]

GENERATION_APPROVAL_TYPE = "generation"
PUBLISH_APPROVAL_TYPE = "publish"
HUMAN_INPUT_APPROVAL_TYPE = "human_input"
APPROVAL_ACTION_APPROVE = "approve_generation"
APPROVAL_ACTION_MODIFY = "modify_generation_scope"
APPROVAL_ACTION_CANCEL = "cancel_run"
APPROVAL_ACTION_REJECT = "reject_generation"
APPROVAL_ACTION_CONTINUE = "continue"
APPROVAL_ACTION_LEGACY_CANCEL = "cancel"
APPROVAL_ACTION_APPROVE_PUBLISH = "approve_publish"
APPROVAL_ACTION_REGENERATE_REPORT = "regenerate_report"
APPROVAL_ACTION_UPDATE_SUPPLEMENT = "update_supplement"
APPROVAL_ACTION_CANCEL_PUBLISH = "cancel_publish"
APPROVAL_ACTION_SUBMIT_HUMAN_INPUT = "submit_human_input"
APPROVAL_ACTIONS = {
    APPROVAL_ACTION_APPROVE,
    APPROVAL_ACTION_MODIFY,
    APPROVAL_ACTION_CANCEL,
    APPROVAL_ACTION_REJECT,
    APPROVAL_ACTION_CONTINUE,
    APPROVAL_ACTION_LEGACY_CANCEL,
}
PUBLISH_APPROVAL_ACTIONS = {
    APPROVAL_ACTION_APPROVE_PUBLISH,
    APPROVAL_ACTION_REGENERATE_REPORT,
    APPROVAL_ACTION_UPDATE_SUPPLEMENT,
    APPROVAL_ACTION_CANCEL_PUBLISH,
}
HUMAN_INPUT_APPROVAL_ACTIONS = {
    APPROVAL_ACTION_SUBMIT_HUMAN_INPUT,
    APPROVAL_ACTION_CANCEL,
    APPROVAL_ACTION_LEGACY_CANCEL,
}

_ALLOWED_SCOPE_OVERRIDE_KEYS = {
    "expected_publish_group_ref",
    "feishu_resource_refs",
    "period_end",
    "period_key",
    "period_start",
    "read_plan",
    "report_period",
    "selected_repository_ids",
    "timezone",
    "user_instructions",
}
_DEFAULT_FEISHU_RESOURCE_ID = "feishu-table-example"
_DEFAULT_GITHUB_RESOURCE_ID = "github-repository-example"
_MAX_GITHUB_REPOSITORIES = 5


def canonical_json_hash(payload: Mapping[str, object]) -> str:
    normalized = _normalize_json_value(payload)
    encoded = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def build_generation_scope(state: Mapping[str, object]) -> dict[str, object]:
    base_scope = _build_base_scope(state)
    requested_action = str(state.get("requested_action") or "").strip().casefold()
    scope_override = state.get("scope_override")
    if requested_action == APPROVAL_ACTION_MODIFY:
        if not isinstance(scope_override, Mapping):
            raise ValueError("scope_override is required for modify_generation_scope")
        base_scope = merge_scope_override(base_scope, scope_override)
    scope_hash = canonical_json_hash(base_scope)
    scope = dict(base_scope)
    scope["scope_hash"] = scope_hash
    return scope


def merge_scope_override(
    base_scope: Mapping[str, object], override: Mapping[str, object]
) -> dict[str, object]:
    unknown_keys = set(override) - _ALLOWED_SCOPE_OVERRIDE_KEYS
    if unknown_keys:
        raise ValueError(f"unsupported scope override fields: {sorted(unknown_keys)}")

    merged = {
        "period_key": _coerce_string(base_scope.get("period_key"), "period_key"),
        "report_period": _coerce_report_period(base_scope.get("report_period")),
        "selected_repository_ids": _coerce_string_list(
            base_scope.get("selected_repository_ids"), "selected_repository_ids"
        ),
        "feishu_resource_refs": _coerce_string_list(
            base_scope.get("feishu_resource_refs"), "feishu_resource_refs"
        ),
        "user_instructions": _coerce_string(
            base_scope.get("user_instructions"), "user_instructions"
        ),
        "expected_publish_group_ref": _coerce_optional_string(
            base_scope.get("expected_publish_group_ref"), "expected_publish_group_ref"
        ),
        "read_plan": _coerce_list(base_scope.get("read_plan"), "read_plan"),
    }

    if "period_key" in override:
        merged["period_key"] = _coerce_string(override["period_key"], "period_key")
    if "report_period" in override:
        merged["report_period"] = _merge_report_period(
            merged["report_period"], override["report_period"]
        )
    if "period_start" in override:
        merged["report_period"]["start_at"] = _coerce_string(
            override["period_start"], "period_start"
        )
    if "period_end" in override:
        merged["report_period"]["end_at"] = _coerce_string(override["period_end"], "period_end")
    if "timezone" in override:
        merged["report_period"]["timezone"] = _coerce_string(override["timezone"], "timezone")
    if "selected_repository_ids" in override:
        merged["selected_repository_ids"] = _coerce_string_list(
            override["selected_repository_ids"], "selected_repository_ids"
        )
        _validate_github_repository_limit(merged["selected_repository_ids"])
    if "feishu_resource_refs" in override:
        merged["feishu_resource_refs"] = _coerce_string_list(
            override["feishu_resource_refs"], "feishu_resource_refs"
        )
    if "user_instructions" in override:
        merged["user_instructions"] = _coerce_string(
            override["user_instructions"], "user_instructions"
        )
    if "expected_publish_group_ref" in override:
        merged["expected_publish_group_ref"] = _coerce_optional_string(
            override["expected_publish_group_ref"], "expected_publish_group_ref"
        )
    if "read_plan" in override:
        merged["read_plan"] = _coerce_list(override["read_plan"], "read_plan")

    return merged


class GenerationApprovalStore:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def ensure_pending_generation_approval(
        self,
        *,
        run_id: str,
        revision: int,
        scope_hash: str,
        requested_from: Sequence[str] | None = None,
        card_message_id: str | None = None,
        challenge_id: str | None = None,
    ) -> HumanApproval:
        allowed_from = list(requested_from or ("local-demo",))
        with self._session_factory() as session:
            existing = session.scalar(
                select(HumanApproval).where(
                    HumanApproval.run_id == run_id,
                    HumanApproval.approval_type == GENERATION_APPROVAL_TYPE,
                    HumanApproval.revision == revision,
                )
            )
            if existing is not None:
                if existing.request_payload_hash != scope_hash:
                    raise ValueError("generation approval revision hash mismatch")
                return existing

            approval = HumanApproval(
                id=new_id(),
                run_id=run_id,
                approval_type=GENERATION_APPROVAL_TYPE,
                revision=revision,
                status="pending",
                challenge_id=challenge_id or str(uuid4()),
                card_message_id=card_message_id,
                requested_from=allowed_from,
                request_payload_hash=scope_hash,
                plan_hash=None,
                actor_id=None,
                actor_type=None,
                decision=None,
                supplement=None,
                decided_at=None,
                expires_at=None,
            )
            session.add(approval)
            session.commit()
            session.refresh(approval)
            return approval

    def load_pending_generation_approval(self, run_id: str) -> HumanApproval | None:
        with self._session_factory() as session:
            return session.scalar(
                select(HumanApproval).where(
                    HumanApproval.run_id == run_id,
                    HumanApproval.approval_type == GENERATION_APPROVAL_TYPE,
                    HumanApproval.status == "pending",
                )
            )

    def load_approval_by_challenge(self, challenge_id: str) -> HumanApproval | None:
        with self._session_factory() as session:
            return session.scalar(
                select(HumanApproval).where(HumanApproval.challenge_id == challenge_id)
            )

    def mark_generation_approval_decision(
        self,
        *,
        challenge_id: str,
        action: str,
        actor_id: str,
        supplement: Mapping[str, object] | None = None,
    ) -> HumanApproval:
        normalized_action = _normalize_action(action)
        with self._session_factory() as session:
            approval = session.scalar(
                select(HumanApproval).where(HumanApproval.challenge_id == challenge_id)
            )
            if approval is None:
                raise ValueError(f"unknown approval challenge_id: {challenge_id}")
            if approval.status != "pending":
                return approval

            approval.actor_id = actor_id
            approval.actor_type = "feishu_user"
            approval.decision = normalized_action
            approval.decided_at = datetime.now(UTC)
            if supplement is not None:
                approval.supplement = dict(supplement)

            approval.status = {
                APPROVAL_ACTION_APPROVE: "approved",
                APPROVAL_ACTION_CONTINUE: "approved",
                APPROVAL_ACTION_CANCEL: "cancelled",
                APPROVAL_ACTION_LEGACY_CANCEL: "cancelled",
                APPROVAL_ACTION_REJECT: "rejected",
                APPROVAL_ACTION_MODIFY: "superseded",
            }[normalized_action]
            session.commit()
            session.refresh(approval)
            return approval


class PublishApprovalStore:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def ensure_pending_publish_approval(
        self,
        *,
        run_id: str,
        revision: int,
        plan_hash: str,
        requested_from: Sequence[str] | None = None,
        card_message_id: str | None = None,
        challenge_id: str | None = None,
    ) -> HumanApproval:
        allowed_from = list(requested_from or ("local-demo",))
        with self._session_factory() as session:
            existing = session.scalar(
                select(HumanApproval).where(
                    HumanApproval.run_id == run_id,
                    HumanApproval.approval_type == PUBLISH_APPROVAL_TYPE,
                    HumanApproval.revision == revision,
                )
            )
            if existing is not None:
                if existing.request_payload_hash != plan_hash:
                    raise ValueError("publish approval revision hash mismatch")
                return existing

            approval = HumanApproval(
                id=new_id(),
                run_id=run_id,
                approval_type=PUBLISH_APPROVAL_TYPE,
                revision=revision,
                status="pending",
                challenge_id=challenge_id or str(uuid4()),
                card_message_id=card_message_id,
                requested_from=allowed_from,
                request_payload_hash=plan_hash,
                plan_hash=plan_hash,
                actor_id=None,
                actor_type=None,
                decision=None,
                supplement=None,
                decided_at=None,
                expires_at=None,
            )
            session.add(approval)
            session.commit()
            session.refresh(approval)
            return approval


class HumanInputApprovalStore:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def ensure_pending_human_input_approval(
        self,
        *,
        run_id: str,
        revision: int,
        request_payload_hash: str,
        requested_from: Sequence[str] | None = None,
        card_message_id: str | None = None,
        challenge_id: str | None = None,
    ) -> HumanApproval:
        allowed_from = list(requested_from or ("local-demo",))
        with self._session_factory() as session:
            existing = session.scalar(
                select(HumanApproval).where(
                    HumanApproval.run_id == run_id,
                    HumanApproval.approval_type == HUMAN_INPUT_APPROVAL_TYPE,
                    HumanApproval.revision == revision,
                )
            )
            if existing is not None:
                if existing.request_payload_hash != request_payload_hash:
                    raise ValueError("human input approval revision hash mismatch")
                return existing

            approval = HumanApproval(
                id=new_id(),
                run_id=run_id,
                approval_type=HUMAN_INPUT_APPROVAL_TYPE,
                revision=revision,
                status="pending",
                challenge_id=challenge_id or str(uuid4()),
                card_message_id=card_message_id,
                requested_from=allowed_from,
                request_payload_hash=request_payload_hash,
                plan_hash=None,
                actor_id=None,
                actor_type=None,
                decision=None,
                supplement=None,
                decided_at=None,
                expires_at=None,
            )
            session.add(approval)
            session.commit()
            session.refresh(approval)
            return approval

    def load_pending_human_input_approval(self, run_id: str) -> HumanApproval | None:
        with self._session_factory() as session:
            return session.scalar(
                select(HumanApproval).where(
                    HumanApproval.run_id == run_id,
                    HumanApproval.approval_type == HUMAN_INPUT_APPROVAL_TYPE,
                    HumanApproval.status == "pending",
                )
            )

    def mark_human_input_decision(
        self,
        *,
        challenge_id: str,
        action: str,
        actor_id: str,
        supplement: Mapping[str, object] | None = None,
    ) -> HumanApproval:
        normalized_action = _normalize_human_input_action(action)
        with self._session_factory() as session:
            approval = session.scalar(
                select(HumanApproval).where(HumanApproval.challenge_id == challenge_id)
            )
            if approval is None:
                raise ValueError(f"unknown approval challenge_id: {challenge_id}")
            if approval.status != "pending":
                return approval

            approval.actor_id = actor_id
            approval.actor_type = "feishu_user"
            approval.decision = normalized_action
            approval.decided_at = datetime.now(UTC)
            if supplement is not None:
                approval.supplement = dict(supplement)

            approval.status = {
                APPROVAL_ACTION_SUBMIT_HUMAN_INPUT: "approved",
                APPROVAL_ACTION_CANCEL: "cancelled",
                APPROVAL_ACTION_LEGACY_CANCEL: "cancelled",
            }[normalized_action]
            session.commit()
            session.refresh(approval)
            return approval

    def load_pending_publish_approval(self, run_id: str) -> HumanApproval | None:
        with self._session_factory() as session:
            return session.scalar(
                select(HumanApproval).where(
                    HumanApproval.run_id == run_id,
                    HumanApproval.approval_type == PUBLISH_APPROVAL_TYPE,
                    HumanApproval.status == "pending",
                )
            )

    def load_approval_by_challenge(self, challenge_id: str) -> HumanApproval | None:
        with self._session_factory() as session:
            return session.scalar(
                select(HumanApproval).where(HumanApproval.challenge_id == challenge_id)
            )

    def mark_publish_approval_decision(
        self,
        *,
        challenge_id: str,
        action: str,
        actor_id: str,
        supplement: Mapping[str, object] | None = None,
    ) -> HumanApproval:
        normalized_action = _normalize_publish_action(action)
        with self._session_factory() as session:
            approval = session.scalar(
                select(HumanApproval).where(HumanApproval.challenge_id == challenge_id)
            )
            if approval is None:
                raise ValueError(f"unknown approval challenge_id: {challenge_id}")
            if approval.status != "pending":
                return approval

            approval.actor_id = actor_id
            approval.actor_type = "feishu_user"
            approval.decision = normalized_action
            approval.decided_at = datetime.now(UTC)
            if supplement is not None:
                approval.supplement = dict(supplement)

            approval.status = {
                APPROVAL_ACTION_APPROVE_PUBLISH: "approved",
                APPROVAL_ACTION_CANCEL_PUBLISH: "cancelled",
                APPROVAL_ACTION_REGENERATE_REPORT: "superseded",
                APPROVAL_ACTION_UPDATE_SUPPLEMENT: "superseded",
            }[normalized_action]
            session.commit()
            session.refresh(approval)
            return approval

    def supersede_publish_approval(self, *, challenge_id: str, actor_id: str) -> HumanApproval:
        with self._session_factory() as session:
            approval = session.scalar(
                select(HumanApproval).where(HumanApproval.challenge_id == challenge_id)
            )
            if approval is None:
                raise ValueError(f"unknown approval challenge_id: {challenge_id}")
            if approval.status != "pending":
                return approval

            approval.actor_id = actor_id
            approval.actor_type = "feishu_user"
            approval.decision = APPROVAL_ACTION_REGENERATE_REPORT
            approval.decided_at = datetime.now(UTC)
            approval.status = "superseded"
            session.commit()
            session.refresh(approval)
            return approval


def _normalize_action(action: str) -> str:
    normalized = action.strip().casefold()
    if normalized not in APPROVAL_ACTIONS:
        raise ValueError(f"unsupported generation approval action: {action}")
    return normalized


def _normalize_publish_action(action: str) -> str:
    normalized = action.strip().casefold()
    if normalized not in PUBLISH_APPROVAL_ACTIONS:
        raise ValueError(f"unsupported publish approval action: {action}")
    return normalized


def _normalize_human_input_action(action: str) -> str:
    normalized = action.strip().casefold()
    if normalized not in HUMAN_INPUT_APPROVAL_ACTIONS:
        raise ValueError(f"unsupported human input approval action: {action}")
    return normalized


def _build_base_scope(state: Mapping[str, object]) -> dict[str, object]:
    period_key = _coerce_string(state.get("period_key"), "period_key")
    report_period = _coerce_report_period(state.get("report_period"))
    scope_state = state.get("scope")
    if isinstance(scope_state, Mapping):
        selected_repository_ids = _coerce_string_list(
            scope_state.get("selected_repository_ids"), "selected_repository_ids"
        )
        _validate_github_repository_limit(selected_repository_ids)
        feishu_resource_refs = _coerce_string_list(
            scope_state.get("feishu_resource_refs"), "feishu_resource_refs"
        )
        user_instructions = _coerce_string(
            scope_state.get("user_instructions"), "user_instructions"
        )
        expected_publish_group_ref = _coerce_optional_string(
            scope_state.get("expected_publish_group_ref"), "expected_publish_group_ref"
        )
        read_plan = _coerce_list(scope_state.get("read_plan"), "read_plan")
    else:
        selected_repository_ids = [_DEFAULT_GITHUB_RESOURCE_ID]
        feishu_resource_refs = [_DEFAULT_FEISHU_RESOURCE_ID]
        user_instructions = ""
        expected_publish_group_ref = "feishu-publish-group-example"
        read_plan = [
            {
                "source_type": "feishu_bitable",
                "source_resource_id": _DEFAULT_FEISHU_RESOURCE_ID,
                "entity_type": "feishu_record",
                "page_no": 1,
            },
            {
                "source_type": "github",
                "source_resource_id": _DEFAULT_GITHUB_RESOURCE_ID,
                "entity_type": "github_issue",
                "page_no": 1,
            },
        ]

    return {
        "period_key": period_key,
        "report_period": report_period,
        "selected_repository_ids": selected_repository_ids,
        "feishu_resource_refs": feishu_resource_refs,
        "user_instructions": user_instructions,
        "expected_publish_group_ref": expected_publish_group_ref,
        "read_plan": read_plan,
    }


def _validate_github_repository_limit(repository_ids: Sequence[str]) -> None:
    if len(repository_ids) > _MAX_GITHUB_REPOSITORIES:
        raise ValueError(
            f"selected_repository_ids cannot exceed {_MAX_GITHUB_REPOSITORIES} repositories"
        )


def _merge_report_period(base_period: Mapping[str, object], override: object) -> dict[str, object]:
    if not isinstance(override, Mapping):
        raise ValueError("report_period override must be a mapping")
    merged = {
        "start_at": _coerce_string(base_period.get("start_at"), "start_at"),
        "end_at": _coerce_string(base_period.get("end_at"), "end_at"),
        "timezone": _coerce_string(base_period.get("timezone"), "timezone"),
    }
    if "start_at" in override:
        merged["start_at"] = _coerce_string(override["start_at"], "start_at")
    if "end_at" in override:
        merged["end_at"] = _coerce_string(override["end_at"], "end_at")
    if "timezone" in override:
        merged["timezone"] = _coerce_string(override["timezone"], "timezone")
    return merged


def _coerce_report_period(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {"start_at": "", "end_at": "", "timezone": ""}
    return {
        "start_at": _coerce_string(value.get("start_at"), "start_at"),
        "end_at": _coerce_string(value.get("end_at"), "end_at"),
        "timezone": _coerce_string(value.get("timezone"), "timezone"),
    }


def _coerce_string(value: object, field_name: str) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, date | datetime):
        return value.isoformat()
    if value is None:
        return ""
    raise ValueError(f"{field_name} must be a string")


def _coerce_optional_string(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    return _coerce_string(value, field_name)


def _coerce_string_list(value: object, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
        raise ValueError(f"{field_name} must be a list")
    return [_coerce_string(item, field_name) for item in value]


def _coerce_list(value: object, field_name: str) -> list[object]:
    if value is None:
        return []
    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
        raise ValueError(f"{field_name} must be a list")
    return [item for item in value]


def _normalize_json_value(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): _normalize_json_value(item)
            for key, item in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, tuple):
        return [_normalize_json_value(item) for item in value]
    if isinstance(value, list):
        return [_normalize_json_value(item) for item in value]
    if isinstance(value, set):
        return [_normalize_json_value(item) for item in sorted(value, key=repr)]
    if isinstance(value, date | datetime):
        return value.isoformat()
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return str(value)
