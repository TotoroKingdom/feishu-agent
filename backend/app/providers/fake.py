from enum import StrEnum


class FakeScenario(StrEnum):
    HAPPY = "happy"
    PARTIAL_FAILURE = "partial-failure"
    UNKNOWN = "unknown"


class FakeFeishuProvider:
    def __init__(self, scenario: FakeScenario = FakeScenario.HAPPY) -> None:
        self.scenario = scenario

    def read_records(self) -> list[dict[str, object]]:
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
        if self.scenario == FakeScenario.UNKNOWN:
            return {"external_id": "github-repository-example", "status": "unknown"}
        if self.scenario == FakeScenario.PARTIAL_FAILURE:
            return {"status": "failed", "error_class": "permission_denied"}
        return {
            "external_id": "github-repository-example",
            "status": "success",
            "issues": 3,
            "pull_requests": 1,
        }

    def read_issue_records(self) -> list[dict[str, object]]:
        if self.scenario == FakeScenario.UNKNOWN:
            return [{"external_id": "github-issue-unknown", "status": "unknown"}]
        if self.scenario == FakeScenario.PARTIAL_FAILURE:
            return [{"status": "failed", "error_class": "permission_denied"}]
        return [
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
        ]


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
        if self.scenario == FakeScenario.UNKNOWN:
            return {"status": "unknown", "external_id": f"fake-document-{report_id}"}
        if self.scenario == FakeScenario.PARTIAL_FAILURE:
            return {"status": "failed", "external_id": f"fake-document-{report_id}"}
        return {"status": "success", "external_id": f"fake-document-{report_id}"}
