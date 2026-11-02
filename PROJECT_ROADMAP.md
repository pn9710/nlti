# NLTI project roadmap

## Milestone 1 — Provincial construction intelligence foundation

**Status: backend/frontend checks, migrations, and PostGIS/Compose runtime verified.**

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
- [x] Run backend/frontend checks, upgrade SQLite and PostGIS migrations, and exercise the API/frontend through Docker Compose.

## Milestone 2 — Lawful source onboarding

- [ ] Verify each official procurement source's access rules, reuse rights, update method, and rate limits before activation. This requires source-by-source legal/operational review.
- [ ] Implement and enable a source-specific connector only after that source is approved. No connector or source is enabled by default.
- [x] Add an admin-only manual import boundary that retains source references and retrieval timestamps.
- [x] Add source-reference deduplication, correction history, explicit archival, and per-source health/run monitoring.
- Do not bypass authentication, CAPTCHA, rate limits, paywalls, or technical controls.

## Milestone 3 — Human-reviewed document extraction

- [x] Add a public-document intake and review queue with content hashes, provenance, extractor/prompt versions, and field-level confidence. Extraction is deterministic and label-based; no model provider is configured.
- [x] Keep proposed values in an unverified draft until an administrator checks the original and approves it.
- Never infer or publish undisclosed bids, awards, pricing, or contractor eligibility.

## Milestone 4 — Contractor opportunity workspace

- [x] Add single-use, expiring email verification with production SMTP delivery and admin verification support.
- [ ] Add production MFA, account recovery, hardened browser sessions, and edge/API rate limiting before customer deployment.
- [x] Let a contractor maintain its own trades, service areas, equipment, qualifications, and capacity.
- [x] Add opt-in, account-scoped in-app match notifications with a user-selected score threshold and explainable upcoming-only screening.
- Do not coordinate bids or imply qualification, eligibility, or award likelihood.

## Milestone 5 — Historical intelligence

- [x] Add provenance-checked public outcome records and tender history fields without bidder or award-price data.
- [x] Report denominator, verified outcomes, missingness, and methodology. No source outcomes are populated by default.
- Do not treat incomplete public records as a complete market or guaranteed price/award forecast.
