# Procurement data sources

The source registry is intentionally empty until an administrator has evaluated a source. Before activating a source, record:

- source owner and official URL;
- terms URL, date reviewed, and whether reuse is explicitly permitted;
- approved access method (manual, API, feed, or download);
- polling frequency and published rate limits, if relevant;
- fields collected, source timestamp, and deduplication/reference key;
- correction, retention, and removal process.

The registry only returns sources with `is_active=true`, a terms review timestamp, explicit `permitted_reuse=true`, a documented update cadence, and access/rate-limit notes. The application does not fetch or scrape source pages. Admins can import records retrieved manually from an approved source; every import records source references and retrieval time, updates corrections in place with a before/after revision, and archives only references explicitly named by the source operator.

Source import runs and health checks are recorded for operational review. The API is a connector boundary, not a preconfigured connector: add a source-specific connector only after its lawful access and reuse rules have been verified. No official sources or tender records are configured by default.

Do not bypass logins, CAPTCHAs, rate limits, paywalls, or technical access controls. Do not imply that a source is complete or continuously monitored. Clearly distinguish source facts from NLTI-generated analysis.

Broad geography labels seeded by NLTI are filter buckets, not authoritative boundaries. Do not load spatial files until the boundary source, licence, CRS, update process, and accuracy are reviewed.
