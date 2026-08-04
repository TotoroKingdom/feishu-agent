from __future__ import annotations

from dataclasses import dataclass
from typing import Final

METRICS_DEFINITION_VERSION: Final[str] = "prd.v1"
OVERDUE_ISSUE_AGE_DAYS: Final[int] = 7
LONG_REVIEW_PR_AGE_DAYS: Final[int] = 7

METRIC_GITHUB_ISSUE_TOTAL_COUNT: Final[str] = "github_issue_total_count"
METRIC_GITHUB_ISSUE_OPEN_COUNT: Final[str] = "github_issue_open_count"
METRIC_GITHUB_ISSUE_CLOSED_COUNT: Final[str] = "github_issue_closed_count"
METRIC_GITHUB_ISSUE_OVERDUE_COUNT: Final[str] = "github_issue_overdue_count"
METRIC_GITHUB_PR_TOTAL_COUNT: Final[str] = "github_pr_total_count"
METRIC_GITHUB_PR_MERGED_COUNT: Final[str] = "github_pr_merged_count"
METRIC_GITHUB_PR_LONG_REVIEW_COUNT: Final[str] = "github_pr_long_review_count"
METRIC_GITHUB_COMMIT_COUNT: Final[str] = "github_commit_count"
METRIC_ACTIVE_CONTRIBUTOR_COUNT: Final[str] = "active_contributor_count"
METRIC_MILESTONE_COMPLETION_RATE: Final[str] = "milestone_completion_rate"
METRIC_PLAN_TASK_COMPLETION_RATE: Final[str] = "plan_task_completion_rate"

METRIC_KEYS: Final[tuple[str, ...]] = (
    METRIC_GITHUB_ISSUE_TOTAL_COUNT,
    METRIC_GITHUB_ISSUE_OPEN_COUNT,
    METRIC_GITHUB_ISSUE_CLOSED_COUNT,
    METRIC_GITHUB_ISSUE_OVERDUE_COUNT,
    METRIC_GITHUB_PR_TOTAL_COUNT,
    METRIC_GITHUB_PR_MERGED_COUNT,
    METRIC_GITHUB_PR_LONG_REVIEW_COUNT,
    METRIC_GITHUB_COMMIT_COUNT,
    METRIC_ACTIVE_CONTRIBUTOR_COUNT,
    METRIC_MILESTONE_COMPLETION_RATE,
    METRIC_PLAN_TASK_COMPLETION_RATE,
)


@dataclass(slots=True)
class MetricComputedValue:
    value: int
    unit: str
    description: str
    source_scope: str
