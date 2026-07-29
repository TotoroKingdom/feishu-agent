from enum import StrEnum

from app.providers.feishu.bitable import FeishuBitableReadPage
from app.providers.github.resources import GitHubRepositoryCoreData


class FakeScenario(StrEnum):
    HAPPY = "happy"
    PARTIAL_FAILURE = "partial-failure"
    UNKNOWN = "unknown"


class FakeFeishuProvider:
    def __init__(self, scenario: FakeScenario = FakeScenario.HAPPY) -> None:
        self.scenario = scenario

    def read_pages(self, scope: dict[str, object] | None = None) -> list[FeishuBitableReadPage]:
        records = self.read_records(scope)
        fetch_status = _fetch_status(records)
        page = FeishuBitableReadPage(
            resource_id="feishu-table-example",
            page_no=1,
            schema_hash="fake-schema-v1",
            records=records,
            has_more=False,
            fetch_status=fetch_status,
        )
        return [page]

    def read_records(self, scope: dict[str, object] | None = None) -> list[dict[str, object]]:
        if self.scenario == FakeScenario.UNKNOWN:
            return [{"external_id": "feishu-record-unknown", "status": "unknown"}]
        if self.scenario == FakeScenario.PARTIAL_FAILURE:
            return [
                {
                    "external_id": "feishu-record-001",
                    "title": "Milestone ready",
                    "status": "success",
                    "author_external_id": "user-a",
                    "occurred_at": "2026-07-22T09:00:00+00:00",
                },
                {"status": "failed", "error_class": "field_missing"},
            ]
        return [
            {
                "external_id": "feishu-record-001",
                "title": "Milestone ready",
                "status": "success",
                "author_external_id": "user-a",
                "occurred_at": "2026-07-22T09:00:00+00:00",
            },
            {
                "external_id": "feishu-record-002",
                "title": "Team update",
                "status": "success",
                "author_external_id": "user-b",
                "occurred_at": "2026-07-23T09:00:00+00:00",
            },
        ]


