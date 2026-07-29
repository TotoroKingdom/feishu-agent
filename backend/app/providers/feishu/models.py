from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class FeishuActor(BaseModel):
    open_id: str | None = None
    user_id: str | None = None
    tenant_key: str | None = None


class FeishuResolvedActor(BaseModel):
    actor_ref: str
    actor_type: Literal["feishu_user"] = "feishu_user"
    open_id: str | None = None
    user_id: str | None = None
    tenant_key: str | None = None


class FeishuCardRecipient(BaseModel):
    recipient_type: Literal["user", "chat"]
    recipient_id: str = Field(min_length=1)


class FeishuCardMessageDraft(BaseModel):
    purpose: str = Field(min_length=1)
    revision: int
    run_id: str
    recipient: FeishuCardRecipient
    operation: Literal["create", "update"]
    content: dict[str, object] = Field(default_factory=dict)
    content_hash: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    card_message_id: str | None = None


class FeishuCardAction(BaseModel):
    action_type: str = Field(min_length=1)
    challenge_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    approval_revision: int
    payload: dict[str, object] = Field(default_factory=dict)
    presented_hash: str = Field(min_length=1)


class FeishuCardActionRequest(BaseModel):
    external_event_id: str = Field(min_length=1)
    actor: FeishuActor
    action: FeishuCardAction
    occurred_at: datetime


class FeishuEventRequest(BaseModel):
    external_event_id: str | None = None
    challenge: str | None = None
    event_type: str | None = None
    token: str | None = None
    actor: FeishuActor | None = None
    payload: dict[str, object] = Field(default_factory=dict)
    occurred_at: datetime | None = None
