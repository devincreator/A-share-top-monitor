# Tasks

- [x] Inventory V113 2026-09 and 2026-10 source attempts.
  Evidence: 39749170758 (0/21 SECURITY_LEVEL), 39749288836 (0/10).
- [x] Preserve partial alternative aggregation evidence.
  Evidence: 39750775772 (14/31 AGGREGATE_ONLY, 17 missing).
- [x] Confirm August 2026 has 21/21 sampled market sessions reconstructed from per-stock bars.
  Evidence: 39743177479.
- [x] Define deterministic V113 acceptance contract and automated tests.
  Evidence: GitHub Actions 39759812906, 10 tests passed, actual frozen data gate PARTIAL (21 security-level dates, 14 aggregate-only dates).
- [ ] Acquire source-verified individual security bars for 2026-09 (21 dates).
- [ ] Acquire source-verified individual security bars for 2026-10 (10 dates).
- [ ] Establish historical A-share listing/delisting membership and suspension
      flags; do not infer absence from missing trading rows.
- [ ] Rebuild whole 1,129-date historical breadth series with >=98% coverage.
- [ ] Cross-validate daily breadth counts with independent sources.
- [ ] Receive PASS from machine-computed data AND universe quality gate.
- [ ] Archive accepted OpenSpec change only after evidence-verified PASS.
