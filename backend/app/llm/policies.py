from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final
from urllib.parse import urlparse, urlunparse

DEFAULT_ALLOWED_URL_HOSTS: Final[tuple[str, ...]] = (
    "github.com",
    "www.github.com",
    "api.github.com",
    "example.test",
    "fake.feishu.local",
    "feishu.cn",
    "www.feishu.cn",
    "feishu.com",
    "www.feishu.com",
    "lark.com",
    "www.lark.com",
)

_CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_ALLOWED_MEMBER_KEYS: Final[tuple[str, ...]] = (
    "member_id",
    "task_count",
    "issue_count",
    "overdue_issue_count",
    "pull_request_count",
    "commit_count",
    "review_count",
    "total_activity_count",
)


@dataclass(frozen=True, slots=True)
class PromptBoundaryPolicy:
    max_text_length: int = 256
    max_identifier_length: int = 128
    allowed_url_hosts: tuple[str, ...] = DEFAULT_ALLOWED_URL_HOSTS


DEFAULT_PROMPT_BOUNDARY_POLICY: Final[PromptBoundaryPolicy] = PromptBoundaryPolicy()


def sanitize_prompt_text(
    value: object,
    *,
    max_length: int,
    allow_newlines: bool = False,
) -> str:
    text = _coerce_text(value)
    text = unicodedata.normalize("NFKC", text)
    text = _CONTROL_CHAR_PATTERN.sub(" ", text)
    if allow_newlines:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = text.replace("\t", " ")
        text = re.sub(r"[^\S\n]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = text.strip()
    else:
        text = text.replace("\r", " ").replace("\n", " ").replace("\t", " ")
        text = re.sub(r"\s+", " ", text).strip()
    if max_length < 0:
        raise ValueError("max_length must be non-negative")
    if len(text) > max_length:
        text = text[:max_length].rstrip()
    return text


def sanitize_prompt_identifier(value: object, *, max_length: int) -> str:
    return sanitize_prompt_text(value, max_length=max_length, allow_newlines=False)


def sanitize_prompt_url(
    value: object,
    *,
    allowed_hosts: Sequence[str] = DEFAULT_ALLOWED_URL_HOSTS,
) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate:
        return None
    parsed = urlparse(candidate)
    if parsed.scheme.casefold() != "https":
        return None
    hostname = (parsed.hostname or "").casefold()
    if not hostname:
        return None
    if not _host_is_allowed(hostname, allowed_hosts):
        return None
    normalized = parsed._replace(scheme="https", netloc=parsed.netloc.lower())
    return urlunparse(normalized)


def sanitize_evidence_item_payload(
    item: Mapping[str, object],
    *,
    max_text_length: int = 256,
    allowed_url_hosts: Sequence[str] = DEFAULT_ALLOWED_URL_HOSTS,
) -> dict[str, object]:
    return {
        "evidence_key": sanitize_prompt_identifier(item.get("evidence_key"), max_length=128),
        "source_type": sanitize_prompt_identifier(item.get("source_type"), max_length=24),
        "source_resource_id": sanitize_prompt_identifier(
            item.get("source_resource_id"), max_length=128
        ),
        "external_id": sanitize_prompt_identifier(item.get("external_id"), max_length=128),
        "url": sanitize_prompt_url(item.get("url"), allowed_hosts=allowed_url_hosts),
        "period_start": item.get("period_start"),
        "period_end": item.get("period_end"),
        "evidence_summary": sanitize_prompt_text(
            item.get("evidence_summary"), max_length=max_text_length
        ),
        "confidence": _coerce_confidence(item.get("confidence")),
        "normalized_entity_id": sanitize_prompt_identifier(
            item.get("normalized_entity_id"), max_length=128
        ),
        "content_hash": sanitize_prompt_identifier(item.get("content_hash"), max_length=64),
        "state": sanitize_prompt_identifier(item.get("state"), max_length=24),
        "is_overdue": bool(item.get("is_overdue")),
    }


def sanitize_member_activity_breakdown(
    member_activity_breakdown: Sequence[Mapping[str, object]],
    *,
    max_text_length: int = 80,
) -> list[dict[str, object]]:
    sanitized: list[dict[str, object]] = []
    for item in member_activity_breakdown:
        if not isinstance(item, Mapping):
            continue
        sanitized.append(
            {
                "member_id": sanitize_prompt_identifier(
                    item.get("member_id"), max_length=max_text_length
                )
                or "unknown",
                "task_count": _coerce_int(item.get("task_count")),
                "issue_count": _coerce_int(item.get("issue_count")),
                "overdue_issue_count": _coerce_int(item.get("overdue_issue_count")),
                "pull_request_count": _coerce_int(item.get("pull_request_count")),
                "commit_count": _coerce_int(item.get("commit_count")),
                "review_count": _coerce_int(item.get("review_count")),
                "total_activity_count": _coerce_int(item.get("total_activity_count")),
            }
        )
    return sanitized


def _coerce_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _coerce_int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(round(value))
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return 0
    return 0


def _coerce_confidence(value: object) -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return max(0.0, min(1.0, float(value)))
    if isinstance(value, str):
        try:
            parsed = float(value.strip())
        except ValueError:
            return 0.0
        return max(0.0, min(1.0, parsed))
    return 0.0


def _host_is_allowed(hostname: str, allowed_hosts: Sequence[str]) -> bool:
    normalized_allowed = [host.casefold().lstrip(".") for host in allowed_hosts if host]
    return any(
        hostname == allowed_host or hostname.endswith(f".{allowed_host}")
        for allowed_host in normalized_allowed
    )
