from __future__ import annotations

from tests.integration.admin._helpers import make_admin_client


def test_admin_schedule_get_update_and_validate_flow() -> None:
    client, _, _ = make_admin_client()

    get_response = client.get("/api/v1/admin/project/schedule")
    assert get_response.status_code == 200
    schedule = get_response.json()["data"]
    assert "cron_expression" in schedule
    assert "timezone" in schedule
    assert "enabled" in schedule
    assert "misfire_policy" in schedule
    assert "revision" in schedule

    update_response = client.put(
        "/api/v1/admin/project/schedule",
        json={
            "cron_expression": "0 9 * * 1",
            "timezone": "Asia/Shanghai",
            "enabled": True,
            "misfire_policy": "fire_once",
            "revision": schedule["revision"],
        },
    )
    assert update_response.status_code == 200
    updated_schedule = update_response.json()["data"]
    assert updated_schedule["enabled"] is True
    assert updated_schedule["revision"] == schedule["revision"] + 1

    validate_response = client.post(
        "/api/v1/admin/project/schedule/validate",
        json={
            "cron_expression": "0 9 * * 1",
            "timezone": "Asia/Shanghai",
            "enabled": True,
            "misfire_policy": "fire_once",
            "revision": updated_schedule["revision"],
        },
    )
    assert validate_response.status_code == 200
    validation = validate_response.json()["data"]
    assert len(validation["next_fire_times"]) == 3
