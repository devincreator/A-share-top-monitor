# V113 Free Historical Market Breadth Recovery

## Problem
Historical market breadth still lacks certified historical stock membership and suspension information.
The first free per-day stock source returned HTTP 429 for all September and October 2026
requests. The substitute daily-public-summary route provided 14 of 31 dates but does
not establish security-level completeness. A second archive returned HTTP 403.

## Goal
Recover the frozen 2022-02-23 through 2026-10-21 market breadth research date set
from independent free sources. Preserve original bytes, source URLs, SHA256, observed
scope and per-date validity. Do not misrepresent market summaries as original stocks.

## Pass Criteria
Full V113 PASS requires >=98% of the fixed 1,129 reference dates plus verified
historical listing universe and suspension-vs-flat separation. Candidate aggregate
coverage alone does not count as full PASS. There may be PARTIAL results.

## Out of Scope
Changes to production alerts, V101 event labels, historical signal backdating,
invented missing values and automatic trading.

## Approved scope amendment: SH/SZ only (2026-10-26)
The user deferred BSE. Deliver V113-SHSZ, a separate interim research dataset,
using the same 1,129 reference dates and >=98% coverage requirement.
Keep all-A acceptance BLOCKED until the excluded BSE market is explicitly restored.
No retrospective inference of BSE counts. Historical original archived BSE evidence is retained without further collection.
