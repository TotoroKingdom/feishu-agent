from __future__ import annotations

from collections.abc import Mapping
from typing import Literal, TypedDict

from pydantic import SecretStr

WORKFLOW_GRAPH_VERSION = "weekly_report.v1"
STATE_SCHEMA_VERSION = 1
_FORBIDDEN_KEY_FRAGMENTS = (
    "secret",
    "token",
    "password",
    "api_key",
    "apikey",
    "credential",
    "client_secret",
)


class WorkflowState(TypedDict, total=False):
    run_id: str
    thread_id: str
    project_id: str
    requester_id: str
    graph_version: str
    state_schema_version: int
    current_stage: str
    current_node: str
    period_key: str
    report_period: dict[str, object]
    selected_repository_ids: list[str]
    feishu_resource_refs: list[str]
    user_instructions: str
    expected_publish_group_ref: str | None
    read_plan: list[object]
    source_batch_refs: list[str]
    normalized_snapshot_ref: str | None
    validation_result_ref: str | None
    metrics_ref: str | None
    evidence_set_ref: str | None
    report_version_ref: str | None
    rendered_report_ref: str | None
    scope_revision: int
    scope_override: dict[str, object]
    scope: dict[str, object]
    approval_revision: int
    approval: dict[str, object]
    control: dict[str, object]
    error: dict[str, object]
    requested_action: Literal[
        "approve_generation",
        "modify_generation_scope",
        "cancel_run",
        "reject_generation",
        "continue",
        "cancel",
    ]
    resume_from: str
    cancel_requested: bool
    error_code: str
    error_summary: str


def thread_id_for_run(run_id: str) -> str:
    return f"report-run:{run_id}"


def ensure_state_is_safe(state: Mapping[str, object]) -> None:
    _scan_mapping(state, ())


def build_initial_state(run_id: str) -> WorkflowState:
    state: WorkflowState = {
        "run_id": run_id,
        "thread_id": thread_id_for_run(run_id),
        "graph_version": WORKFLOW_GRAPH_VERSION,
        "state_schema_version": STATE_SCHEMA_VERSION,
        "current_stage": "created",
        "current_node": "load_project_config",
        "scope_revision": 1,
        "approval_revision": 0,
        "source_batch_refs": [],
        "normalized_snapshot_ref": None,
        "validation_result_ref": None,
        "metrics_ref": None,
        "evidence_set_ref": None,
        "report_version_ref": None,
        "rendered_report_ref": None,
        "scope": {},
        "approval": {},
        "control": {
            "requested_action": None,
            "resume_from": "load_project_config",
            "cancel_requested": False,
        },
        "error": {},
        "requested_action": "continue",
        "resume_from": "load_project_config",
        "cancel_requested": False,
    }
    ensure_state_is_safe(state)
    return state


def _scan_mapping(mapping: Mapping[str, object], path: tuple[str, ...]) -> None:
    for key, value in mapping.items():
        key_text = str(key)
        if _contains_forbidden_fragment(key_text):
            raise ValueError(f"state contains a secret-like field: {'.'.join((*path, key_text))}")
        _scan_value(value, (*path, key_text))


def _scan_value(value: object, path: tuple[str, ...]) -> None:
    if isinstance(value, SecretStr):
        raise ValueError(f"state contains a secret value at {'.'.join(path)}")
    if isinstance(value, Mapping):
        _scan_mapping(value, path)
        return
    if isinstance(value, list | tuple):
        for index, item in enumerate(value):
            _scan_value(item, (*path, str(index)))
        return
    if isinstance(value, set):
        for index, item in enumerate(sorted(value, key=repr)):
            _scan_value(item, (*path, str(index)))


def _contains_forbidden_fragment(text: str) -> bool:
    lowered = text.casefold()
    return any(fragment in lowered for fragment in _FORBIDDEN_KEY_FRAGMENTS)
