from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlencode
from urllib.request import Request

from pydantic import SecretStr

from app.providers.github.client import GitHubClient, GitHubHTTPResponse, GitHubTransport
from app.providers.github.resources import GitHubRepositoryReader


@dataclass(slots=True)
class FakeTransport(GitHubTransport):
    responses: dict[str, GitHubHTTPResponse]
    requests: list[str]

    def send(self, request: Request, *, timeout: float) -> GitHubHTTPResponse:
        self.requests.append(request.full_url)
        response = self.responses.get(request.full_url)
        if response is None:
            raise AssertionError(f"unexpected url: {request.full_url}")
        return response


def _json_response(
    *,
    status_code: int = 200,
    body: object = (),
    headers: dict[str, str] | None = None,
) -> GitHubHTTPResponse:
    return GitHubHTTPResponse(
        status_code=status_code,
        headers=headers or {},
        body=json.dumps(body).encode("utf-8"),
    )


def _client(transport: FakeTransport) -> GitHubClient:
    return GitHubClient(
        token_provider=lambda: SecretStr("ghp_test_token"),
        base_url="https://api.github.test",
        transport=transport,
    )


def test_repository_reader_collects_commits_and_aggregates_latest_reviews() -> None:
    period_start = datetime(2026, 7, 20, tzinfo=UTC)
    period_end = datetime(2026, 7, 27, tzinfo=UTC)
    scope = {
        "selected_repository_ids": ["acme/demo"],
        "period_start": period_start,
        "period_end": period_end,
    }

    issues_url = "https://api.github.test/repos/acme/demo/issues?" + urlencode(
        {
            "state": "all",
            "per_page": 100,
            "since": period_start.isoformat(),
        }
    )
    pulls_url = "https://api.github.test/repos/acme/demo/pulls?state=all&per_page=100"
    commits_url = "https://api.github.test/repos/acme/demo/commits?" + urlencode(
        {
            "per_page": 100,
            "since": period_start.isoformat(),
        }
    )
    milestones_url = "https://api.github.test/repos/acme/demo/milestones?state=all&per_page=100"
    contributors_url = "https://api.github.test/repos/acme/demo/contributors?per_page=100"
    reviews_url = "https://api.github.test/repos/acme/demo/pulls/2/reviews?per_page=100"
    transport = FakeTransport(
        responses={
            "https://api.github.test/repos/acme/demo": _json_response(
                body={
                    "id": 101,
                    "full_name": "acme/demo",
                    "name": "demo",
                    "default_branch": "main",
                    "updated_at": "2026-07-24T09:00:00Z",
                }
            ),
            issues_url: _json_response(
                body=[
                    {
                        "id": 1,
                        "number": 1,
                        "title": "Fix flaky test",
                        "updated_at": "2026-07-24T10:00:00Z",
                    },
                    {
                        "id": 2,
                        "number": 2,
                        "title": "Add release checklist",
                        "pull_request": {"url": "https://api.github.test/pulls/2"},
                        "updated_at": "2026-07-24T10:00:00Z",
                    },
                ]
            ),
            pulls_url: _json_response(
                body=[
                    {
                        "id": 11,
                        "number": 2,
                        "title": "Add release checklist",
                        "state": "open",
                        "updated_at": "2026-07-24T12:00:00Z",
                        "head": {"label": "feature/release-checklist"},
                        "base": {"ref": "main"},
                    }
                ]
            ),
            commits_url: _json_response(
                body=[
                    {
                        "sha": "aaa111",
                        "commit": {
                            "message": "Add aggregation support\n\nKeeps review state in sync.",
                            "author": {
                                "login": "contributor-a",
                                "date": "2026-07-23T08:00:00Z",
                            },
                        },
                    },
                    {
                        "sha": "bbb222",
                        "commit": {
                            "message": "Outside window",
                            "author": {
                                "login": "contributor-b",
                                "date": "2026-07-28T08:00:00Z",
                            },
                        },
                    },
                ]
            ),
            milestones_url: _json_response(
                body=[
                    {
                        "id": 201,
                        "number": 1,
                        "title": "Release 1.0",
                        "state": "open",
                        "open_issues": 2,
                        "closed_issues": 1,
                    }
                ]
            ),
            contributors_url: _json_response(
                body=[
                    {
                        "login": "contributor-a",
                        "contributions": 12,
                    }
                ]
            ),
            reviews_url: _json_response(
                body=[
                    {
                        "id": 301,
                        "state": "COMMENTED",
                        "submitted_at": "2026-07-24T13:00:00Z",
                        "user": {"login": "reviewer-a"},
                        "pull_request": {
                            "number": 2,
                            "title": "Add release checklist",
                        },
                    },
                    {
                        "id": 302,
                        "state": "APPROVED",
                        "submitted_at": "2026-07-24T14:00:00Z",
                        "user": {"login": "reviewer-b"},
                        "pull_request": {
                            "number": 2,
                            "title": "Add release checklist",
                        },
                    },
                ]
            ),
        },
        requests=[],
    )
    reader = GitHubRepositoryReader(_client(transport))

    data = reader.read_repository_core_data(scope)

    assert data.repository_ref == "acme/demo"
    assert data.repository["full_name"] == "acme/demo"
    assert len(data.issues) == 1
    assert len(data.pull_requests) == 1
    assert len(data.commits) == 1
    assert len(data.reviews) == 2
    assert len(data.milestones) == 1
    assert len(data.contributors) == 1
    assert data.fetch_status == "complete"
    assert data.pull_requests[0]["latest_review_state"] == "approved"
    assert data.pull_requests[0]["review_count"] == 2
    assert data.commits[0]["sha"] == "aaa111"
    assert transport.requests == [
        "https://api.github.test/repos/acme/demo",
        issues_url,
        pulls_url,
        commits_url,
        milestones_url,
        contributors_url,
        reviews_url,
    ]
