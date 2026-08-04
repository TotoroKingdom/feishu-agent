from __future__ import annotations

from ._helpers import make_admin_client


def test_llm_model_config_and_connectivity_job() -> None:
    client, _, _ = make_admin_client()

    model_response = client.get("/api/v1/admin/model-config")
    assert model_response.status_code == 200
    model = model_response.json()["data"]

    patch_response = client.patch(
        "/api/v1/admin/model-config",
        json={
            "base_url": "https://api.openai.example/v1",
            "model": "gpt-4.1-mini",
            "temperature": 0.1,
            "timeout_seconds": 45,
            "max_retries": 3,
            "stream": True,
            "revision": model["revision"],
        },
    )
    assert patch_response.status_code == 200
    updated_model = patch_response.json()["data"]
    assert updated_model["model"] == "gpt-4.1-mini"

    job_response = client.post("/api/v1/admin/project/connectivity-test")
    assert job_response.status_code == 202
    job = job_response.json()["data"]
    assert job["result_summary"]["llm"]["status"] in {"ok", "degraded", "failed"}
