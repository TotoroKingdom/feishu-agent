from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

SOURCE_TYPE_FEISHU_BITABLE = "feishu_bitable"
SOURCE_TYPE_GITHUB = "github"
ENTITY_TYPE_FEISHU_RECORD = "feishu_record"
ENTITY_TYPE_GITHUB_ISSUE = "github_issue"
ENTITY_TYPE_GITHUB_REPOSITORY = "github_repository"
ENTITY_TYPE_GITHUB_PULL_REQUEST = "github_pull_request"
ENTITY_TYPE_GITHUB_COMMIT = "github_commit"
ENTITY_TYPE_GITHUB_REVIEW = "github_review"
ENTITY_TYPE_GITHUB_MILESTONE = "github_milestone"
ENTITY_TYPE_GITHUB_CONTRIBUTOR = "github_contributor"
NORMALIZER_VERSION = "minimal.v1"
VALIDATION_RULE_SET_VERSION = "minimal.v1"
DEFAULT_FEISHU_RESOURCE_ID = "feishu-table-example"
DEFAULT_GITHUB_RESOURCE_ID = "github-repository-example"
MAX_SOURCE_BATCH_RECORDS = 1000


@dataclass(slots=True)
class ValidationOutcome:
    validation_pass: bool
    data_quality_status: Literal["complete", "partial", "blocked"]
    critical_count: int
    warning_count: int
    missing_items: list[str]
    conflicts: list[dict[str, object]]
    warnings: list[str]
    input_snapshot_hash: str


def canonical_json_hash(value: object) -> str:
    encoded = json.dumps(
        _normalize_json_value(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _normalize_json_value(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): _normalize_json_value(item)
            for key, item in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, tuple):
        return [_normalize_json_value(item) for item in value]
    if isinstance(value, list):
        return [_normalize_json_value(item) for item in value]
    if isinstance(value, set):
        return [_normalize_json_value(item) for item in sorted(value, key=repr)]
    if hasattr(value, "isoformat") and callable(getattr(value, "isoformat")):
        return value.isoformat()
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return str(value)


def build_batch_set_hash(payload_hashes: Sequence[str]) -> str:
    return canonical_json_hash({"payload_hashes": sorted(payload_hashes)})