class FakeGitHubProvider:
    def __init__(self, scenario: FakeScenario = FakeScenario.HAPPY) -> None:
        self.scenario = scenario

    def read_repository(self) -> dict[str, object]:
        data = self.read_repository_core_data({})
        repository = dict(data.repository)
        repository.setdefault("external_id", repository.get("id"))
        repository["status"] = data.fetch_status
        repository["issues"] = len(data.issues)
        repository["pull_requests"] = len(data.pull_requests)
        if data.error_code is not None:
            repository["error_code"] = data.error_code
        if data.error_summary is not None:
            repository["error_summary"] = data.error_summary
        return repository

    def read_issue_records(self) -> list[dict[str, object]]:
        return list(self.read_repository_core_data({}).issues)

    def read_repository_core_data(
        self, scope: dict[str, object] | None = None
    ) -> GitHubRepositoryCoreData:
        repository_ref = _scope_repository_ref(scope)
        if self.scenario == FakeScenario.UNKNOWN:
            return GitHubRepositoryCoreData(
                repository={
                    "id": "github-repository-unknown",
                    "full_name": repository_ref,
                    "name": repository_ref.split("/")[-1],
                    "status": "unknown",
                    "archived": False,
                },
                issues=[
                    {
                        "external_id": "github-issue-unknown",
                        "status": "unknown",
                    }
                ],
                fetch_status="partial",
                repository_ref=repository_ref,
            )
        if self.scenario == FakeScenario.PARTIAL_FAILURE:
            return GitHubRepositoryCoreData(
                repository={
                    "id": "github-repository-example",
                    "full_name": repository_ref,
                    "name": repository_ref.split("/")[-1],
                    "status": "failed",
                    "error_class": "permission_denied",
                    "archived": False,
                },
                issues=[
                    {
                        "status": "failed",
                        "error_class": "permission_denied",
                    }
                ],
                fetch_status="failed",
                error_code="permission_denied",
                error_summary="permission denied",
                repository_ref=repository_ref,
            )
        return GitHubRepositoryCoreData(
            repository={
                "id": "github-repository-example",
                "full_name": repository_ref,
                "name": repository_ref.split("/")[-1],
                "title": repository_ref,
                "status": "success",
                "archived": False,
                "default_branch": "main",
                "open_issues_count": 2,
                "closed_issues_count": 1,
                "pushed_at": "2026-07-24T12:00:00+00:00",
            },
            issues=[
                {
                    "external_id": "issue-1",
                    "number": 1,
                    "title": "Fix flaky test",
                    "status": "open",
                    "author_external_id": "contributor-a",
                    "occurred_at": "2026-07-22T12:00:00+00:00",
                    "html_url": "https://example.test/issues/1",
                },
                {
                    "external_id": "issue-pr-2",
                    "number": 2,
                    "title": "Add report export",
                    "status": "open",
                    "author_external_id": "contributor-b",
                    "pull_request": True,
                    "occurred_at": "2026-07-23T12:00:00+00:00",
                    "html_url": "https://example.test/pull/2",
                },
                {
                    "external_id": "issue-3",
                    "number": 3,
                    "title": "Update docs",
                    "status": "closed",
                    "author_external_id": "contributor-c",
                    "occurred_at": "2026-07-24T12:00:00+00:00",
                    "html_url": "https://example.test/issues/3",
                },
            ],
            pull_requests=[
                {
                    "external_id": "pr-2",
                    "number": 2,
                    "title": "Add report export",
                    "status": "open",
                    "author_external_id": "contributor-b",
                    "occurred_at": "2026-07-23T12:00:00+00:00",
                    "html_url": "https://example.test/pull/2",
                    "head": {"label": "feature/report-export", "ref": "feature/report-export"},
                    "base": {"ref": "main"},
                    "latest_review_state": "approved",
                    "review_count": 2,
                }
            ],
            commits=[
                {
                    "external_id": "commit-aaa111",
                    "sha": "aaa111",
                    "message": "Refine report metrics",
                    "status": "complete",
                    "author_external_id": "contributor-a",
                    "occurred_at": "2026-07-22T08:00:00+00:00",
                    "html_url": "https://example.test/commit/aaa111",
                    "commit": {
                        "message": "Refine report metrics\n\nKeep calculations stable.",
                        "author": {
                            "login": "contributor-a",
                            "date": "2026-07-22T08:00:00+00:00",
                        },
                    },
                },
                {
                    "external_id": "commit-bbb222",
                    "sha": "bbb222",
                    "message": "Add review aggregation",
                    "status": "complete",
                    "author_external_id": "contributor-b",
                    "occurred_at": "2026-07-23T08:00:00+00:00",
                    "html_url": "https://example.test/commit/bbb222",
                    "commit": {
                        "message": "Add review aggregation\n\nCapture latest review state.",
                        "author": {
                            "login": "contributor-b",
                            "date": "2026-07-23T08:00:00+00:00",
                        },
                    },
                },
            ],
            reviews=[
                {
                    "external_id": "review-1",
                    "id": 101,
                    "state": "APPROVED",
                    "title": "PR #2: Add report export",
                    "author_external_id": "reviewer-a",
                    "occurred_at": "2026-07-23T13:00:00+00:00",
                    "submitted_at": "2026-07-23T13:00:00+00:00",
                    "html_url": "https://example.test/pull/2#review-1",
                    "pull_request_number": 2,
                    "pull_request": {"number": 2, "title": "Add report export"},
                    "user": {"login": "reviewer-a"},
                },
                {
                    "external_id": "review-2",
                    "id": 102,
                    "state": "COMMENTED",
                    "title": "PR #2: Add report export",
                    "author_external_id": "reviewer-b",
                    "occurred_at": "2026-07-23T14:00:00+00:00",
                    "submitted_at": "2026-07-23T14:00:00+00:00",
                    "html_url": "https://example.test/pull/2#review-2",
                    "pull_request_number": 2,
                    "pull_request": {"number": 2, "title": "Add report export"},
                    "user": {"login": "reviewer-b"},
                },
            ],
            milestones=[
                {
                    "external_id": "milestone-1",
                    "id": 201,
                    "number": 1,
                    "title": "Release 1.0",
                    "status": "open",
                    "occurred_at": "2026-07-24T10:00:00+00:00",
                    "html_url": "https://example.test/milestones/1",
                    "description": "Ship the first release",
                    "open_issues": 2,
                    "closed_issues": 1,
                    "creator": {"login": "pm-a"},
                }
            ],
            contributors=[
                {
                    "external_id": "contributor-a",
                    "login": "contributor-a",
                    "name": "Contributor A",
                    "status": "active",
                    "contributions": 12,
                    "html_url": "https://example.test/users/contributor-a",
                },
                {
                    "external_id": "contributor-b",
                    "login": "contributor-b",
                    "name": "Contributor B",
                    "status": "active",
                    "contributions": 7,
                    "html_url": "https://example.test/users/contributor-b",
                },
            ],
            repository_ref=repository_ref,
        )


