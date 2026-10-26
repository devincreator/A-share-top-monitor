# Market Breadth

- Target observations are the frozen V111 1,129 reference dates.
- Original stock-bar-based breadth and public article aggregates are separate classes.
- Valid traded bars do not establish suspended-security universe automatically.
- V113 PASS requires >=98% target coverage, historical stock membership,
  correct suspension-vs-flat handling and zero duplicate stock/date keys.

## V113 Shanghai/Shenzhen interim scope (2026-10-26)
- User explicitly deferred Beijing Stock Exchange. Current research deliverable is SH+SZ only.
- The frozen 1,129-date calendar and 98% day coverage target remain unchanged.
- SHSZ_RESEARCH_PASS must not be reported as all-A-share or V113 full-universe PASS.
- Historical listed SH/SZ membership, delisted stocks, suspension vs flat, duplicate-free original bar evidence and independent source reconciliation remain required for a formal scoped audit.
- BSE source files and earlier research records are preserved but excluded from SHSZ pipeline, joins, metrics and gates. Do not launch more BSE jobs for this change.

## Independent SH/SZ historical issuer population (2026-10-26)

- Compare historical A-share **issuer** counts against official A-share
  totals, not totals including B-only listed companies.
- Preserve source URLs and monthly cutoffs for every benchmark.
- If a dated source-list and a retrospective IPO/outDate interval disagree,
  report exact codes, date, original status, and source SHA256; no automatic
  deletion, addition, or inferred halt.
- A numerical issuer count match alone does not certify security-identity
  membership; historical listed and suspended stock status must remain
  auditable independently.
