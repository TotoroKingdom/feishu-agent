from app.providers.fake import FakeLLMProvider, FakeScenario


def test_fake_llm_returns_stable_structured_report() -> None:
    provider = FakeLLMProvider(FakeScenario.HAPPY)
    assert provider.generate_report([{"title": "Milestone ready"}]) == {
        "status": "success",
        "summary": "Milestone ready",
        "usage": {"input_tokens": 12, "output_tokens": 8},
    }
