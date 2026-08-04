from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Literal, Protocol, runtime_checkable

from app.domain.source import (
    DEFAULT_FEISHU_RESOURCE_ID,
    MAX_SOURCE_BATCH_RECORDS,
    canonical_json_hash,
)

_SUPPORTED_TEXT_TYPES = {"text", "rich_text", "url", "number", "formula"}
_SUPPORTED_PERSON_TYPES = {"person"}
_SUPPORTED_DATE_TYPES = {"date", "datetime", "created_time", "last_modified_time"}
_SUPPORTED_ENUM_TYPES = {"single_select", "multi_select"}


class FeishuBitableError(ValueError):
    pass


class FeishuBitableSchemaMismatchError(FeishuBitableError):
    pass


class FeishuBitableMissingFieldError(FeishuBitableError):
    pass


class FeishuBitableTypeChangedError(FeishuBitableError):
    pass


class FeishuBitableRecordLimitError(FeishuBitableError):
    pass


@dataclass(slots=True, frozen=True)
class FeishuBitableFieldMapping:
    logical_field: str
    external_field_id: str
    external_field_name: str
    external_field_type: str
    converter: str
    required_level: Literal["critical", "required", "optional"] = "required"
    mapping_options: dict[str, object] = field(default_factory=dict)
    enabled: bool = True


@dataclass(slots=True, frozen=True)
class FeishuBitableReadPage:
    resource_id: str
    page_no: int
    schema_hash: str
    records: list[dict[str, object]]
    cursor: str | None = None
    next_cursor: str | None = None
    has_more: bool = False
    fetch_status: Literal["complete", "partial", "failed"] = "complete"
    schema_version: str = "feishu.bitable.v1"


@runtime_checkable
class FeishuBitableClient(Protocol):
    def get_table_schema(self, resource_id: str) -> Mapping[str, object]: ...

    def list_records(
        self, resource_id: str, *, page_token: str | None = None, page_size: int = 500
    ) -> Mapping[str, object]: ...


@runtime_checkable
class FeishuBitableSource(Protocol):
    def read_pages(
        self, scope: Mapping[str, object] | None = None
    ) -> Sequence[FeishuBitableReadPage]: ...

    def read_records(
        self, scope: Mapping[str, object] | None = None
    ) -> list[dict[str, object]]: ...


