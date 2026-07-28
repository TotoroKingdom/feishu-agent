from app.providers.fake import FakeFeishuProvider, FakeGitHubProvider, FakeScenario


def test_fake_read_adapters_are_deterministic_and_network_free() -> None:
    first = FakeFeishuProvider(FakeScenario.HAPPY).read_records()
    second = FakeFeishuProvider(FakeScenario.HAPPY).read_records()
    github = FakeGitHubProvider(FakeScenario.HAPPY).read_repository()
    assert first == second
    assert first[0]["external_id"] == "feishu-record-001"
    assert github["external_id"] == "github-repository-example"


def test_fake_partial_failure_is_explicit() -> None:
    result = FakeGitHubProvider(FakeScenario.PARTIAL_FAILURE).read_repository()
    assert result["status"] == "failed"
    assert result["error_class"] == "permission_denied"
