# Security baseline and deployment gaps

## Implemented foundation

- Account passwords are stored using Argon2id through `pwdlib`; registration cannot choose an admin role.
- Bearer access tokens are signed with HS256, issued for 45 minutes, and checked against the active account row.
- A contractor can read only its own profile and request matches only for that profile. Admin operations are separate; an admin must be bootstrapped explicitly with `python -m nlti.admin`.
- Users cannot self-assert verified insurance during signup. Tender and source writes require admin authorization.
- Source URLs use HTTP(S) URL validation. Active sources require a reviewed terms URL, review timestamp, and explicit permission to reuse.
- `.env`, databases, Python virtual environments, and frontend build output are ignored by Git. Compose runs application services as non-root where supported.
- Demo records are opt-in and excluded from public listings and totals by default.

## Required before real customer or production use

- Replace local bearer-token storage and simple passwords with a reviewed production identity flow, secure cookie/session handling or equivalent controls, account verification, recovery, MFA, and rate limiting.
- Deploy behind HTTPS, configure a unique strong `NLTI_SECRET_KEY`, narrowly scope CORS origins, database credentials, backups, audit retention, monitoring, and least-privilege database access.
- Review privacy notices, consent, data retention/deletion, tenant isolation, operational incident response, and applicable provincial/federal requirements.
- Re-test authorization and database migrations against the actual deployment configuration. Do not expose the development admin bootstrap workflow.
- Treat all extracted notice data as unverified until a human confirms it against the original official procurement document.

Never commit `.env`, credentials, API keys, private keys, or customer documents. Do not expose a contractor's private pricing, bid strategy, capacity details, or confidential documents to competitors. NLTI must not coordinate bids or promise awards.
