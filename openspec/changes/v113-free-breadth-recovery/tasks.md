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
- Deferred, not a gate for SHSZ-only V113: BSE stock source shards and suspension audit (user explicitly postponed BSE).
- Deferred, not a gate for SHSZ-only V113: combined full-A market validator.

## 2026-10-26 user-directed SH/SZ scope only
- [x] User deferred BSE. Exclude BJ from current V113 data/features and validation; preserve its original archives.
- [x] BaoStock 24 stock shards finished: 5,564 symbols, 0 failed symbols; strict SH/SZ audit 1,097/1,129 complete dates and 41 listed-day gaps (run 39897170025).
- [x] Independently download TDX ZIP and verify header/CRC/whole-archive hash and SH/SZ sample bars (run 39897910188).
- [ ] Use original TDX .day only to repair verified missing listed SH/SZ stock-days; do not impute suspended stocks.
- [ ] Re-evaluate the 1,129-date >=98% scoped coverage threshold against actual merged evidence.
- [ ] Investigate independent year/month-end exchange universe mismatch before formal scoped membership certification.
- [ ] Keep V113 all-market acceptance blocked; no Beijing dependence and no production model modification.

## 2026-10-26 dated outDate evidence
- [x] Inventory exactly 41 BaoStock stock/day misses, all at outDate, over 32 distinct trading days, 41 different stocks (run 40254546648).
- [x] Independently audit 339 historical delisted codes: 149 have last observed bars dated on outDate, 41 have last bars before outDate and 149 had no bars inside anchor window (run 40255059928).
- [x] Verify four dated historical listings: delisting-date absent for sample candidates, with control source code tradeStatus=0 (run 40255161569).
- [x] Abandon immediate TDX full-archive re-download after 2026-10-26 source returned invalid 987-byte content; do not retry same blocked source in a loop (run 40254247712).
- [ ] Audit all 32 historical date-specific security lists in eight source batches (run 40255562468).
- [ ] Reconcile all 41 source cases with verifiable ABSENT / SUSPENDED / TRADING statuses and freeze SHSZ-only research daily breadth acceptance (run 40255765013).
- [ ] Validate SHSZ-only full history moving average/new-high/new-low factors (run 40255873584).
- [ ] Independently reconcile historic exchange-end security population before production-grade PIT certification.
