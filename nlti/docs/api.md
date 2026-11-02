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

Tender reads accept `q`, `region`, `trade`, `status`, `limit` (1–100, default 50), and `offset`. Use `include_demo=true` only when intentionally testing the fictional examples. Demo rows are excluded from public reads, dashboard counts, and matching otherwise.

## Authentication and contractor data

- `POST /auth/register` creates a contractor account and an initially unverified profile.
- `POST /auth/token` accepts `{ "email": "...", "password": "..." }` and returns a short-lived bearer token.
- `GET /auth/me` returns the authenticated account.
- `GET /contractors` returns the requesting contractor's profile; admins can list all profiles.
- `POST /matches/{contractor_id}` computes explainable screening results for that account's own profile. Admins can request any contractor's matches.

Send tokens using `Authorization: Bearer <access_token>`. Public registration cannot create admins. Provision the initial administrator through the documented local CLI command.

## Admin writes

- `POST /tenders` creates a tender, rejecting duplicate source references.
- `POST /sources` creates a source-registry record. A source can be public only when its terms URL has been reviewed and reuse is explicitly permitted.
- `POST /contractors` is reserved for admins.

Tender/source updates, document uploads, source scraping, tender awards, and production identity management are not implemented yet.
