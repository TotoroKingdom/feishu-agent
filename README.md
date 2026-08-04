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

## Artifact Policy

- Repeatable command output is written to
  `artifacts/generated/<run-id>/<command>/`; this tree is ignored by Git.
- Set `FEISHU_AGENT_ARTIFACT_RUN_ID` to a safe run identifier when several
  commands must share one output directory. Otherwise, each process creates a
  timestamped run identifier.
- Evidence that must be reviewed and versioned belongs in a separate
  `artifacts/evidence/<timestamp>-<scope>/` directory and must contain only
  redacted summaries. Historical tracked artifacts remain preserved, but
  commands no longer use them as output targets.
- Setuptools metadata is generated below `backend/.build-metadata/`, which is
  ignored, instead of overwriting tracked `backend/*.egg-info` files.
- TypeScript incremental metadata is generated below the ignored
  `frontend/.next/cache/` tree instead of overwriting tracked
  `frontend/tsconfig.tsbuildinfo`.

## Deployment Notes

- `backend` and `frontend` are internal services in Compose.
- `nginx` is the only public entrypoint and denies `/internal/*`.
- `APP_PROFILE=production` must not use fake providers.
- `BACKEND_BASE_URL` defaults to `http://127.0.0.1:8000` locally and is overridden to `http://backend:8000` in Compose.
