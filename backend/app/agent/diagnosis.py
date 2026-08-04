from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy.orm import Session

from app.agent.policies.problem_registry import ProblemPolicyRegistry, ProblemPolicyResolution
from app.approvals import canonical_json_hash
from app.db.models import DiagnosisRecord, ValidationResult, new_id

SessionFactory = Callable[[], Session]


@dataclass(slots=True)
class DiagnosisOutcome:
    status: Literal["continue", "blocked"]
    problem_key: str
    problem_type: str
    severity: str
    recoverability: str
    planned_action: str
    next_node: str | None
    exit_route: str
    attempt: int
    max_attempts: int
    diagnosis_record_ref: str
    diagnosis_patch: dict[str, object]
    observation: dict[str, object]


class DiagnosisService:
    def __init__(
        self,
        session_factory: SessionFactory,
        registry: ProblemPolicyRegistry | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._registry = registry or ProblemPolicyRegistry()

    def diagnose_problem(self, state: Mapping[str, object]) -> DiagnosisOutcome:
        diagnosis_state = _mapping_value(state.get("diagnosis"))
        source_node = _source_node(state, diagnosis_state)
        error_code = _string_value(state.get("error_code"))
        error_summary = _string_value(state.get("error_summary"))
        error_class = _string_value(_mapping_value(state.get("error")).get("class"))
        observation = _build_observation(state, source_node, error_code, error_summary)

        current_counters = _mapping_value(diagnosis_state.get("retry_counters"))
        existing_attempt = int(current_counters.get(_problem_key(source_node, error_code)) or 0)
        attempt = existing_attempt + 1
        resolution = self._registry.resolve(
            node_name=source_node,
            error_code=error_code,
            error_class=error_class,
            observation=observation,
            attempt=attempt,
        )
        with self._session_factory() as session:
            record = self._create_record(
                session,
                state=state,
                source_node=source_node,
                observation=observation,
                resolution=resolution,
                attempt=attempt,
            )
            human_input_patch = _human_input_patch(
                session,
                record=record,
                source_node=source_node,
                observation=observation,
                resolution=resolution,
                attempt=attempt,
            )
            session.commit()

        retry_counters = dict(current_counters)
        retry_counters[resolution.problem_key] = attempt
        diagnosis_record_refs = _append_unique(
            diagnosis_state.get("diagnosis_record_refs"), record.id
        )
        diagnosis_patch = {
            "source_node": source_node,
            "active_problem_key": resolution.problem_key,
            "retry_counters": retry_counters,
            "diagnosis_record_refs": diagnosis_record_refs,
            "next_repair_action": resolution.planned_action,
            "planned_node": resolution.next_node,
        }
        if human_input_patch is not None:
            diagnosis_patch.update(human_input_patch)

        if resolution.exit_route == "blocked":
            diagnosis_patch["result"] = "blocked"
            diagnosis_patch["resolved_at"] = datetime.now(UTC).isoformat()
            return DiagnosisOutcome(
                status="blocked",
                problem_key=resolution.problem_key,
                problem_type=resolution.problem_type,
                severity=resolution.severity,
                recoverability=resolution.recoverability,
                planned_action=resolution.planned_action,
                next_node=None,
                exit_route=resolution.exit_route,
                attempt=attempt,
                max_attempts=resolution.max_attempts,
                diagnosis_record_ref=record.id,
                diagnosis_patch=diagnosis_patch,
                observation=observation,
            )

        return DiagnosisOutcome(
            status="continue",
            problem_key=resolution.problem_key,
            problem_type=resolution.problem_type,
            severity=resolution.severity,
            recoverability=resolution.recoverability,
            planned_action=resolution.planned_action,
            next_node=resolution.next_node,
            exit_route=resolution.exit_route,
            attempt=attempt,
            max_attempts=resolution.max_attempts,
            diagnosis_record_ref=record.id,
            diagnosis_patch=diagnosis_patch,
            observation=observation,
        )

    def _create_record(
        self,
        session: Session,
        *,
        state: Mapping[str, object],
        source_node: str,
        observation: dict[str, object],
        resolution: ProblemPolicyResolution,
        attempt: int,
    ) -> DiagnosisRecord:
        validation_result_id = _string_value(state.get("validation_result_ref"))
        if validation_result_id is not None:
            validation_result = session.get(ValidationResult, validation_result_id)
            if validation_result is None:
                validation_result_id = None
        impact_scope = _impact_scope(observation)
        record = DiagnosisRecord(
            id=new_id(),
            run_id=str(state["run_id"]),
            validation_result_id=validation_result_id,
            problem_key=resolution.problem_key,
            problem_type=resolution.problem_type,
            severity=resolution.severity,
            observation=observation,
            diagnosis={
                "source_node": source_node,
                "error_code": observation.get("error_code"),
                "error_class": observation.get("error_class"),
                "error_summary": observation.get("error_summary"),
            },
            impact_scope=impact_scope,
            recoverability=resolution.recoverability,
            planned_action=resolution.planned_action,
            action_params={
                "attempt": attempt,
                "max_attempts": resolution.max_attempts,
                "next_node": resolution.next_node,
                "exit_route": resolution.exit_route,
            },
            attempt=attempt,
            result="blocked" if resolution.exit_route == "blocked" else "planned",
            next_node=resolution.next_node,
            created_at=datetime.now(UTC),
            resolved_at=datetime.now(UTC) if resolution.exit_route == "blocked" else None,
        )
        session.add(record)
        session.flush()
        return record


def _source_node(state: Mapping[str, object], diagnosis_state: Mapping[str, object]) -> str:
    value = diagnosis_state.get("source_node")
    if isinstance(value, str) and value:
        return value
    value = state.get("current_node")
    if isinstance(value, str) and value and value != "diagnose_problem":
        return value
    return "unknown"


def _build_observation(
    state: Mapping[str, object],
    source_node: str,
    error_code: str | None,
    error_summary: str | None,
) -> dict[str, object]:
    observation = {
        "run_id": state.get("run_id"),
        "source_node": source_node,
        "current_stage": state.get("current_stage"),
        "error_code": error_code,
        "error_summary": error_summary,
        "error_class": _string_value(_mapping_value(state.get("error")).get("class")),
        "source_batch_refs": list(_list_value(state.get("source_batch_refs"))),
        "selected_repository_ids": list(_list_value(state.get("selected_repository_ids"))),
        "normalized_snapshot_ref": _string_value(state.get("normalized_snapshot_ref")),
        "validation_result_ref": _string_value(state.get("validation_result_ref")),
        "metrics_ref": _string_value(state.get("metrics_ref")),
        "evidence_set_ref": _string_value(state.get("evidence_set_ref")),
        "report_version_ref": _string_value(state.get("report_version_ref")),
        "impact_scope": {
            "critical": _is_critical_problem(source_node, error_code, error_summary),
            "source_node": source_node,
        },
    }
    return observation


def _is_critical_problem(
    source_node: str,
    error_code: str | None,
    error_summary: str | None,
) -> bool:
    normalized = _normalize_token(error_code)
    summary = _normalize_token(error_summary)
    if "non_key" in normalized or "non_key" in summary:
        return False
    if "optional" in summary:
        return False
    if source_node == "validate_data" and "missing" in normalized:
        return "non_key" not in normalized
    return True


def _problem_key(source_node: str, error_code: str | None) -> str:
    registry = ProblemPolicyRegistry()
    problem_type = registry.classify_problem_type(
        node_name=source_node,
        error_code=error_code,
        error_class=None,
        observation={},
    )
    return f"{source_node}:{problem_type}"


def _append_unique(existing: object, new_value: str | None) -> list[str]:
    items: list[str] = []
    if isinstance(existing, list):
        items.extend(item for item in existing if isinstance(item, str))
    if isinstance(new_value, str) and new_value:
        items.append(new_value)
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped


def _mapping_value(value: object) -> dict[str, object]:
    return dict(value) if isinstance(value, Mapping) else {}


def _list_value(value: object) -> list[object]:
    return list(value) if isinstance(value, list) else []


def _string_value(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _impact_scope(observation: Mapping[str, object]) -> dict[str, object]:
    impact_scope = observation.get("impact_scope")
    if isinstance(impact_scope, Mapping):
        return dict(impact_scope)
    return {}


def _human_input_patch(
    session: Session,
    *,
    record: DiagnosisRecord,
    source_node: str,
    observation: Mapping[str, object],
    resolution: ProblemPolicyResolution,
    attempt: int,
) -> dict[str, object] | None:
    if resolution.planned_action != "request_human_input":
        return None

    required_fields = _human_input_required_fields(session, record, observation, source_node)
    resume_from = _human_input_resume_from(source_node)
    prompt_schema = {
        "problem_key": resolution.problem_key,
        "requested_fields": required_fields,
        "resume_from": resume_from,
        "checkpoint_id": record.id,
    }
    return {
        "problem_key": resolution.problem_key,
        "attempt": attempt,
        "reason": _string_value(observation.get("error_summary"))
        or _string_value(observation.get("error_code"))
        or "human input required",
        "required_fields": required_fields,
        "resume_from": resume_from,
        "checkpoint_id": record.id,
        "required": True,
        "request_payload_hash": canonical_json_hash(prompt_schema),
    }


def _human_input_required_fields(
    session: Session,
    record: DiagnosisRecord,
    observation: Mapping[str, object],
    source_node: str,
) -> list[dict[str, object]]:
    if record.validation_result_id is not None:
        validation_result = session.get(ValidationResult, record.validation_result_id)
        if validation_result is not None:
            fields: list[dict[str, object]] = []
            for item in validation_result.missing_items:
                if not isinstance(item, str) or not item.strip():
                    continue
                fields.append({"name": item, "type": "string", "required": True})
            if fields:
                return fields
    summary = _normalize_token(_string_value(observation.get("error_summary")))
    code = _normalize_token(_string_value(observation.get("error_code")))
    if source_node == "validate_data" and (
        "github_username" in summary or "member_mapping" in code
    ):
        return [{"name": "github_username", "type": "string", "required": True}]
    return [{"name": "supplement", "type": "string", "required": True}]


def _human_input_resume_from(source_node: str) -> str:
    if source_node == "validate_data":
        return "validate_data"
    return source_node


def _normalize_token(value: str | None) -> str:
    if value is None:
        return ""
    return value.replace("-", "_").replace(" ", "_").strip().casefold()
