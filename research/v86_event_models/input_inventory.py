#!/usr/bin/env python3
"""Audit V86 event-level input availability without inventing model results."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

REQUIRED = {
    "alerts": {"date", "direction", "scale", "event_id"},
    "pivots": {"turning_date", "direction", "scale", "pivot_id", "confirmation_date"},
}


def inspect_inputs(alerts, pivots):
    result = {"status": "BLOCKED", "formal_backtest_allowed": False, "files": {}, "issues": []}
    for kind, path in (("alerts", alerts), ("pivots", pivots)):
        p = Path(path)
        item = {"path": str(p), "exists": p.is_file()}
        if not p.is_file():
            result["issues"].append(f"{kind}: missing event-level file")
        else:
            raw = p.read_bytes()
            item["sha256"] = hashlib.sha256(raw).hexdigest()
            with p.open("r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                missing = sorted(REQUIRED[kind] - set(reader.fieldnames or []))
                item["missing_fields"] = missing
                item["rows"] = sum(1 for _ in reader)
            if missing:
                result["issues"].append(f"{kind}: missing columns {missing}")
            if not item["rows"]:
                result["issues"].append(f"{kind}: no event records")
        result["files"][kind] = item
    if not result["issues"]:
        result["status"] = "INPUT_SCHEMA_READY_NOT_YET_AUDITED"
        result["note"] = "Schema only: event time, one-to-one matching, PIT and embargo remain unchecked."
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--alerts", default="research/data/v86_formal_alert_events.csv")
    parser.add_argument("--pivots", default="research/data/v86_objective_pivot_events.csv")
    parser.add_argument("--output", default="research/status/v86_input_inventory.json")
    args = parser.parse_args()
    result = inspect_inputs(args.alerts, args.pivots)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
