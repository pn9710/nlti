# Security baseline and deployment gaps

## Implemented foundation

- Account passwords are stored using Argon2id through `pwdlib`; registration cannot choose an admin role.
- Bearer access tokens are signed with HS256, issued for 45 minutes, and checked against the active account row.
- Email verification uses single-use SHA-256 token hashes, 30-minute expiry, and a per-account resend throttle. Local development exposes a verification URL; production uses configured SMTP and blocks contractor matching/notifications until verified.
- A contractor can read only its own profile and request matches only for that profile. Admin operations are separate; an admin must be bootstrapped explicitly with `python -m nlti.admin`.
- Users cannot self-assert verified insurance during signup. Tender and source writes require admin authorization.
- Source URLs use HTTP(S) URL validation. Active sources require reviewed terms, explicit permission to reuse, an update cadence, and access/rate-limit notes.
- Public-document uploads are admin-only, type/size limited, content-hash deduplicated, and stored outside the database. Original document access is admin-only. Proposed fields remain drafts until a human approves them.
- Tender corrections, explicit archival, source runs, document decisions, and outcome verification preserve provenance and actor/timestamps where applicable.
- `.env`, databases, Python virtual environments, and frontend build output are ignored by Git. Compose runs application services as non-root where supported.
- Demo records are opt-in and excluded from public listings and totals by default.

## Required before real customer or production use

- Add MFA, password recovery, a hardened browser session strategy, and edge/API rate limiting before production. Email verification and bounded resend throttling are implemented, but do not replace these controls.
- Deploy behind HTTPS, configure a unique strong `NLTI_SECRET_KEY`, narrowly scope CORS origins, database credentials, backups, audit retention, monitoring, and least-privilege database access.
- Review privacy notices, consent, data retention/deletion, tenant isolation, operational incident response, and applicable provincial/federal requirements.
- Re-test authorization and database migrations against the actual deployment configuration. Do not expose the development admin bootstrap workflow.
- Treat all extracted notice data as unverified until a human confirms it against the original official procurement document.

Never commit `.env`, credentials, API keys, private keys, or customer documents. Do not expose a contractor's private pricing, bid strategy, capacity details, or confidential documents to competitors. NLTI must not coordinate bids or promise awards.
