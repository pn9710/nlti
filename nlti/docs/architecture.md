# Architecture

## Milestone 1 running system

- **API:** FastAPI provides public tender, dashboard summary, geography, and approved-source reads; account, contractor, matching, and admin write routes are explicitly separated.
- **Database:** SQLAlchemy 2 models and Alembic revisions target PostgreSQL with PostGIS. Tender and source records preserve provenance. Geography supports a province/region hierarchy and an optional EPSG:4326 multipolygon. SQLite is supported for tests, where boundary geometry is JSON.
- **Web:** Next.js App Router, React, TypeScript, and Tailwind render a responsive procurement overview. Public dashboard totals come from database queries; no sample values are hard-coded.
- **Matching:** The existing LangGraph wrapper calls a deterministic, explainable screening calculation. Scores are not eligibility determinations, award predictions, or bid-price guidance.
- **Acquisition:** No connectors or scrapers are enabled. Procurement source metadata is reviewed before a source can appear in the public registry.

## Geography and notice lifecycle

Region labels currently provide broad search buckets only. They are not legally authoritative boundaries, and all boundary geometry begins as `NULL`. Load licensed, source-attributed boundary data only after identifying the authoritative dataset and its permitted use.

The upcoming feed requires a published closing date on or after the current date and a `planned` or `open` status. Historical notices include a past closing date or a `closed`, `awarded`, or `cancelled` state. Records with no closing date are not silently presented as upcoming. Fictional demo rows are filtered from public queries and totals by default.

## Document-extraction architecture

Extraction is deliberately a design boundary, not a live AI integration in this milestone. When enabled in a later milestone, a permitted public document should move through:

1. Source registration and access/retention review.
2. Retrieval with an immutable source URL, fetch time, checksum, and content type.
3. Text extraction and proposed fields with extractor/model/prompt versions, per-field confidence, and warnings.
4. An unverified draft state that is not visible as a canonical tender.
5. Human review against the original notice before any accepted values update public tender data.

The source PDF remains authoritative. AI output must never invent a deadline, qualification, value, award, or eligibility result. Do not ingest private contractor documents until access controls, retention, and deletion behavior are explicitly implemented. There is no configured model provider, extraction job, or automated source access in the current app.

## Deferred responsibilities

- Procurement Scout: add individual permitted source connectors only after source review.
- Tender Analyst: implement the staged, human-reviewed extraction boundary above.
- Opportunity Matcher: later improve profile-specific ranking with visible reasons and user controls.
- Cost and market intelligence: require independently verified lawful public data; never infer or disclose confidential competing bids.
- Compliance assistance: display listed requirements as unverified reminders, not legal advice or an eligibility decision.
