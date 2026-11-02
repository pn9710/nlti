# NLTI development guide

NLTI is an early-stage, source-attributed procurement intelligence application. It contains a FastAPI/Python API, SQLAlchemy models and Alembic migrations, PostgreSQL/PostGIS data store, and a Next.js/React/TypeScript/Tailwind dashboard. Matching remains deterministic and explainable. No real procurement source is configured by default.

## Run with Docker Compose

Requirements: Docker Desktop / Docker Compose v2.

1. From this directory, copy `.env.example` to `.env`.
2. Set `POSTGRES_PASSWORD` to a URL-safe, local development password. Set `DATABASE_URL` to use the same password. Set `NLTI_SECRET_KEY` to a unique random value of at least 32 characters. Do not commit `.env`.
3. Start all services:

   ```powershell
   docker compose up --build
   ```

Compose starts PostGIS, applies Alembic migrations, seeds reference geography labels, then starts the API and frontend.

- Dashboard: <http://localhost:3000>
- API health: <http://localhost:8000/health>
- Interactive API and OpenAPI schema: <http://localhost:8000/docs>

The database begins without real tenders or registered procurement sources. To create an admin, set environment variables for the one-time process and pass them only to the API container:

```powershell
$env:NLTI_ADMIN_EMAIL = "admin@example.ca"
$env:NLTI_ADMIN_PASSWORD = "use-a-unique-password-of-at-least-16-chars"
docker compose exec -e NLTI_ADMIN_EMAIL -e NLTI_ADMIN_PASSWORD api python -m nlti.admin
Remove-Item Env:NLTI_ADMIN_EMAIL, Env:NLTI_ADMIN_PASSWORD
```

Admin registration is not public.

## Run the API without Docker

Python 3.11+ and PostgreSQL/PostGIS are recommended. SQLite is useful for tests and local smoke checks; it stores boundary data as JSON rather than a spatial geometry.

```powershell
cd nlti
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
$env:DATABASE_URL = "sqlite:///./nlti.db"
alembic upgrade head
python -m nlti.seed
uvicorn nlti.api.main:app --reload
```

In another terminal:

```powershell
cd frontend
npm install
npm run dev
```

The frontend defaults to `http://localhost:8000` for the API. Set `NEXT_PUBLIC_NLTI_API_URL` if the API runs elsewhere. The API CORS allowlist is configured by `NLTI_ALLOWED_ORIGINS`.

Run backend tests from this directory with `pytest`.

## Geographic and tender data

`python -m nlti.seed` adds only coarse filter labels (the province and broad regions). They are not authoritative administrative boundaries; no geometry or official source is populated. PostGIS stores optional EPSG:4326 multipolygons once a licensed, source-attributed boundary dataset has been selected.

Tender lists are separated by a known closing date and published notice status. Upcoming notices need a published closing date on or after today and a `planned` or `open` status. Historical notices have a past closing date or a `closed`, `awarded`, or `cancelled` status. Records without a closing date are not described as upcoming.

Fictional seed records can be added explicitly with `python -m nlti.seed --demo`. They are clearly marked and hidden from public tender queries and dashboard totals unless an API caller explicitly passes `include_demo=true`.

## Documentation

- [API reference](docs/api.md)
- [Architecture and extraction design](docs/architecture.md)
- [Procurement source policy](docs/data-sources.md)
- [Security baseline and deployment gaps](docs/security.md)
- [Project roadmap](../PROJECT_ROADMAP.md)
