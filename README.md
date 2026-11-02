# NLTI — Newfoundland and Labrador Tender Intelligence

NLTI is a source-attributed public procurement intelligence application for Newfoundland and Labrador construction. It includes a FastAPI API, SQLAlchemy/Alembic data layer, PostgreSQL/PostGIS development environment, Next.js/TypeScript frontend, reviewed-source ingestion, human-reviewed document extraction, contractor account/workspace features, and verified public outcome coverage.

The supplied starter project is in [`nlti/`](nlti/). Start with its [development guide](nlti/README.md), [API reference](nlti/docs/api.md), [roadmap](PROJECT_ROADMAP.md), [data-source policy](nlti/docs/data-sources.md), and [security baseline](nlti/docs/security.md).

No procurement sources are connected and no real tender or outcome data is seeded by default. Source onboarding remains manual until access rules and reuse permissions are reviewed; the app does not scrape or bypass source controls. Demo records are fictional, explicitly labelled, and excluded from public listings unless requested with `include_demo=true`.