@dataclass(slots=True)
class FeishuBitableReader:
    client: FeishuBitableClient
    mappings_by_resource: Mapping[str, Sequence[FeishuBitableFieldMapping]] | None = None
    page_size: int = 500
    max_records: int = MAX_SOURCE_BATCH_RECORDS

    def read_pages(self, scope: Mapping[str, object] | None = None) -> list[FeishuBitableReadPage]:
        resource_ids = self._resource_ids(scope)
        pages: list[FeishuBitableReadPage] = []
        total_records = 0

        for resource_id in resource_ids:
            schema = self.client.get_table_schema(resource_id)
            schema_hash = _schema_hash(schema)
            mappings = self._mappings_for_resource(resource_id)
            validated_mappings = self._validate_mappings(schema, mappings)

            page_token: str | None = None
            page_no = 1
            while True:
                response = self.client.list_records(
                    resource_id,
                    page_token=page_token,
                    page_size=self.page_size,
                )
                raw_records = _extract_records(response)
                next_token, has_more = _extract_page_cursor(response)
                records = [
                    self._convert_record(
                        raw_record,
                        mappings=validated_mappings,
                        resource_id=resource_id,
                    )
                    for raw_record in raw_records
                ]
                total_records += len(records)
                if total_records > self.max_records:
                    raise FeishuBitableRecordLimitError(
                        f"record limit exceeded for resource {resource_id}: {self.max_records}"
                    )
                pages.append(
                    FeishuBitableReadPage(
                        resource_id=resource_id,
                        page_no=page_no,
                        schema_hash=schema_hash,
                        records=records,
                        cursor=page_token,
                        next_cursor=next_token,
                        has_more=has_more,
                        fetch_status="complete",
                    )
                )
                if not has_more:
                    break
                page_token = next_token
                page_no += 1

        return pages

    def read_records(self, scope: Mapping[str, object] | None = None) -> list[dict[str, object]]:
        records: list[dict[str, object]] = []
        for page in self.read_pages(scope):
            records.extend(page.records)
        return records

    def _resource_ids(self, scope: Mapping[str, object] | None) -> list[str]:
        if scope is None:
            return [DEFAULT_FEISHU_RESOURCE_ID]

        read_plan = scope.get("read_plan")
        if isinstance(read_plan, Sequence) and not isinstance(read_plan, str | bytes | bytearray):
            resource_ids = [
                str(item.get("source_resource_id"))
                for item in read_plan
                if isinstance(item, Mapping)
                and str(item.get("source_type") or "") == "feishu_bitable"
                and str(item.get("source_resource_id") or "")
            ]
            if resource_ids:
                return _deduplicate(resource_ids)

        resource_refs = scope.get("feishu_resource_refs")
        if isinstance(resource_refs, Sequence) and not isinstance(
            resource_refs, str | bytes | bytearray
        ):
            resource_ids = [str(value) for value in resource_refs if str(value)]
            if resource_ids:
                return _deduplicate(resource_ids)

        return [DEFAULT_FEISHU_RESOURCE_ID]

    def _mappings_for_resource(self, resource_id: str) -> list[FeishuBitableFieldMapping]:
        if self.mappings_by_resource and resource_id in self.mappings_by_resource:
            return list(self.mappings_by_resource[resource_id])
        return list(_default_mappings())

    def _validate_mappings(
        self,
        schema: Mapping[str, object],
        mappings: Sequence[FeishuBitableFieldMapping],
    ) -> list[FeishuBitableFieldMapping]:
        fields = _schema_fields(schema)
        field_index_by_id = {
            str(field.get("id") or ""): field for field in fields if str(field.get("id") or "")
        }
        field_index_by_name = {
            str(field.get("name") or ""): field for field in fields if str(field.get("name") or "")
        }

        validated: list[FeishuBitableFieldMapping] = []
        for mapping in mappings:
            if not mapping.enabled:
                continue
            field = field_index_by_id.get(mapping.external_field_id) or field_index_by_name.get(
                mapping.external_field_name
            )
            if field is None:
                if mapping.required_level in {"critical", "required"}:
                    raise FeishuBitableMissingFieldError(
                        "missing required field: "
                        f"{mapping.logical_field} -> {mapping.external_field_id}"
                    )
                continue
            actual_type = str(field.get("type") or "")
            if not _converter_matches_type(mapping.converter, actual_type):
                raise FeishuBitableTypeChangedError(
                    "field type changed for "
                    f"{mapping.logical_field}: expected {mapping.converter}, got {actual_type}"
                )
            validated.append(mapping)
        return validated

    def _convert_record(
        self,
        raw_record: Mapping[str, object],
        *,
        mappings: Sequence[FeishuBitableFieldMapping],
        resource_id: str,
    ) -> dict[str, object]:
        field_values = _record_fields(raw_record)
        converted: dict[str, object] = {
            "source_type": "feishu_bitable",
            "entity_type": "feishu_record",
            "source_resource_id": resource_id,
            "attributes": {},
            "assignee_external_ids": [],
            "labels": [],
        }

        for mapping in mappings:
            value = _read_field_value(field_values, mapping)
            converted_value = _convert_value(mapping, value)
            converted[mapping.logical_field] = converted_value

        external_id = converted.get("external_id")
        if not external_id:
            raise FeishuBitableSchemaMismatchError("external_id is required")
        if "state" not in converted and "status" in converted:
            converted["state"] = converted["status"]
        if "status" not in converted and "state" in converted:
            converted["status"] = converted["state"]
        return converted


def _default_mappings() -> list[FeishuBitableFieldMapping]:
    return [
        FeishuBitableFieldMapping(
            logical_field="external_id",
            external_field_id="external_id",
            external_field_name="external_id",
            external_field_type="text",
            converter="text",
            required_level="critical",
        ),
        FeishuBitableFieldMapping(
            logical_field="title",
            external_field_id="title",
            external_field_name="title",
            external_field_type="text",
            converter="text",
            required_level="required",
        ),
        FeishuBitableFieldMapping(
            logical_field="status",
            external_field_id="status",
            external_field_name="status",
            external_field_type="single_select",
            converter="enum",
            required_level="required",
            mapping_options={"value_map": {"done": "success", "blocked": "failed"}},
        ),
        FeishuBitableFieldMapping(
            logical_field="author_external_id",
            external_field_id="author",
            external_field_name="author",
            external_field_type="person",
            converter="person",
            required_level="required",
        ),
        FeishuBitableFieldMapping(
            logical_field="occurred_at",
            external_field_id="occurred_at",
            external_field_name="occurred_at",
            external_field_type="date",
            converter="date",
            required_level="critical",
        ),
    ]


def _schema_hash(schema: Mapping[str, object]) -> str:
    return canonical_json_hash({"fields": _schema_fields(schema)})


def _schema_fields(schema: Mapping[str, object]) -> list[dict[str, object]]:
    fields = schema.get("fields")
    if not isinstance(fields, Sequence) or isinstance(fields, str | bytes | bytearray):
        raise FeishuBitableSchemaMismatchError("schema.fields is required")
    normalized_fields: list[dict[str, object]] = []
    for raw_field in fields:
        if not isinstance(raw_field, Mapping):
            continue
        normalized_fields.append(
            {
                "id": str(raw_field.get("id") or raw_field.get("field_id") or ""),
                "name": str(raw_field.get("name") or raw_field.get("field_name") or ""),
                "type": str(raw_field.get("type") or raw_field.get("field_type") or ""),
                "options": raw_field.get("options") or {},
            }
        )
    return normalized_fields


