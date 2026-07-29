from __future__ import annotations

from collections.abc import Mapping
from typing import Literal, cast

from app.approvals import canonical_json_hash
from app.providers.feishu.models import FeishuCardMessageDraft, FeishuCardRecipient


class FeishuCardFactory:
    def build_delivery(
        self,
        *,
        run_id: str,
        purpose: str,
        revision: int,
        recipient: FeishuCardRecipient,
        title: str,
        summary: str,
        operation: Literal["create", "update"] = "create",
        card_message_id: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> FeishuCardMessageDraft:
        content = {
            "header": {
                "title": title,
                "purpose": purpose,
                "revision": revision,
            },
            "summary": summary,
            "recipient": recipient.model_dump(mode="json"),
            "operation": operation,
            "metadata": dict(metadata or {}),
        }
        if card_message_id is not None:
            content["card_message_id"] = card_message_id
        content_hash = canonical_json_hash(content)
        idempotency_key = canonical_json_hash(
            {
                "run_id": run_id,
                "purpose": purpose,
                "revision": revision,
                "recipient": recipient.model_dump(mode="json"),
                "operation": operation,
                "content_hash": content_hash,
            }
        )
        return FeishuCardMessageDraft(
            purpose=purpose,
            revision=revision,
            run_id=run_id,
            recipient=recipient,
            operation=cast(Literal["create", "update"], operation),
            content=content,
            content_hash=content_hash,
            idempotency_key=idempotency_key,
            card_message_id=card_message_id,
        )
