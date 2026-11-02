# NLTI project roadmap

## Milestone 1 — Provincial construction intelligence foundation

**Status: backend verified; frontend build and PostGIS/Compose runtime verification remain pending.**

- [x] Preserve the FastAPI, SQLAlchemy, matching, and LangGraph starter.
- [x] Add versioned Alembic migrations and a PostgreSQL/PostGIS development stack.
- [x] Add province/region hierarchy and nullable EPSG:4326 multipolygon storage. No official boundaries are loaded.
- [x] Add procurement-source registry fields for owner, official URL, access method, terms review, reuse permission, and activation.
- [x] Separate upcoming notices from historical notices; expose source-attributed search and filters.
- [x] Add public dashboard totals sourced from database counts and clear empty states.
- [x] Add contractor registration, password hashing, short-lived bearer tokens, and contractor-scoped profile/matching access.
- [x] Require admin authorization for procurement-source and tender writes; make initial admin creation an explicit CLI operation.
- [x] Add a Next.js/React/TypeScript/Tailwind dashboard and Docker Compose development environment.
- [x] Add API, data-policy, security, architecture, and development documentation; keep fictional demo records opt-in.
- [x] Document the future public-document extraction flow, provenance, confidence, and human-review boundary.
- [x] Keep source acquisition manual; no scraper, AI extraction service, award statistics, or bid-price data is fabricated.
- [ ] Run backend/frontend checks and exercise the app in the configured Codespace or a machine with Python, Node.js, and Docker available.

## Milestone 2 — Lawful source onboarding

- Verify each official procurement source's access rules, reuse rights, update method, and rate limits before activation.
- Add one reviewed connector at a time, retaining source references and retrieval timestamps.
- Add deduplication, corrections, archival, and per-source health monitoring.
- Do not bypass authentication, CAPTCHA, rate limits, paywalls, or technical controls.

## Milestone 3 — Human-reviewed document extraction

- Add a public-document intake and extraction queue with hashes, provenance, model/prompt versions, and field-level confidence.
- Keep extracted values in an unverified draft until a human checks the original notice.
- Never infer or publish undisclosed bids, awards, pricing, or contractor eligibility.

## Milestone 4 — Contractor opportunity workspace

- Add account verification and production identity/security controls.
- Let a contractor maintain its own trades, service areas, equipment, qualifications, and capacity.
- Extend transparent screening and notifications only with explicit user controls and no bid coordination.

## Milestone 5 — Historical intelligence

- Add independently verified public award outcomes and tender history where lawful data is available.
- Document coverage, missingness, corrections, and methodology before producing market summaries.
- Do not treat incomplete public records as a complete market or guaranteed price/award forecast.