class FakeLLMProvider:
    def __init__(self, scenario: FakeScenario = FakeScenario.HAPPY) -> None:
        self.scenario = scenario

    def generate_report(self, records: list[dict[str, object]]) -> dict[str, object]:
        if self.scenario == FakeScenario.UNKNOWN:
            return {"status": "unknown", "error_class": "timeout"}
        if self.scenario == FakeScenario.PARTIAL_FAILURE:
            return {"status": "failed", "error_class": "invalid_structured_output"}
        title = str(records[0].get("title", "No updates")) if records else "No updates"
        return {
            "status": "success",
            "summary": title,
            "usage": {"input_tokens": 12, "output_tokens": 8},
        }


class FakeEffectProvider:
    def __init__(self, scenario: FakeScenario = FakeScenario.HAPPY) -> None:
        self.scenario = scenario

    def preview_publish(self, report_id: str) -> dict[str, str]:
        return self.create_feishu_document(report_id)

    def create_feishu_document(self, report_id: str) -> dict[str, str]:
        if self.scenario == FakeScenario.UNKNOWN:
            return {
                "status": "unknown",
                "external_id": f"fake-document-{report_id}",
                "url": f"https://fake.feishu.local/doc/{report_id}",
            }
        if self.scenario == FakeScenario.PARTIAL_FAILURE:
            return {
                "status": "failed",
                "external_id": f"fake-document-{report_id}",
                "url": f"https://fake.feishu.local/doc/{report_id}",
                "error_class": "document_creation_failed",
            }
        return {
            "status": "success",
            "external_id": f"fake-document-{report_id}",
            "url": f"https://fake.feishu.local/doc/{report_id}",
            "provider_request_id": f"fake-request-document-{report_id}",
        }

    def send_group_summary(self, run_id: str) -> dict[str, str]:
        if self.scenario == FakeScenario.UNKNOWN:
            return {
                "status": "unknown",
                "external_id": f"fake-message-{run_id}",
                "url": f"https://fake.feishu.local/message/{run_id}",
            }
        if self.scenario == FakeScenario.PARTIAL_FAILURE:
            return {
                "status": "failed",
                "external_id": f"fake-message-{run_id}",
                "url": f"https://fake.feishu.local/message/{run_id}",
                "error_class": "message_send_failed",
            }
        return {
            "status": "success",
            "external_id": f"fake-message-{run_id}",
            "url": f"https://fake.feishu.local/message/{run_id}",
            "provider_request_id": f"fake-request-message-{run_id}",
        }

    def upsert_bitable_archive(self, run_id: str) -> dict[str, str]:
        if self.scenario == FakeScenario.UNKNOWN:
            return {
                "status": "unknown",
                "external_id": f"fake-archive-{run_id}",
                "url": f"https://fake.feishu.local/archive/{run_id}",
            }
        if self.scenario == FakeScenario.PARTIAL_FAILURE:
            return {
                "status": "failed",
                "external_id": f"fake-archive-{run_id}",
                "url": f"https://fake.feishu.local/archive/{run_id}",
                "error_class": "archive_write_failed",
            }
        return {
            "status": "success",
            "external_id": f"fake-archive-{run_id}",
            "url": f"https://fake.feishu.local/archive/{run_id}",
            "provider_request_id": f"fake-request-archive-{run_id}",
        }


def _fetch_status(records: list[dict[str, object]]) -> str:
    statuses = {
        str(record.get("status") or "").casefold() for record in records if isinstance(record, dict)
    }
    if "failed" in statuses:
        return "failed"
    if "unknown" in statuses:
        return "partial"
    return "complete"


def _scope_repository_ref(scope: dict[str, object] | None) -> str:
    if scope is None:
        return "github-repository-example"
    selected = scope.get("selected_repository_ids")
    if isinstance(selected, list) and selected and isinstance(selected[0], str):
        candidate = selected[0].strip()
        if candidate:
            return candidate
    repository_ref = scope.get("repository_ref")
    if isinstance(repository_ref, str) and repository_ref.strip():
        return repository_ref.strip()
    return "github-repository-example"
