from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

DiagnosisAction = Literal[
    "retry_current_node",
    "repair_and_retry",
    "degrade_and_continue",
    "request_human_input",
    "abort_run",
]

ExitRoute = Literal["retry", "continue", "blocked"]
Recoverability = Literal["retryable", "degradable", "human", "fatal"]


@dataclass(frozen=True, slots=True)
class ProblemPolicyResolution:
    problem_key: str
    problem_type: str
    severity: str
    recoverability: Recoverability
    planned_action: DiagnosisAction
    next_node: str | None
    exit_route: ExitRoute
    max_attempts: int
    allowed_actions: tuple[DiagnosisAction, ...]
    retryable: bool
    observation: dict[str, object]


class ProblemPolicyRegistry:
    def resolve(
        self,
        *,
        node_name: str,
        error_code: str | None,
        error_class: str | None,
        observation: Mapping[str, object] | None = None,
        attempt: int = 1,
    ) -> ProblemPolicyResolution:
        observation_dict = dict(observation or {})
        problem_type = self.classify_problem_type(
            node_name=node_name,
            error_code=error_code,
            error_class=error_class,
            observation=observation_dict,
        )
        policy = self._policy_for(problem_type, node_name=node_name, observation=observation_dict)
        normalized_attempt = max(1, attempt)
        if normalized_attempt >= policy["max_attempts"] and policy["retryable"]:
            return ProblemPolicyResolution(
                problem_key=self._problem_key(node_name, problem_type),
                problem_type=problem_type,
                severity=policy["severity"],
                recoverability=policy["recoverability"],
                planned_action="abort_run",
                next_node=None,
                exit_route="blocked",
                max_attempts=policy["max_attempts"],
                allowed_actions=("abort_run",),
                retryable=False,
                observation=observation_dict,
            )

        return ProblemPolicyResolution(
            problem_key=self._problem_key(node_name, problem_type),
            problem_type=problem_type,
            severity=policy["severity"],
            recoverability=policy["recoverability"],
            planned_action=policy["planned_action"],
            next_node=policy["next_node"],
            exit_route=policy["exit_route"],
            max_attempts=policy["max_attempts"],
            allowed_actions=policy["allowed_actions"],
            retryable=policy["retryable"],
            observation=observation_dict,
        )

    def classify_problem_type(
        self,
        *,
        node_name: str,
        error_code: str | None,
        error_class: str | None,
        observation: Mapping[str, object] | None = None,
    ) -> str:
        normalized_code = _normalize_token(error_code)
        normalized_class = _normalize_token(error_class)
        node_token = _normalize_token(node_name)
        if _contains_any((normalized_code, normalized_class), ("timeout", "transient_timeout")):
            return "timeout"
        if _contains_any((normalized_code, normalized_class), ("rate_limit", "rate_limited")):
            return "rate_limit"
        if _contains_any((normalized_code, normalized_class), ("permission", "forbidden", "auth")):
            return "permission"
        if _contains_any(
            (normalized_code, normalized_class),
            ("grounding", "claim_evidence_mismatch", "unknown_claim_key"),
        ):
            return "grounding"
        if _contains_any((normalized_code, normalized_class), ("llm", "model", "prompt")) and (
            "schema" in normalized_code or "schema" in normalized_class
        ):
            return "llm"
        if _contains_any((normalized_code, normalized_class), ("schema", "validation")):
            return "schema"
        if _contains_any((normalized_code, normalized_class), ("missing", "not_found", "absent")):
            return "missing"
        if _contains_any((normalized_code, normalized_class), ("conflict", "duplicate", "version")):
            return "conflict"
        if "report" in node_token and "schema" in normalized_code:
            return "llm"
        if _is_non_key_observation(observation or {}, normalized_code, normalized_class):
            return "missing"
        return "unknown"

    def _policy_for(
        self,
        problem_type: str,
        *,
        node_name: str,
        observation: Mapping[str, object],
    ) -> dict[str, object]:
        is_non_key = _is_non_key_observation(observation, None, None)
        if problem_type == "timeout":
            return {
                "severity": "medium",
                "recoverability": "retryable",
                "planned_action": "retry_current_node",
                "next_node": node_name,
                "exit_route": "retry",
                "max_attempts": 3,
                "allowed_actions": ("retry_current_node", "abort_run"),
                "retryable": True,
            }
        if problem_type == "rate_limit":
            return {
                "severity": "medium",
                "recoverability": "retryable",
                "planned_action": "retry_current_node",
                "next_node": node_name,
                "exit_route": "retry",
                "max_attempts": 3,
                "allowed_actions": ("retry_current_node", "abort_run"),
                "retryable": True,
            }
        if problem_type == "permission":
            return {
                "severity": "high",
                "recoverability": "human",
                "planned_action": "request_human_input",
                "next_node": None,
                "exit_route": "blocked",
                "max_attempts": 1,
                "allowed_actions": ("request_human_input", "abort_run"),
                "retryable": False,
            }
        if problem_type == "schema":
            return {
                "severity": "high",
                "recoverability": "retryable",
                "planned_action": "repair_and_retry",
                "next_node": node_name,
                "exit_route": "retry",
                "max_attempts": 2,
                "allowed_actions": ("repair_and_retry", "abort_run"),
                "retryable": True,
            }
        if problem_type == "missing":
            if is_non_key:
                return {
                    "severity": "low",
                    "recoverability": "degradable",
                    "planned_action": "degrade_and_continue",
                    "next_node": _degrade_next_node(node_name),
                    "exit_route": "continue",
                    "max_attempts": 1,
                    "allowed_actions": ("degrade_and_continue", "abort_run"),
                    "retryable": False,
                }
            return {
                "severity": "high",
                "recoverability": "retryable",
                "planned_action": "repair_and_retry",
                "next_node": node_name,
                "exit_route": "retry",
                "max_attempts": 2,
                "allowed_actions": ("repair_and_retry", "abort_run"),
                "retryable": True,
            }
        if problem_type == "conflict":
            return {
                "severity": "medium",
                "recoverability": "retryable",
                "planned_action": "repair_and_retry",
                "next_node": node_name,
                "exit_route": "retry",
                "max_attempts": 2,
                "allowed_actions": ("repair_and_retry", "retry_current_node", "abort_run"),
                "retryable": True,
            }
        if problem_type == "llm":
            return {
                "severity": "high",
                "recoverability": "retryable",
                "planned_action": "repair_and_retry",
                "next_node": node_name,
                "exit_route": "retry",
                "max_attempts": 2,
                "allowed_actions": ("repair_and_retry", "abort_run"),
                "retryable": True,
            }
        if problem_type == "grounding":
            if is_non_key:
                return {
                    "severity": "low",
                    "recoverability": "degradable",
                    "planned_action": "degrade_and_continue",
                    "next_node": _degrade_next_node(node_name),
                    "exit_route": "continue",
                    "max_attempts": 1,
                    "allowed_actions": ("degrade_and_continue", "abort_run"),
                    "retryable": False,
                }
            return {
                "severity": "high",
                "recoverability": "retryable",
                "planned_action": "repair_and_retry",
                "next_node": "generate_structured_report" if node_name == "verify_grounding" else node_name,
                "exit_route": "retry",
                "max_attempts": 2,
                "allowed_actions": ("repair_and_retry", "abort_run"),
                "retryable": True,
            }
        return {
            "severity": "critical",
            "recoverability": "fatal",
            "planned_action": "abort_run",
            "next_node": None,
            "exit_route": "blocked",
            "max_attempts": 1,
            "allowed_actions": ("abort_run",),
            "retryable": False,
        }

    @staticmethod
    def _problem_key(node_name: str, problem_type: str) -> str:
        return f"{node_name}:{problem_type}"


