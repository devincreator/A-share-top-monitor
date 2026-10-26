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

## Shanghai/Shenzhen-only original archive recovery
- BaoStock 24 shards run 39895352257: 5,564 SH/SZ symbols captured, 1,097/1,129 fully observed days, 41 listed-stock-day gaps.
- TDX historical ZIP source https://data.tdx.com.cn/vipdoc/hsjday.zip verified in run 39897910188 (549,908,719 bytes, ZIP SHA256 07aab2f1166a794cebfa380cda058417499c4f74049a5fe36fe029f5c803d400).
- Use TDX SHA-audited raw .day per code as a strictly limited alternate source for listed-date gaps, not a blanket replacement of BaoStock suspension status.
- Recover a gap only when archive code, date, price scale, positive volume/amount and comparison against overlap BaoStock raw close pass.
- Mark unresolved stock-date gaps explicitly. Preserve source divergence as a blocker.
- Final scoped status is distinct from all-A status, which remains excluded/BLOCKED.
