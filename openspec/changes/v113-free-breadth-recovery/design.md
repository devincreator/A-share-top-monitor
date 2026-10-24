# Technical Design

1. Use the fixed V111 000985 observed trading-date anchor; never shrink denominator.
2. Source discovery precedes a bounded three-day probe. If 429, 403, invalid schema,
   or zero accepted dates, cease that route for this run and switch **source family**.
3. A successful GitHub workflow is not the same as data acceptance. Validate
   usable dates separately, using an acceptance report.
4. Store source URL, capture time, raw SHA256, source date, symbol/date duplicates,
   price/previous-close consistency and effective stock population.
5. Types: SECURITY_LEVEL_TRADING_OBSERVATIONS, AGGREGATE_ONLY, UNVERIFIED, MISSING.
   Exclude AGGREGATE_ONLY from membership/suspension certification.
6. Cross-source discrepancies must be visible and must not be silently resolved.
7. Emit candidate and formal gate outcomes separately. Production signals remain blocked.
8. Respect D-1 price, D-2 financing, next-complete-period weekly/monthly and
   disclosure-date+1 trading session release assumptions.
9. Preserve the V112 946 exact plus 183 rounded-bound margin source evidence separately.
10. Use a frozen, deterministic validator in CI. Tests must include deliberate
    false-success, missing-date, and unverified-universe cases.
