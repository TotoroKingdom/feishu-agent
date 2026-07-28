from app.providers.fake import FakeEffectProvider, FakeScenario


def test_fake_effects_return_stable_ids_without_writes() -> None:
    result = FakeEffectProvider(FakeScenario.HAPPY).preview_publish("report-001")
    assert result == {"status": "success", "external_id": "fake-document-report-001"}
