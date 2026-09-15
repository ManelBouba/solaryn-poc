# Deploy SOLARYN to Render

This package is configured for Render as a Python web service.

## Automatic Blueprint deployment

1. Push this repository to GitHub.
2. In Render, choose **New > Blueprint**.
3. Connect the GitHub repository.
4. Render detects `render.yaml` from the repository root.
5. Approve the `solaryn-demo` service.
6. When deployment finishes, open the generated `https://<service>.onrender.com` URL.
7. Health check: `/api/v1/health`.

## Render settings encoded in render.yaml

- Runtime: Python
- Python: 3.12.11
- Region: Frankfurt
- Build: `pip install -r Solaryn_Platform/requirements-lock.txt`
- Start: `cd Solaryn_Platform && uvicorn foundation:create_app --factory --host 0.0.0.0 --port $PORT`
- Health check: `/api/v1/health`
- Plan: Free

## Persistence note

The current foundation stores sites, climate snapshots, and analyses in SQLite under `Solaryn_Platform/workspace/foundation.sqlite3`. Render's default filesystem is ephemeral, so data can be lost on redeploy/restart. This is acceptable for a competition demo. For persistent production storage, use a paid persistent disk or migrate to Render Postgres.
