from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Protocol, runtime_checkable

from app.domain.source import DEFAULT_GITHUB_RESOURCE_ID
from app.providers.github.client import (
    GitHubClient,
    GitHubClientError,
    GitHubNotFoundError,
    GitHubPermissionError,
    GitHubRateLimitError,
)
from app.security.credentials import CredentialVault

GitHubFetchStatus = Literal["complete", "partial", "failed"]


@dataclass(slots=True)
class GitHubRepositoryCoreData:
    repository: dict[str, object]
    issues: list[dict[str, object]] = field(default_factory=list)
    pull_requests: list[dict[str, object]] = field(default_factory=list)
    commits: list[dict[str, object]] = field(default_factory=list)
    reviews: list[dict[str, object]] = field(default_factory=list)
    milestones: list[dict[str, object]] = field(default_factory=list)
    contributors: list[dict[str, object]] = field(default_factory=list)
    fetch_status: GitHubFetchStatus = "complete"
    error_code: str | None = None
    error_summary: str | None = None
    repository_ref: str = DEFAULT_GITHUB_RESOURCE_ID

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "repository": dict(self.repository),
            "records": [dict(record) for record in self.issues],
            "issues": [dict(record) for record in self.issues],
            "pull_requests": [dict(record) for record in self.pull_requests],
            "commits": [dict(record) for record in self.commits],
            "reviews": [dict(record) for record in self.reviews],
            "milestones": [dict(record) for record in self.milestones],
            "contributors": [dict(record) for record in self.contributors],
            "repository_ref": self.repository_ref,
            "fetch_status": self.fetch_status,
            "error_code": self.error_code,
            "error_summary": self.error_summary,
        }
        payload["summary"] = {
            "issue_count": len(self.issues),
            "pull_request_count": len(self.pull_requests),
            "commit_count": len(self.commits),
            "review_count": len(self.reviews),
            "milestone_count": len(self.milestones),
            "contributor_count": len(self.contributors),
        }
        payload["records_count"] = sum(
            len(records)
            for records in (
                self.issues,
                self.pull_requests,
                self.commits,
                self.reviews,
                self.milestones,
                self.contributors,
            )
        )
        return payload

    def all_records(self) -> list[dict[str, object]]:
        return [
            *[dict(record) for record in self.issues],
            *[dict(record) for record in self.pull_requests],
            *[dict(record) for record in self.commits],
            *[dict(record) for record in self.reviews],
            *[dict(record) for record in self.milestones],
            *[dict(record) for record in self.contributors],
        ]


@runtime_checkable
class GitHubRepositorySource(Protocol):
    def read_repository_core_data(
        self, scope: Mapping[str, object]
    ) -> GitHubRepositoryCoreData: ...


