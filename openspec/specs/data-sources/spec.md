# Data Source Acquisition

- Every recovered historical row MUST retain URL or immutable origin, source date,
  file checksum, unit, and identity/classification.
- Batch extraction MUST be gated by a bounded probe.
- HTTP 403/429, unparseable schema and date mismatch MUST NOT be counted as success.
- No trading signal may be emitted from an unaccepted research data pipeline.
