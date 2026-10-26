# Assumed Historical Release Lag

- Daily stock/index bars from session T are available no earlier than T+1 trading session.
- Financing for T is available no earlier than T+2 trading sessions.
- Weekly and monthly inputs require a completed preceding period.
- Financial announcements enter after actual disclosure date +1 trading session.
- These are research assumptions, not certified historical publication timestamps.

## V113 SH/SZ historical source-publication certification (2026-10-26)

- **Mechanically verified assumed lag**: a market-session T stock bar may
  contribute to a next-session T+1 decision, never to T or earlier.
  Trading calendar and decision timestamps must be explicit.
- **Not certified by a retrospective download**: obtaining a T bar or a
  dated membership result in 2026 does NOT prove what the source published
  at the actual historical decision timestamp T+1.
- A separate **historical actual-PIT PASS** requires contemporaneous archived
  source snapshots with independently verifiable capture/publication timestamps
  and an immutable source-version chain. Without that, mark
  HISTORICAL_ACTUAL_PIT_BLOCKED, even if no-future timing checks pass.
- Monthly issuer statistics published after a given month may audit the
  historical universe, but may NOT be used as a predictor as of an earlier
  decision date.
- The decision-date feature builder must use historical observations
  T-1 or older and may not leak IPO/OUT metadata revisions or T+1 stock bars
  into T decisions. No SH/SZ output may be promoted based solely on a lag test.
