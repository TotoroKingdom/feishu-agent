from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.agent.state import (
    STATE_SCHEMA_VERSION,
    WORKFLOW_GRAPH_VERSION,
    WorkflowState,
    ensure_state_is_safe,
)


def build_workflow_graph(
    checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> Any:
    builder = StateGraph(WorkflowState)
    builder.add_node("bootstrap_run", _bootstrap_run)
    builder.add_node("await_resume", _await_resume)
    builder.add_edge(START, "bootstrap_run")
    builder.add_edge("bootstrap_run", "await_resume")
    builder.add_edge("await_resume", END)
    return builder.compile(checkpointer=checkpointer, name=WORKFLOW_GRAPH_VERSION)


def _bootstrap_run(state: WorkflowState) -> dict[str, object]:
    ensure_state_is_safe(state)
    return {
        "graph_version": WORKFLOW_GRAPH_VERSION,
        "state_schema_version": STATE_SCHEMA_VERSION,
        "current_stage": "awaiting_resume",
        "current_node": "await_resume",
        "resume_from": "bootstrap_run",
    }


def _await_resume(state: WorkflowState) -> dict[str, object]:
    ensure_state_is_safe(state)
    prompt = {
        "run_id": state["run_id"],
        "thread_id": state["thread_id"],
        "current_stage": state["current_stage"],
        "current_node": "await_resume",
    }
    resume_payload = interrupt(prompt)
    if not isinstance(resume_payload, Mapping):
        raise ValueError("resume payload must be a mapping")
    ensure_state_is_safe(resume_payload)
    action = str(resume_payload.get("action", "")).strip().casefold()
    if action not in {"continue", "cancel"}:
        raise ValueError("unsupported resume action")
    if action == "cancel":
        return {
            "requested_action": "cancel",
            "cancel_requested": True,
            "current_stage": "cancelled",
            "current_node": "complete_run",
            "resume_from": "await_resume",
        }
    return {
        "requested_action": "continue",
        "current_stage": "completed",
        "current_node": "complete_run",
        "resume_from": "await_resume",
    }
