from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.request import Request

from pydantic import SecretStr

from app.providers.github.client import GitHubClient, GitHubHTTPResponse, GitHubTransport


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


def test_milestones_are_listed_and_accepted_contributors_return_empty_lists() -> None:
    milestones_url = "https://api.github.test/repos/acme/demo/milestones?state=all&per_page=100"
    contributors_url = "https://api.github.test/repos/acme/demo/contributors?per_page=100"
    transport = FakeTransport(
        responses={
            milestones_url: _json_response(
                body=[
                    {
                        "id": 201,
                        "number": 1,
                        "title": "Release 1.0",
                        "state": "open",
                        "open_issues": 2,
                        "closed_issues": 1,
                    },
                    {
                        "id": 202,
                        "number": 2,
                        "title": "Release 0.9",
                        "state": "closed",
                        "open_issues": 0,
                        "closed_issues": 5,
                    },
                ]
            ),
            contributors_url: _json_response(
                status_code=202,
                body=[],
                headers={"Retry-After": "60"},
            ),
        },
        requests=[],
    )
    client = _client(transport)

    milestones = client.list_repository_milestones("acme", "demo")
    contributors = client.list_repository_contributors("acme", "demo")

    assert [milestone["number"] for milestone in milestones] == [1, 2]
    assert contributors == []
    assert transport.requests == [milestones_url, contributors_url]
