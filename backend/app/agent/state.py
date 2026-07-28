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
    graph_version: str
    state_schema_version: int
    current_stage: str
    current_node: str
    requested_action: Literal["continue", "cancel"]
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
        "current_node": "bootstrap_run",
        "resume_from": "bootstrap_run",
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