class GitHubRepositoryReader:
    def __init__(self, client: GitHubClient) -> None:
        self._client = client

    def read_repository_core_data(self, scope: Mapping[str, object]) -> GitHubRepositoryCoreData:
        repository_ref = _repository_ref_from_scope(scope)
        owner, repo = _split_repository_ref(repository_ref)
        period_start, period_end = _period_bounds_from_scope(scope)
        repository = self._client.get_repository(owner, repo)

        issues = self._client.list_repository_issues(
            owner,
            repo,
            since=period_start,
            until=period_end,
        )
        pull_requests = self._client.list_repository_pull_requests(
            owner,
            repo,
            since=period_start,
            until=period_end,
        )
        commits = self._client.list_repository_commits(
            owner,
            repo,
            since=period_start,
            until=period_end,
        )
        milestones = self._client.list_repository_milestones(owner, repo)
        contributors = self._client.list_repository_contributors(owner, repo)
        reviews, review_errors = self._collect_reviews(owner, repo, pull_requests)
        fetch_status: GitHubFetchStatus = "complete" if not review_errors else "partial"
        error_summary = "; ".join(review_errors) if review_errors else None
        return GitHubRepositoryCoreData(
            repository=repository,
            issues=issues,
            pull_requests=pull_requests,
            commits=commits,
            reviews=reviews,
            milestones=milestones,
            contributors=contributors,
            fetch_status=fetch_status,
            error_summary=error_summary,
            repository_ref=repository_ref,
        )

    def _collect_reviews(
        self, owner: str, repo: str, pull_requests: list[dict[str, object]]
    ) -> tuple[list[dict[str, object]], list[str]]:
        reviews: list[dict[str, object]] = []
        errors: list[str] = []
        latest_by_pr: dict[int, tuple[datetime | None, str]] = {}
        review_counts: defaultdict[int, int] = defaultdict(int)
        for pull_request in pull_requests:
            number = pull_request.get("number")
            if not isinstance(number, int):
                continue
            try:
                pull_reviews = self._client.list_pull_request_reviews(owner, repo, number)
            except (
                GitHubPermissionError,
                GitHubNotFoundError,
                GitHubRateLimitError,
                GitHubClientError,
            ) as exc:
                errors.append(f"pull_request_reviews:{number}:{type(exc).__name__}")
                continue
            review_counts[number] += len(pull_reviews)
            for review in pull_reviews:
                if not isinstance(review, dict):
                    continue
                review = dict(review)
                review["pull_request_number"] = number
                reviews.append(review)
                submitted_at = _pick_review_datetime(review)
                state = str(review.get("state") or "").casefold()
                current = latest_by_pr.get(number)
                if current is None or (
                    submitted_at is not None
                    and current[0] is not None
                    and submitted_at >= current[0]
                ):
                    latest_by_pr[number] = (submitted_at, state)
                elif current is None:
                    latest_by_pr[number] = (submitted_at, state)
        for pull_request in pull_requests:
            number = pull_request.get("number")
            if not isinstance(number, int):
                continue
            latest = latest_by_pr.get(number)
            if latest is not None:
                pull_request["latest_review_state"] = latest[1]
            pull_request["review_count"] = review_counts.get(number, 0)
        return reviews, errors


def build_github_client_from_vault(
    credential_vault: CredentialVault,
    credential_id: str,
    *,
    base_url: str = "https://api.github.com",
    user_agent: str = "feishu-agent/0.1",
    timeout_seconds: float = 30.0,
) -> GitHubClient:
    credential = credential_vault.resolve(credential_id)
    return GitHubClient(
        token_provider=lambda: credential.secret,
        base_url=base_url,
        timeout_seconds=timeout_seconds,
        user_agent=user_agent,
    )


def _repository_ref_from_scope(scope: Mapping[str, object]) -> str:
    selected = scope.get("selected_repository_ids")
    if isinstance(selected, Sequence) and selected:
        first = selected[0]
        if isinstance(first, str) and first.strip():
            return first.strip()
    repository_ref = scope.get("repository_ref")
    if isinstance(repository_ref, str) and repository_ref.strip():
        return repository_ref.strip()
    return DEFAULT_GITHUB_RESOURCE_ID


def _split_repository_ref(repository_ref: str) -> tuple[str, str]:
    if "/" not in repository_ref:
        raise ValueError(f"invalid github repository ref: {repository_ref}")
    owner, repo = repository_ref.split("/", 1)
    if not owner or not repo:
        raise ValueError(f"invalid github repository ref: {repository_ref}")
    return owner, repo


def _period_bounds_from_scope(
    scope: Mapping[str, object],
) -> tuple[datetime | None, datetime | None]:
    return (
        _coerce_datetime(scope.get("period_start")),
        _coerce_datetime(scope.get("period_end")),
    )


def _coerce_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _pick_review_datetime(review: Mapping[str, object]) -> datetime | None:
    for key in ("submitted_at", "created_at", "updated_at"):
        value = review.get(key)
        parsed = _coerce_datetime(value)
        if parsed is not None:
            return parsed
    return None
