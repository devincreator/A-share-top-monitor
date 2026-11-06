# Market Breadth (V113 delta)

## ADDED Requirements

### Requirement: Fail closed on source failure
The collector SHALL attempt a bounded sample before bulk extraction, SHALL
log 403/429/date/schema failures and SHALL switch to a different source family
rather than unbounded repeat attempts.

#### Scenario: HTTP 429 from all probe dates
- GIVEN a historical security-level provider reports HTTP 429 for all sample days
- WHEN the collector evaluates bulk eligibility
- THEN it SHALL block this provider for the current batch
- AND it SHALL NOT count any date as valid market breadth data.

### Requirement: Distinct evidence levels
Each trading day SHALL be classified as SECURITY_LEVEL, AGGREGATE_ONLY,
UNVERIFIED or MISSING and SHALL carry source and SHA256 evidence.

#### Scenario: public article lists rise/fall counts
- GIVEN the input contains only aggregate rise/fall counts
- WHEN the coverage calculator runs
- THEN the date SHALL NOT count toward certified individual-security coverage.

### Requirement: Frozen V113 acceptance
V113 SHALL require coverage of at least 98% of the frozen 1,129-date calendar,
no duplicate stock/date identities, verifiable historical listed universe, and
suspension-versus-flat distinction. It SHALL NOT replace absent observations
with zeroes, forward fills, or inferred security data.

#### Scenario: 100% aggregated coverage with no membership information
- GIVEN every date has aggregate data but membership and suspension audits fail
- WHEN acceptance runs
- THEN the result SHALL NOT be PASS.

#### Scenario: 98% original bar coverage without suspension identity
- GIVEN >=98% of days have security bars but suspension scope is unverified
- WHEN acceptance runs
- THEN the result SHALL NOT be PASS.
