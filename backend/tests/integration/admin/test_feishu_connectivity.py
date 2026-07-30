from __future__ import annotations

from ._helpers import make_admin_client


def test_feishu_resource_connectivity_and_field_mappings() -> None:
    client, _, _ = make_admin_client()

    resource_response = client.post(
        "/api/v1/admin/project/feishu-resources",
        json={
            "resource_type": "bitable",
            "external_id": "tbl_123",
            "name": "Tasks",
            "enabled": True,
            "schema_hash": None,
        },
    )
    assert resource_response.status_code == 201
    resource = resource_response.json()["data"]

    schema_response = client.post(
        f"/api/v1/admin/project/feishu-resources/{resource['id']}/schema",
        json={
            "schema_hash": "schema-hash-1",
            "revision": resource["revision"],
            "fields": [{"id": "fld_1", "name": "Task"}],
        },
    )
    assert schema_response.status_code == 200
    updated_resource = schema_response.json()["data"]
    assert updated_resource["schema_hash"] == "schema-hash-1"

    mappings_response = client.put(
        f"/api/v1/admin/project/feishu-resources/{resource['id']}/field-mappings",
        json={
            "schema_hash": "schema-hash-1",
            "revision": updated_resource["revision"],
            "mappings": [
                {
                    "logical_field": "task_id",
                    "external_field_id": "fld_1",
                    "external_field_name": "Task",
                    "external_field_type": "text",
                    "converter": "text",
                    "required_level": "critical",
                    "mapping_options": {},
                    "enabled": True,
                }
            ],
        },
    )
    assert mappings_response.status_code == 200
    assert mappings_response.json()["data"]["mappings"][0]["logical_field"] == "task_id"

    connectivity_response = client.post(
        f"/api/v1/admin/project/feishu-resources/{resource['id']}/connectivity-test"
    )
    assert connectivity_response.status_code == 200
    connectivity = connectivity_response.json()["data"]
    assert connectivity["resource_id"] == resource["id"]
    assert connectivity["status"] in {"ok", "degraded"}

