# Tasks

- [x] Inventory V113 2026-09 and 2026-10 source attempts.
  Evidence: 39749170758 (0/21 SECURITY_LEVEL), 39749288836 (0/10).
- [x] Preserve partial alternative aggregation evidence.
  Evidence: 39750775772 (14/31 AGGREGATE_ONLY, 17 missing).
- [x] Confirm August 2026 has 21/21 sampled market sessions reconstructed from per-stock bars.
  Evidence: 39743177479.
- [x] Define deterministic V113 acceptance contract and automated tests.
  Evidence: GitHub Actions 39759812906, 10 tests passed, actual frozen data gate PARTIAL (21 security-level dates, 14 aggregate-only dates).
- [ ] Acquire source-verified individual security bars for 2026-09 (21 dates). Full BaoStock 24-shard source run 39895352257 initiated; **not complete until artifact audit passes**.
- [ ] Acquire source-verified individual security bars for 2026-10 (10 dates). Included in source run 39895352257; independent BSE source run 39896246528 initiated.
- [ ] Establish historical A-share listing/delisting membership and suspension
      flags; do not infer absence from missing trading rows.
- [ ] Rebuild whole 1,129-date historical breadth series with >=98% coverage.
- [ ] Cross-validate daily breadth counts with independent sources.
- [ ] Receive PASS from machine-computed data AND universe quality gate.
- [ ] Archive accepted OpenSpec change only after evidence-verified PASS.

## 2026-10-23 full-rebuild evidence
- [x] Pilot BaoStock stock bars 24/24 symbols successfully downloaded (run 39895225084), zero calendar gaps within pilot.
- [x] Historical BaoStock SH 2,467 + SZ 3,097 type-1 entries; BSE absent (run 39895018158).
- [x] BSE current 353 securities + 248 old/new code mappings + 3 secondary transfers merged to 358 candidate identities; not yet PIT-certified (run 39895931145).
- [x] Build SH/SZ 24-shard downloader and independent complete calendar audit; completion pending source runs.
- [x] Build BJ eight-shard downloader and independent code and suspension gap audit; completion pending source runs.
- [x] Implement MA20/60/120 and 60/252-day high-low breadth with past-only history; syntax and tests checked (run 39896880333).
- [ ] Verify SH/SZ all-source shards artifact, count failures and issue list, and publish acceptance.
- [ ] Verify BSE source shards, repair errors, audit suspended-days vs no-bars, and publish acceptance.
- [ ] Run combined 1,129-day full-A breadth validator; no formal PASS before all checks.