def _extract_records(response: Mapping[str, object]) -> list[Mapping[str, object]]:
    for key in ("items", "records", "data"):
        candidate = response.get(key)
        if isinstance(candidate, Mapping) and "items" in candidate:
            nested = candidate.get("items")
            if isinstance(nested, Sequence) and not isinstance(nested, str | bytes | bytearray):
                return [item for item in nested if isinstance(item, Mapping)]
        if isinstance(candidate, Sequence) and not isinstance(candidate, str | bytes | bytearray):
            return [item for item in candidate if isinstance(item, Mapping)]
    return []


def _extract_page_cursor(response: Mapping[str, object]) -> tuple[str | None, bool]:
    has_more = bool(response.get("has_more") or response.get("hasMore"))
    for key in ("page_token", "next_page_token", "next_cursor", "cursor"):
        candidate = response.get(key)
        if isinstance(candidate, str) and candidate:
            return candidate, has_more or key != "cursor"
    data = response.get("data")
    if isinstance(data, Mapping):
        for key in ("page_token", "next_page_token", "next_cursor", "cursor"):
            candidate = data.get(key)
            if isinstance(candidate, str) and candidate:
                return candidate, has_more or key != "cursor"
        has_more = bool(data.get("has_more") or data.get("hasMore") or has_more)
    return None, has_more


def _record_fields(raw_record: Mapping[str, object]) -> Mapping[str, object]:
    fields = raw_record.get("fields")
    if isinstance(fields, Mapping):
        return fields
    return raw_record


def _read_field_value(
    field_values: Mapping[str, object], mapping: FeishuBitableFieldMapping
) -> object:
    if mapping.external_field_id in field_values:
        return field_values[mapping.external_field_id]
    if mapping.external_field_name in field_values:
        return field_values[mapping.external_field_name]
    return None


def _convert_value(mapping: FeishuBitableFieldMapping, value: object) -> object:
    converter = mapping.converter
    if converter == "text":
        return _convert_text(value)
    if converter == "person":
        return _convert_person(value, mapping.mapping_options)
    if converter == "date":
        return _convert_date(value)
    if converter == "enum":
        return _convert_enum(value, mapping.mapping_options)
    return value


def _convert_text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _convert_person(value: object, mapping_options: Mapping[str, object]) -> str | list[str] | None:
    if value is None:
        return None

    multiple = bool(mapping_options.get("multiple"))
    people: list[object]
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        people = list(value)
    else:
        people = [value]

    person_ids = [
        person_id for person in people if (person_id := _extract_person_id(person)) is not None
    ]
    if multiple:
        return person_ids
    return person_ids[0] if person_ids else None


def _extract_person_id(person: object) -> str | None:
    if isinstance(person, str):
        return person or None
    if isinstance(person, Mapping):
        for key in ("id", "user_id", "open_id", "email", "name"):
            candidate = person.get(key)
            if isinstance(candidate, str) and candidate:
                return candidate
    return None


def _convert_date(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _to_utc(value).isoformat()
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=UTC).isoformat()
    if isinstance(value, Mapping):
        for key in ("timestamp", "value", "date", "text"):
            candidate = value.get(key)
            converted = _convert_date(candidate)
            if converted is not None:
                return converted
        return None
    if isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
        return _to_utc(parsed).isoformat()
    return str(value)


def _convert_enum(value: object, mapping_options: Mapping[str, object]) -> str | None:
    if value is None:
        return None
    if isinstance(value, Mapping):
        for key in ("name", "text", "label", "id", "value"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate:
                value = candidate
                break
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        values = [item for item in (_convert_enum(item, mapping_options) for item in value) if item]
        return ",".join(values) if values else None
    text = str(value)
    value_map = mapping_options.get("value_map")
    if isinstance(value_map, Mapping):
        mapped = value_map.get(text)
        if isinstance(mapped, str) and mapped:
            return mapped
    return text


def _converter_matches_type(converter: str, actual_type: str) -> bool:
    if converter == "text":
        return actual_type in _SUPPORTED_TEXT_TYPES
    if converter == "person":
        return actual_type in _SUPPORTED_PERSON_TYPES
    if converter == "date":
        return actual_type in _SUPPORTED_DATE_TYPES
    if converter == "enum":
        return actual_type in _SUPPORTED_ENUM_TYPES
    return True


def _to_utc(value: datetime) -> datetime:
    return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)


def _deduplicate(values: Sequence[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped
