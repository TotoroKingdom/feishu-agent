from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlencode
from urllib.request import Request

import pytest
from pydantic import SecretStr

from app.providers.github.client import (
    GitHubClient,
    GitHubHTTPResponse,
    GitHubNotFoundError,
    GitHubPermissionError,
    GitHubRateLimitError,
    GitHubTransport,
)


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


def test_repository_issues_are_paginated_filtered_and_prs_are_excluded() -> None:
    first_query = urlencode(
        {
            "state": "all",
            "per_page": 2,
            "since": datetime(2026, 7, 24, tzinfo=UTC).isoformat(),
        }
    )
    first_url = f"https://api.github.test/repos/acme/demo/issues?{first_query}"
    second_url = "https://api.github.test/repos/acme/demo/issues?page=2"
    transport = FakeTransport(
        responses={
            first_url: _json_response(
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
                ],
                headers={"Link": f'<{second_url}>; rel="next"'},
            ),
            second_url: _json_response(
                body=[
                    {
                        "id": 3,
                        "number": 3,
                        "title": "Old issue",
                        "updated_at": "2026-07-28T10:00:00Z",
                    }
                ]
            ),
        },
        requests=[],
    )
    client = _client(transport)

    issues = client.list_repository_issues(
        "acme",
        "demo",
        per_page=2,
        since=datetime(2026, 7, 24, tzinfo=UTC),
        until=datetime(2026, 7, 28, tzinfo=UTC),
    )

    assert [issue["number"] for issue in issues] == [1]
    assert transport.requests == [first_url, second_url]


def test_repository_pull_requests_are_listed_without_issue_filtering() -> None:
    pulls_url = "https://api.github.test/repos/acme/demo/pulls?state=all&per_page=100"
    transport = FakeTransport(
        responses={
            pulls_url: _json_response(
                body=[
                    {
                        "id": 11,
                        "number": 11,
                        "title": "Add metrics",
                        "updated_at": "2026-07-25T12:00:00Z",
                    },
                    {
                        "id": 12,
                        "number": 12,
                        "title": "Refine copy",
                        "updated_at": "2026-07-26T12:00:00Z",
                    },
                ]
            )
        },
        requests=[],
    )
    client = _client(transport)

    pulls = client.list_repository_pull_requests("acme", "demo")

    assert [pull["number"] for pull in pulls] == [11, 12]


@pytest.mark.parametrize(
    ("status_code", "error_type"),
    [
        (403, GitHubPermissionError),
        (404, GitHubNotFoundError),
        (429, GitHubRateLimitError),
    ],
)
def test_repository_errors_map_to_specific_exception_types(
    status_code: int, error_type: type[Exception]
) -> None:
    url = "https://api.github.test/repos/acme/demo/issues?state=all&per_page=100"
    transport = FakeTransport(
        responses={
            url: GitHubHTTPResponse(
                status_code=status_code,
                headers={"Retry-After": "60"} if status_code == 429 else {},
                body=b'{"message":"boom"}',
            )
        },
        requests=[],
    )
    client = _client(transport)

    with pytest.raises(error_type) as error:
        client.list_repository_issues("acme", "demo")

    assert "boom" in str(error.value)
    if status_code == 429:
        assert getattr(error.value, "retry_after") == 60
