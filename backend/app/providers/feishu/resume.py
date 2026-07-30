from __future__ import annotations

from collections.abc import Mapping

from app.approvals import (
    APPROVAL_ACTION_APPROVE,
    APPROVAL_ACTION_APPROVE_PUBLISH,
    APPROVAL_ACTION_CANCEL,
    APPROVAL_ACTION_CANCEL_PUBLISH,
    APPROVAL_ACTION_CONTINUE,
    APPROVAL_ACTION_LEGACY_CANCEL,
    APPROVAL_ACTION_MODIFY,
    APPROVAL_ACTION_REGENERATE_REPORT,
    APPROVAL_ACTION_REJECT,
    APPROVAL_ACTION_UPDATE_SUPPLEMENT,
    APPROVAL_ACTION_SUBMIT_HUMAN_INPUT,
    APPROVAL_ACTIONS,
    PUBLISH_APPROVAL_ACTIONS,
)
from app.providers.feishu.models import FeishuCardAction, FeishuResolvedActor


class FeishuResumeError(ValueError):
    pass


def normalize_callback_action(action: str) -> str:
    normalized = action.strip().casefold()
    aliases = {
        APPROVAL_ACTION_APPROVE: APPROVAL_ACTION_APPROVE,
        APPROVAL_ACTION_CONTINUE: APPROVAL_ACTION_APPROVE,
        APPROVAL_ACTION_MODIFY: APPROVAL_ACTION_MODIFY,
        APPROVAL_ACTION_CANCEL: APPROVAL_ACTION_CANCEL,
        APPROVAL_ACTION_LEGACY_CANCEL: APPROVAL_ACTION_CANCEL,
        APPROVAL_ACTION_REJECT: APPROVAL_ACTION_REJECT,
        APPROVAL_ACTION_APPROVE_PUBLISH: APPROVAL_ACTION_APPROVE_PUBLISH,
        APPROVAL_ACTION_REGENERATE_REPORT: APPROVAL_ACTION_REGENERATE_REPORT,
        APPROVAL_ACTION_UPDATE_SUPPLEMENT: APPROVAL_ACTION_UPDATE_SUPPLEMENT,
        APPROVAL_ACTION_SUBMIT_HUMAN_INPUT: APPROVAL_ACTION_SUBMIT_HUMAN_INPUT,
        APPROVAL_ACTION_CANCEL_PUBLISH: APPROVAL_ACTION_CANCEL_PUBLISH,
    }
    if normalized not in aliases:
        raise FeishuResumeError(f"unsupported callback action: {action}")
    return aliases[normalized]


def approval_type_for_action(action: str) -> str:
    if action == APPROVAL_ACTION_SUBMIT_HUMAN_INPUT:
        return "human_input"
    if action in APPROVAL_ACTIONS:
        return "generation"
    if action in PUBLISH_APPROVAL_ACTIONS:
        return "publish"
    raise FeishuResumeError(f"unsupported callback action: {action}")


def build_resume_payload(
    *, action: FeishuCardAction, actor: FeishuResolvedActor
) -> dict[str, object]:
    normalized_action = normalize_callback_action(action.action_type)
    payload: dict[str, object] = {
        "action": normalized_action,
        "challenge_id": action.challenge_id,
        "approval_ref": action.challenge_id,
        "approval_revision": action.approval_revision,
        "presented_hash": action.presented_hash,
        "actor_id": actor.actor_ref,
        "actor_type": actor.actor_type,
        "run_id": action.run_id,
    }
    if action.payload:
        payload["payload"] = dict(action.payload)
        if normalized_action == APPROVAL_ACTION_MODIFY and "scope_override" in action.payload:
            payload["scope_override"] = dict(action.payload["scope_override"])  # type: ignore[arg-type]
        if (
            normalized_action == APPROVAL_ACTION_UPDATE_SUPPLEMENT
            and "supplement" in action.payload
        ):
            payload["supplement"] = dict(action.payload["supplement"])  # type: ignore[arg-type]
        if normalized_action == APPROVAL_ACTION_SUBMIT_HUMAN_INPUT:
            supplement = action.payload.get("supplement")
            if isinstance(supplement, Mapping):
                payload["supplement"] = dict(supplement)
            else:
                payload["supplement"] = dict(action.payload)
    return payload


def requested_from_matches(actor_refs: set[str], requested_from: list[str]) -> bool:
    return bool(actor_refs.intersection(requested_from))


def action_payload_summary(action: Mapping[str, object]) -> dict[str, object]:
    return {key: value for key, value in action.items() if key != "payload"}
