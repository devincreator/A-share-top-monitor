# Feature Engineering

- Decision-date joins MUST be as-of joins and preserve source observation date.
- Absent values and bounded financing precision MUST remain distinguishable.
- Rebuilding with later source observations MUST NOT change a frozen prior feature.
