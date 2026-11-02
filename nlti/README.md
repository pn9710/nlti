# NLTI development guide

NLTI is an early-stage, source-attributed procurement intelligence application. It contains a FastAPI/Python API, SQLAlchemy models and Alembic migrations, PostgreSQL/PostGIS data store, and a Next.js/React/TypeScript/Tailwind dashboard. It includes reviewed-source ingestion, human-reviewed document extraction, contractor verification and workspace features, and verified public outcome coverage. Matching remains deterministic and explainable. No real procurement source is configured by default.

## Run with Docker Compose

Requirements: Docker Desktop / Docker Compose v2.

1. From this directory, copy `.env.example` to `.env`.
2. Set `POSTGRES_PASSWORD` to a URL-safe local password and `NLTI_SECRET_KEY` to a random value of at least 32 characters. Do not commit `.env`.
3. Start all services:

   ```bash
   docker compose up --build
   ```

Compose starts PostGIS, applies Alembic migrations, seeds reference geography labels, then starts the API and frontend.

- Dashboard: <http://localhost:3000>
- API health: <http://localhost:8000/health>
- Interactive API and OpenAPI schema: <http://localhost:8000/docs>

The database begins without real tenders or registered procurement sources. To create an admin, set environment variables for the one-time process and pass them only to the API container:

```bash
NLTI_ADMIN_EMAIL=admin@example.ca NLTI_ADMIN_PASSWORD='use-a-unique-password-of-at-least-16-chars' \
   docker compose exec -e NLTI_ADMIN_EMAIL -e NLTI_ADMIN_PASSWORD api python -m nlti.admin
```

Admin registration is not public.

## Run the API without Docker

Python 3.11+ and PostgreSQL/PostGIS are recommended. SQLite is useful for tests and local smoke checks; it stores boundary data as JSON rather than a spatial geometry.

```bash
cd nlti
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
export DATABASE_URL='sqlite:///./nlti.db'
alembic upgrade head
python -m nlti.seed
uvicorn nlti.api.main:app --reload
```

In another terminal:

```powershell
cd frontend
npm ci
npm run dev
```

The frontend defaults to `http://localhost:8000` for the API. Set `NEXT_PUBLIC_NLTI_API_URL` if the API runs elsewhere. The API CORS allowlist is configured by `NLTI_ALLOWED_ORIGINS`.

Run backend tests and lint from the `nlti/` directory with `pytest` and `ruff check nlti tests migrations`. Run frontend checks from `nlti/frontend/` with `npm run lint` and `npm run build`.

## Workflow notes

- Register a procurement source only after its owner, terms, reuse permission, access method, update cadence, and access/rate-limit notes have been reviewed. The dashboard's manual batch importer accepts source-attributed records and explicit archive references; it never fetches a source page.
- Public PDF and UTF-8 text uploads are limited to 10 MB and stored under `NLTI_DOCUMENT_STORE` (a persistent Compose volume by default). A deterministic labeled-field parser creates an unverified draft. An administrator must inspect the original and approve or reject it before publication.
- Contractor email verification links are shown in local development. Production verification requires `NLTI_SMTP_HOST` and `NLTI_SMTP_SENDER`; configure credentials and TLS for the chosen mail provider. Tokens are hashed, expire after 30 minutes, and are single-use.
- Outcome records include public status, source reference, publication date, verification method, and provenance only. Award amounts and bidder identities are intentionally not collected. Coverage reports disclose the denominator and missing outcomes.

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
