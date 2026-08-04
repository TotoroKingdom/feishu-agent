from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Literal

from app.domain.source import (
    DEFAULT_FEISHU_RESOURCE_ID,
    DEFAULT_GITHUB_RESOURCE_ID,
    SOURCE_TYPE_FEISHU_BITABLE,
    SOURCE_TYPE_GITHUB,
    VALIDATION_RULE_SET_VERSION,
    ValidationOutcome,
)


def validate_normalized_entities(
    entities: Sequence[Mapping[str, object]],
    *,
    input_snapshot_hash: str,
    rule_set_version: str = VALIDATION_RULE_SET_VERSION,
) -> ValidationOutcome:
    critical_items: list[str] = []
    warnings: list[str] = []
    conflicts: list[dict[str, object]] = []
    seen_identity: set[tuple[str, str, str, str]] = set()
    source_counts = {SOURCE_TYPE_FEISHU_BITABLE: 0, SOURCE_TYPE_GITHUB: 0}
    source_resource_ids = {
        SOURCE_TYPE_FEISHU_BITABLE: DEFAULT_FEISHU_RESOURCE_ID,
        SOURCE_TYPE_GITHUB: DEFAULT_GITHUB_RESOURCE_ID,
    }

    for index, entity in enumerate(entities):
        source_type = str(entity.get("source_type") or "")
        entity_type = str(entity.get("entity_type") or "")
        source_resource_id = str(entity.get("source_resource_id") or "")
        external_id = str(entity.get("external_id") or "")
        state = str(entity.get("state") or "")
        attributes = entity.get("attributes")
        if source_type in source_counts:
            source_counts[source_type] += 1
        if not external_id:
            critical_items.append(
                f"{source_type or 'unknown'}:{entity_type or 'unknown'}:external_id:{index}"
            )
        if not entity.get("title"):
            warnings.append(f"{source_type or 'unknown'}:{entity_type or 'unknown'}:title:{index}")
        if (
            source_type == SOURCE_TYPE_FEISHU_BITABLE
            and source_resource_id
            and source_resource_id != source_resource_ids[SOURCE_TYPE_FEISHU_BITABLE]
        ):
            warnings.append(f"feishu_resource_mismatch:{source_resource_id}")
        if state.lower() in {"failed", "unknown"}:
            critical_items.append(f"{source_type}:{entity_type}:state:{state or 'unknown'}")
        if isinstance(attributes, Mapping) and bool(attributes.get("pull_request")):
            critical_items.append(f"{source_type}:{entity_type}:pull_request_excluded")
        identity = (source_type, source_resource_id, entity_type, external_id)
        if identity in seen_identity:
            conflicts.append({"key": "duplicate_entity", "identity": list(identity)})
        else:
            seen_identity.add(identity)

    if source_counts[SOURCE_TYPE_FEISHU_BITABLE] == 0:
        critical_items.append("feishu_records_missing")
    if source_counts[SOURCE_TYPE_GITHUB] == 0:
        critical_items.append("github_issues_missing")

    critical_count = len(critical_items)
    warning_count = len(warnings)
    status: Literal["complete", "partial", "blocked"]
    if critical_count:
        status = "blocked"
        validation_pass = False
    elif warning_count:
        status = "partial"
        validation_pass = True
    else:
        status = "complete"
        validation_pass = True

    return ValidationOutcome(
        validation_pass=validation_pass,
        data_quality_status=status,
        critical_count=critical_count,
        warning_count=warning_count,
        missing_items=critical_items,
        conflicts=conflicts,
        warnings=warnings,
        input_snapshot_hash=input_snapshot_hash,
    )
