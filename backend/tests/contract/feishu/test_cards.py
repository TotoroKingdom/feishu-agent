from app.providers.feishu import FeishuCardFactory, FeishuCardRecipient


def test_card_delivery_is_deterministic_for_same_purpose_revision_and_recipient() -> None:
    factory = FeishuCardFactory()
    recipient = FeishuCardRecipient(recipient_type="user", recipient_id="ou_123")

    first = factory.build_delivery(
        run_id="run-001",
        purpose="generation_approval",
        revision=1,
        recipient=recipient,
        title="Approve generation",
        summary="Review the proposed scope",
    )
    second = factory.build_delivery(
        run_id="run-001",
        purpose="generation_approval",
        revision=1,
        recipient=recipient,
        title="Approve generation",
        summary="Review the proposed scope",
    )

    assert first.content_hash == second.content_hash
    assert first.idempotency_key == second.idempotency_key
    assert first.content["header"]["purpose"] == "generation_approval"
    assert first.content["header"]["revision"] == 1
    assert first.content["recipient"]["recipient_id"] == "ou_123"


def test_card_update_uses_a_distinct_idempotency_key() -> None:
    factory = FeishuCardFactory()
    recipient = FeishuCardRecipient(recipient_type="chat", recipient_id="chat-123")

    created = factory.build_delivery(
        run_id="run-001",
        purpose="publish_approval",
        revision=2,
        recipient=recipient,
        title="Approve publish",
        summary="Review the publish plan",
    )
    updated = factory.build_delivery(
        run_id="run-001",
        purpose="publish_approval",
        revision=2,
        recipient=recipient,
        title="Approve publish",
        summary="Review the publish plan",
        operation="update",
        card_message_id="msg-123",
    )

    assert created.idempotency_key != updated.idempotency_key
    assert updated.operation == "update"
    assert updated.card_message_id == "msg-123"
    assert updated.content["card_message_id"] == "msg-123"
