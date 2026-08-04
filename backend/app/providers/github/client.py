from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable
from urllib.error import HTTPError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

from pydantic import SecretStr


@dataclass(slots=True, frozen=True)
class GitHubHTTPResponse:
    status_code: int
    headers: dict[str, str]
    body: bytes


@runtime_checkable
class GitHubTransport(Protocol):
    def send(self, request: Request, *, timeout: float) -> GitHubHTTPResponse: ...


class UrllibGitHubTransport:
    def send(self, request: Request, *, timeout: float) -> GitHubHTTPResponse:
        try:
            with urlopen(request, timeout=timeout) as response:  # nosec: controlled API client
                return GitHubHTTPResponse(
                    status_code=int(getattr(response, "status", 200)),
                    headers={key: value for key, value in response.headers.items()},
                    body=response.read(),
                )
        except HTTPError as error:
            return GitHubHTTPResponse(
                status_code=error.code,
                headers={key: value for key, value in error.headers.items()},
                body=error.read(),
            )


class GitHubClientError(RuntimeError):
    def __init__(
        self,
        status_code: int,
        message: str,
        *,
        retry_after: int | None = None,
        response_body: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after
        self.response_body = response_body


class GitHubPermissionError(GitHubClientError):
    pass


class GitHubNotFoundError(GitHubClientError):
    pass


class GitHubRateLimitError(GitHubClientError):
    pass


class GitHubServiceError(GitHubClientError):
    pass


GitHubTokenProvider = Callable[[], SecretStr]


class GitHubClient:
    def __init__(
        self,
        *,
        token_provider: GitHubTokenProvider,
        base_url: str = "https://api.github.com",
        transport: GitHubTransport | None = None,
        timeout_seconds: float = 30.0,
        user_agent: str = "feishu-agent/0.1",
    ) -> None:
        self._token_provider = token_provider
        self._base_url = base_url.rstrip("/")
        self._transport = transport or UrllibGitHubTransport()
        self._timeout_seconds = timeout_seconds
        self._user_agent = user_agent

    def __repr__(self) -> str:
        return f"GitHubClient(base_url={self._base_url!r}, auth='configured')"

    def list_repository_issues(
        self,
        owner: str,
        repo: str,
        *,
        state: str = "all",
        per_page: int = 100,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[dict[str, object]]:
        items = self._collect_pages(
            f"/repos/{owner}/{repo}/issues",
            params=_build_params(
                state=state,
                per_page=per_page,
                since=since,
            ),
        )
        return [
            item
            for item in items
            if isinstance(item, Mapping)
            and not item.get("pull_request")
            and _within_window(item, since=since, until=until)
        ]

    def list_repository_pull_requests(
        self,
        owner: str,
        repo: str,
        *,
        state: str = "all",
        per_page: int = 100,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[dict[str, object]]:
        items = self._collect_pages(
            f"/repos/{owner}/{repo}/pulls",
            params=_build_params(
                state=state,
                per_page=per_page,
            ),
        )
        return [
            item
            for item in items
            if isinstance(item, Mapping) and _within_window(item, since=since, until=until)
        ]

    def get_repository(self, owner: str, repo: str) -> dict[str, object]:
        response = self._send("GET", self._build_url(f"/repos/{owner}/{repo}"))
        payload = _decode_json(response.body)
        if not isinstance(payload, Mapping):
            raise GitHubServiceError(response.status_code, "unexpected GitHub repository payload")
        return dict(payload)

    def list_repository_commits(
        self,
        owner: str,
        repo: str,
        *,
        per_page: int = 100,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[dict[str, object]]:
        items = self._collect_pages(
            f"/repos/{owner}/{repo}/commits",
            params=_build_params(per_page=per_page, since=since),
        )
        return [
            item
            for item in items
            if isinstance(item, Mapping) and _within_commit_window(item, since=since, until=until)
        ]

    def list_pull_request_reviews(
        self,
        owner: str,
        repo: str,
        pull_number: int | str,
        *,
        per_page: int = 100,
    ) -> list[dict[str, object]]:
        return self._collect_pages(
            f"/repos/{owner}/{repo}/pulls/{pull_number}/reviews",
            params={"per_page": per_page},
        )

    def list_repository_milestones(
        self,
        owner: str,
        repo: str,
        *,
        state: str = "all",
        per_page: int = 100,
    ) -> list[dict[str, object]]:
        return self._collect_pages(
            f"/repos/{owner}/{repo}/milestones",
            params=_build_params(state=state, per_page=per_page),
        )

    def list_repository_contributors(
        self,
        owner: str,
        repo: str,
        *,
        per_page: int = 100,
    ) -> list[dict[str, object]]:
        return self._collect_pages(
            f"/repos/{owner}/{repo}/contributors",
            params={"per_page": per_page},
        )

    def _collect_pages(
        self, path: str, *, params: Mapping[str, object] | None = None
    ) -> list[dict[str, object]]:
        url: str | None = self._build_url(path, params)
        items: list[dict[str, object]] = []
        while url is not None:
            response = self._send("GET", url)
            payload = _decode_json(response.body)
            if isinstance(payload, list):
                items.extend([item for item in payload if isinstance(item, dict)])
            elif isinstance(payload, Mapping):
                items.append(dict(payload))
            else:
                raise GitHubServiceError(response.status_code, "unexpected GitHub response body")
            url = _next_link(response.headers, self._base_url)
        return items

    def _send(self, method: str, url: str, body: bytes | None = None) -> GitHubHTTPResponse:
        token = self._token_provider().get_secret_value()
        request = Request(
            url,
            data=body,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "User-Agent": self._user_agent,
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        response = self._transport.send(request, timeout=self._timeout_seconds)
        if response.status_code >= 400:
            raise _map_error(response)
        return response

    def _build_url(self, path: str, params: Mapping[str, object] | None = None) -> str:
        url = f"{self._base_url}{path}"
        if params:
            query = urlencode(
                {key: _query_value(value) for key, value in params.items() if value is not None},
                doseq=True,
            )
            if query:
                url = f"{url}?{query}"
        return url


def _query_value(value: object) -> object:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    return value


def _build_params(
    *,
    state: str | None = None,
    per_page: int,
    since: datetime | None = None,
) -> dict[str, object]:
    if state is not None:
        params: dict[str, object] = {"state": state, "per_page": per_page}
    else:
        params = {"per_page": per_page}
    if since is not None:
        params["since"] = since.astimezone(UTC).isoformat()
    return params


def _decode_json(body: bytes) -> object:
    if not body:
        return []
    return json.loads(body.decode("utf-8"))


def _next_link(headers: Mapping[str, str], base_url: str) -> str | None:
    link = headers.get("Link") or headers.get("link")
    if not link:
        return None
    for part in link.split(","):
        url_part, *params = part.split(";")
        if not any(param.strip() == 'rel="next"' for param in params):
            continue
        start = url_part.find("<")
        end = url_part.find(">")
        if start == -1 or end == -1 or end <= start + 1:
            continue
        next_url = url_part[start + 1 : end]
        return urljoin(base_url, next_url)
    return None


def _map_error(response: GitHubHTTPResponse) -> GitHubClientError:
    body_text = response.body.decode("utf-8", errors="replace") if response.body else None
    message = body_text or f"GitHub request failed with status {response.status_code}"
    retry_after = _retry_after(response.headers)
    if response.status_code in {401, 403}:
        return GitHubPermissionError(
            response.status_code, message, retry_after=retry_after, response_body=body_text
        )
    if response.status_code == 404:
        return GitHubNotFoundError(
            response.status_code, message, retry_after=retry_after, response_body=body_text
        )
    if response.status_code == 429:
        return GitHubRateLimitError(
            response.status_code, message, retry_after=retry_after, response_body=body_text
        )
    return GitHubServiceError(
        response.status_code, message, retry_after=retry_after, response_body=body_text
    )


def _retry_after(headers: Mapping[str, str]) -> int | None:
    raw = headers.get("Retry-After") or headers.get("retry-after")
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _within_window(
    item: Mapping[str, object],
    *,
    since: datetime | None,
    until: datetime | None,
) -> bool:
    boundary = _pick_datetime(item)
    if boundary is None:
        return True
    if since is not None and boundary < since.astimezone(UTC):
        return False
    if until is not None and boundary >= until.astimezone(UTC):
        return False
    return True


def _within_commit_window(
    item: Mapping[str, object],
    *,
    since: datetime | None,
    until: datetime | None,
) -> bool:
    boundary = _pick_commit_datetime(item)
    if boundary is None:
        return True
    if since is not None and boundary < since.astimezone(UTC):
        return False
    if until is not None and boundary >= until.astimezone(UTC):
        return False
    return True


def _pick_datetime(item: Mapping[str, object]) -> datetime | None:
    for key in ("updated_at", "created_at", "closed_at"):
        candidate = item.get(key)
        if isinstance(candidate, str) and candidate:
            try:
                parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
            except ValueError:
                continue
            return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return None


def _pick_commit_datetime(item: Mapping[str, object]) -> datetime | None:
    commit = item.get("commit")
    if isinstance(commit, Mapping):
        for key in ("committer", "author"):
            nested = commit.get(key)
            if isinstance(nested, Mapping):
                candidate = nested.get("date")
                if isinstance(candidate, str) and candidate:
                    try:
                        parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
                    except ValueError:
                        continue
                    return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return _pick_datetime(item)
