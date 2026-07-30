from __future__ import annotations

import pytest

from app.agent.policies.problem_registry import ProblemPolicyRegistry


@pytest.mark.parametrize(
    (
        "error_code",
        "error_class",
        "node_name",
        "observation",
        "expected_problem_type",
        "expected_action",
        "expected_exit_route",
        "expected_max_attempts",
    ),
    [
        (
            "GITHUB_TIMEOUT",
            "timeout",
            "collect_github_data",
            {},
            "timeout",
            "retry_current_node",
            "retry",
            3,
        ),
        (
            "GITHUB_RATE_LIMITED",
            "rate_limited",
            "collect_github_data",
            {},
            "rate_limit",
            "retry_current_node",
            "retry",
            3,
        ),
        (
            "GITHUB_PERMISSION_DENIED",
            "permission_denied",
            "collect_github_data",
            {},
            "permission",
            "request_human_input",
            "continue",
            1,
        ),
        (
            "MISSING_NON_KEY_FIELD",
            None,
            "validate_data",
            {"impact_scope": {"critical": False}},
            "missing",
            "degrade_and_continue",
            "continue",
            1,
        ),
        (
            "LLM_SCHEMA_INVALID",
            "schema_invalid",
            "generate_structured_report",
            {},
            "llm",
            "repair_and_retry",
            "retry",
            2,
        ),
        (
            "GROUNDING_NON_KEY",
            None,
            "verify_grounding",
            {"impact_scope": {"critical": False}},
            "grounding",
            "degrade_and_continue",
            "continue",
            1,
        ),
        (
            "GROUNDING_CLAIM_PERIOD_MISMATCH",
            None,
            "verify_grounding",
            {},
            "grounding",
            "repair_and_retry",
            "retry",
            2,
        ),
    ],
)
def test_problem_registry_classifies_known_error_classes(
    error_code: str,
    error_class: str | None,
    node_name: str,
    observation: dict[str, object],
    expected_problem_type: str,
    expected_action: str,
    expected_exit_route: str,
    expected_max_attempts: int,
) -> None:
    registry = ProblemPolicyRegistry()

    resolution = registry.resolve(
        node_name=node_name,
        error_code=error_code,
        error_class=error_class,
        observation=observation,
    )

    assert resolution.problem_type == expected_problem_type
    assert resolution.planned_action == expected_action
    assert resolution.exit_route == expected_exit_route
    assert resolution.max_attempts == expected_max_attempts
    assert expected_action in resolution.allowed_actions


def test_problem_registry_falls_back_for_unknown_errors() -> None:
    registry = ProblemPolicyRegistry()

    resolution = registry.resolve(
        node_name="generate_structured_report",
        error_code="TOTALLY_UNKNOWN",
        error_class="mystery",
        observation={},
    )

    assert resolution.problem_type == "unknown"
    assert resolution.planned_action == "abort_run"
    assert resolution.exit_route == "blocked"
    assert resolution.max_attempts == 1
    assert resolution.allowed_actions == ("abort_run",)
