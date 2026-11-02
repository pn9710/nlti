# Architecture

## Milestone 1 running system

- **API:** FastAPI provides public tender, dashboard summary, geography, and approved-source reads; account, contractor, matching, and admin write routes are explicitly separated.
- **Database:** SQLAlchemy 2 models and Alembic revisions target PostgreSQL with PostGIS. Tender and source records preserve provenance. Geography supports a province/region hierarchy and an optional EPSG:4326 multipolygon. SQLite is supported for tests, where boundary geometry is JSON.
- **Web:** Next.js App Router, React, TypeScript, and Tailwind render a responsive procurement overview. Public dashboard totals come from database queries; no sample values are hard-coded.
- **Matching:** The existing LangGraph wrapper calls a deterministic, explainable screening calculation. Scores are not eligibility determinations, award predictions, or bid-price guidance.
- **Acquisition:** No connectors or scrapers are enabled. Procurement source metadata is reviewed before a source can appear in the public registry.
- **Source operations:** Admin-only manual imports deduplicate by source reference, preserve retrieval times, record correction snapshots, archive only explicitly withdrawn references, and track health/run history.
- **Document review:** Admins can upload public PDF/text files for hash-deduplicated local storage. A deterministic labeled-field parser records proposed fields and per-field confidence as a draft. Human approval is required before creating a public tender.
- **Contractor workspace:** Contractors can update their own profile and opt into in-app notices with a minimum screening score. Production matching/notifications require email verification; notices cover upcoming opportunities only.
- **Historical outcomes:** Admins can record independently verified public status with source provenance. Coverage displays missingness; no award prices or bidder identities are collected.

## Geography and notice lifecycle

Region labels currently provide broad search buckets only. They are not legally authoritative boundaries, and all boundary geometry begins as `NULL`. Load licensed, source-attributed boundary data only after identifying the authoritative dataset and its permitted use.

The upcoming feed requires a published closing date on or after the current date and a `planned` or `open` status. Historical notices include a past closing date or a `closed`, `awarded`, or `cancelled` state. Records with no closing date are not silently presented as upcoming. Fictional demo rows are filtered from public queries and totals by default.

## Document-extraction architecture

Extraction uses a deterministic parser for explicitly labeled text only; there is no model provider or automatic document fetching. Each permitted public document moves through:

1. Source registration and access/retention review.
2. Retrieval with an immutable source URL, fetch time, checksum, and content type.
3. Text extraction and proposed fields with extractor version, prompt version (`not-used` for the local parser), per-field confidence, and warnings.
4. An unverified draft state that is not visible as a canonical tender.
5. Human review against the original notice before any accepted values update public tender data.

The source PDF remains authoritative. Parser output must never invent a deadline, qualification, value, award, or eligibility result. Do not ingest private contractor documents. The local queue has admin-only document access and persistent storage, but production retention/deletion policy and any future model provider require separate review.

## Deferred responsibilities

- Procurement Scout: add source-specific connectors only after lawful access, reuse rights, update method, and limits are reviewed.
- Identity: add MFA, account recovery, and hardened production browser sessions before customer deployment.
- Tender Analyst: any future model-assisted extraction must keep the unverified-draft and human-approval boundary.
- Opportunity Matcher: improve ranking only with visible reasons and user controls; never present results as eligibility or award predictions.
- Cost and market intelligence: require independently verified lawful public data; never infer or disclose confidential competing bids.
- Compliance assistance: display listed requirements as unverified reminders, not legal advice or an eligibility decision.
