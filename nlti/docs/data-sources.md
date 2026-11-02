# Procurement data sources

The source registry is intentionally empty until an administrator has evaluated a source. Before activating a source, record:

- source owner and official URL;
- terms URL, date reviewed, and whether reuse is explicitly permitted;
- approved access method (manual, API, feed, or download);
- polling frequency and published rate limits, if relevant;
- fields collected, source timestamp, and deduplication/reference key;
- correction, retention, and removal process.

The registry only returns sources with `is_active=true`, a terms review timestamp, and explicit `permitted_reuse=true`. The first milestone does not fetch or scrape source pages. Tender records retain their official source URL/name and collection timestamp.

Do not bypass logins, CAPTCHAs, rate limits, paywalls, or technical access controls. Do not imply that a source is complete or continuously monitored. Clearly distinguish source facts from NLTI-generated analysis.

Broad geography labels seeded by NLTI are filter buckets, not authoritative boundaries. Do not load spatial files until the boundary source, licence, CRS, update process, and accuracy are reviewed.
