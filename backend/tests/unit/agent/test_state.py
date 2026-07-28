import pytest
from pydantic import SecretStr

from app.agent.state import (
    STATE_SCHEMA_VERSION,
    WORKFLOW_GRAPH_VERSION,
    build_initial_state,
    ensure_state_is_safe,
    thread_id_for_run,
)


def test_build_initial_state_sets_versioned_metadata() -> None:
    state = build_initial_state("run-123")

    assert state["run_id"] == "run-123"
    assert state["thread_id"] == thread_id_for_run("run-123")
    assert state["graph_version"] == WORKFLOW_GRAPH_VERSION
    assert state["state_schema_version"] == STATE_SCHEMA_VERSION
    assert state["current_stage"] == "created"
    assert state["cancel_requested"] is False


def test_ensure_state_is_safe_rejects_secret_like_values() -> None:
    with pytest.raises(ValueError, match="secret"):
        ensure_state_is_safe({"run_id": "run-123", "app_secret": "hide-me"})

    with pytest.raises(ValueError, match="secret"):
        ensure_state_is_safe({"run_id": "run-123", "token": SecretStr("hide-me")})
