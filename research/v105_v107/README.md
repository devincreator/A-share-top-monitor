# V105–V107 independent research (not production)

V105 diagnoses the original V101 alerts by reading the immutable V102 false-positive and missed-pivot tables. This is *ex post explanation only*, not a new predictor. V106 creates a causal trailing-price state baseline. The resulting state at close t is not automatically certified as available at t+1 09:20; V103 must independently establish that fact prospectively. V107 market-wide breadth, turnover and financing are **not added** until original-source time and data quality are independently verified.

Run:
```bash
python -m unittest discover -s research/v105_v107 -p 'test_*.py' -v
python research/v105_v107/diagnose_and_state.py
```

It refuses a changed price SHA and never alters V101/V102, quality_gates.json, production or frozen thresholds. It emits a diagnosis, a feature-only daily table and summary. These are *not* newly issued alerts, scored predictions or independent out-of-sample results. No 80/80 claim is authorized. V108–V110 require verified causal inputs, frozen candidate registration, independent future predictions and later-matured outcomes.
