from app.providers.fake import FakeEffectProvider, FakeScenario


def test_fake_effects_return_stable_ids_without_writes() -> None:
    provider = FakeEffectProvider(FakeScenario.HAPPY)
    document = provider.preview_publish("report-001")
    summary = provider.send_group_summary("run-001")
    archive = provider.upsert_bitable_archive("run-001")

    assert document == {
        "status": "success",
        "external_id": "fake-document-report-001",
        "url": "https://fake.feishu.local/doc/report-001",
        "provider_request_id": "fake-request-document-report-001",
    }
    assert summary == {
        "status": "success",
        "external_id": "fake-message-run-001",
        "url": "https://fake.feishu.local/message/run-001",
        "provider_request_id": "fake-request-message-run-001",
    }
    assert archive == {
        "status": "success",
        "external_id": "fake-archive-run-001",
        "url": "https://fake.feishu.local/archive/run-001",
        "provider_request_id": "fake-request-archive-run-001",
    }
