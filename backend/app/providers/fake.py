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
                {"external_id": "feishu-record-001", "status": "success"},
                {"status": "failed", "error_class": "field_missing"},
            ]
        return [
            {"external_id": "feishu-record-001", "title": "Milestone ready", "status": "success"}
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