def _normalize_token(value: str | None) -> str:
    if value is None:
        return ""
    return value.replace("-", "_").replace(" ", "_").strip().casefold()


def _contains_any(values: Sequence[str], needles: Sequence[str]) -> bool:
    return any(needle in value for value in values for needle in needles)


def _is_non_key_observation(
    observation: Mapping[str, object], normalized_code: str | None, normalized_class: str | None
) -> bool:
    if normalized_code and "non_key" in normalized_code:
        return True
    if normalized_class and "non_key" in normalized_class:
        return True
    impact_scope = observation.get("impact_scope")
    if isinstance(impact_scope, Mapping) and impact_scope.get("critical") is False:
        return True
    error_summary = observation.get("error_summary")
    if isinstance(error_summary, str):
        summary = error_summary.casefold()
        if "non-key" in summary or "optional" in summary:
            return True
    return False


def _degrade_next_node(node_name: str) -> str | None:
    mapping = {
        "collect_feishu_data": "collect_github_data",
        "collect_github_data": "normalize_data",
        "normalize_data": "validate_data",
        "validate_data": "calculate_metrics",
        "calculate_metrics": "build_evidence",
        "build_evidence": "generate_structured_report",
        "generate_structured_report": "verify_grounding",
        "verify_grounding": "render_report",
        "render_report": "build_publish_plan",
    }
    return mapping.get(node_name, node_name or None)
