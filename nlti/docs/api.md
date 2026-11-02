# API reference

The canonical interactive OpenAPI specification is served by FastAPI at `/docs` (JSON: `/openapi.json`). API routes currently use synchronous SQLAlchemy sessions and JSON request/response bodies.

## Public reads

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Database-backed service health check |
| `GET` | `/summary` | Database counts for upcoming/history notices and reviewed sources |
| `GET` | `/geographies` | Province/region reference hierarchy |
| `GET` | `/sources` | Sources approved for public display |
| `GET` | `/tenders` | Active source-attributed tender records |
| `GET` | `/tenders/upcoming` | Active `planned`/`open` notices with a closing date today or later |
| `GET` | `/tenders/historical` | Past-dated or `closed`/`awarded`/`cancelled` notices |
| `GET` | `/outcomes` | Independently verified public outcomes with provenance |
| `GET` | `/history/coverage` | Eligible historical notice count, verified coverage, and missingness |

Tender reads accept `q`, `region`, `trade`, `status`, `limit` (1–100, default 50), and `offset`. Use `include_demo=true` only when intentionally testing the fictional examples. Demo rows are excluded from public reads, dashboard counts, and matching otherwise.

## Authentication and contractor data

- `POST /auth/register` creates a contractor account and an initially unverified profile.
- `POST /auth/token` accepts `{ "email": "...", "password": "..." }` and returns a short-lived bearer token.
- `POST /auth/verification` sends a single-use email link (or returns a local development link); requests are throttled.
- `POST /auth/verify-email` consumes the one-time token. Tokens expire after 30 minutes.
- `GET /auth/me` returns the authenticated account.
- `GET/PATCH /contractors/me` reads or updates the requesting contractor's own profile.
- `GET/PUT /contractors/me/notifications` reads or changes explicit in-app alert preferences and score threshold.
- `GET /notifications` and `POST /notifications/{id}/read` are contractor-scoped.
- `POST /matches/{contractor_id}` screens upcoming active notices only. Production contractor access requires verified email; results are not eligibility decisions.
- `GET /contractors` returns the requesting contractor's profile; admins can list all profiles.

Send tokens using `Authorization: Bearer <access_token>`. Public registration cannot create admins. Provision the initial administrator through the documented local CLI command.

## Admin writes

- `POST /tenders` creates a tender, rejecting duplicate source references.
- `PATCH /tenders/{id}?reason=...` corrects a tender and records before/after snapshots.
- `POST /tenders/{id}/archive?reason=...` archives without deleting history; `GET /tenders/{id}/revisions` returns the admin audit trail.
- `POST /sources` creates a source-registry record. Activation requires reviewed terms, explicit reuse permission, an update cadence, and access/rate-limit notes.
- `POST /sources/{id}/ingest` accepts manually retrieved records, deduplicates by source reference, tracks retrieval time, and only archives explicitly named references.
- `POST /sources/{id}/checks` and `GET /sources/{id}/runs` record source health and import runs.
- `POST /contractors` is reserved for admins.
- `GET /accounts` and `POST /accounts/{id}/verify` are admin-only account review operations.
- `POST /tenders/{id}/outcome` records an independently verified public outcome for a historical notice.

## Human-reviewed documents

- `POST /documents` accepts multipart `source_id`, `source_url`, and a PDF or UTF-8 text file up to 10 MB. The source must be active and reviewed. Files are hash-deduplicated and stored in `NLTI_DOCUMENT_STORE`.
- A deterministic labeled-field parser records its version, field-level confidence, and proposed values as an unverified draft. It does not use a model or fetch URLs.
- Admins can list drafts with `GET /documents?status=needs_review`, retrieve originals through `GET /documents/{id}/file`, and approve or reject through `POST /documents/{id}/review`. Approval requires reviewed tender fields and creates a canonical tender; rejected or unreviewed fields are never public.

## Verified outcomes

- `POST /tenders/{id}/outcome` records a public outcome only for historical notices and requires an approved source, official reference/URL, verification method, and admin identity.
- Outcome fields intentionally exclude award amounts and bidder identities. `GET /outcomes` returns only outcomes whose tender and source remain active and public.
- `GET /history/coverage` reports the denominator, verified count, missing count, and methodology. It is not a completeness or forecast claim.

No source scraper or connector is enabled by default. A lawful source must be reviewed and configured before ingestion. Production email delivery requires SMTP configuration; MFA, account recovery, and hardened production session handling remain deployment work.
