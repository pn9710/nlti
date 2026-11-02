# NLTI — Newfoundland and Labrador Tender Intelligence

NLTI is a source-attributed public procurement intelligence foundation for Newfoundland and Labrador construction. Milestone 1 includes a FastAPI API, SQLAlchemy/Alembic data layer, PostgreSQL/PostGIS development environment, Next.js/TypeScript frontend, contractor account foundation, source-reviewed public tender listings, and explainable contractor-to-tender matching.

The supplied starter project is in [`nlti/`](nlti/). Start with its [development guide](nlti/README.md), [API reference](nlti/docs/api.md), [roadmap](PROJECT_ROADMAP.md), [data-source policy](nlti/docs/data-sources.md), and [security baseline](nlti/docs/security.md).

No procurement sources are connected and no real tender data is seeded by default. Demo records are fictional, explicitly labelled, and excluded from public listings unless requested with `include_demo=true`.
