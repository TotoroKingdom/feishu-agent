# feishu-agent

## Quick Start

- `docker compose config`
- `docker compose up --build`
- Open `https://localhost:8443`
- Health check: `http://localhost:8080/health`
- Readiness check: `http://localhost:8080/ready`

## Local Commands

- `python scripts/full_ci_local.py`
- `python scripts/recovery_drill.py`
- `python scripts/sbom.py`
- `python scripts/dependency_scan.py`
- `python scripts/secret_scan.py`

## Deployment Notes

- `backend` and `frontend` are internal services in Compose.
- `nginx` is the only public entrypoint and denies `/internal/*`.
- `APP_PROFILE=production` must not use fake providers.
- `BACKEND_BASE_URL` defaults to `http://127.0.0.1:8000` locally and is overridden to `http://backend:8000` in Compose.
