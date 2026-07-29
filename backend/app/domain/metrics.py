from __future__ import annotations

from dataclasses import dataclass
from typing import Final

METRICS_DEFINITION_VERSION: Final[str] = "minimal.v1"
OVERDUE_ISSUE_AGE_DAYS: Final[int] = 7

METRIC_GITHUB_ISSUE_TOTAL_COUNT: Final[str] = "github_issue_total_count"
METRIC_GITHUB_ISSUE_OPEN_COUNT: Final[str] = "github_issue_open_count"
METRIC_GITHUB_ISSUE_CLOSED_COUNT: Final[str] = "github_issue_closed_count"
METRIC_GITHUB_ISSUE_OVERDUE_COUNT: Final[str] = "github_issue_overdue_count"
METRIC_ACTIVE_CONTRIBUTOR_COUNT: Final[str] = "active_contributor_count"

METRIC_KEYS: Final[tuple[str, ...]] = (
    METRIC_GITHUB_ISSUE_TOTAL_COUNT,
    METRIC_GITHUB_ISSUE_OPEN_COUNT,
    METRIC_GITHUB_ISSUE_CLOSED_COUNT,
    METRIC_GITHUB_ISSUE_OVERDUE_COUNT,
    METRIC_ACTIVE_CONTRIBUTOR_COUNT,
)


@dataclass(slots=True)
class MetricComputedValue:
    value: int
    unit: str
    description: str
    source_scope: str
