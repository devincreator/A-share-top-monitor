#!/usr/bin/env python3
"""Validate V86 input records, preserving research-only gates and legacy formats."""
import argparse
import csv
import hashlib
import json
from datetime import date, datetime
from pathlib import Path

EVENT_FIELDS = {"id", "date", "scale", "direction"}
LEGACY_FIELDS = {
    "alerts": {"event_id", "date", "scale", "direction"},
    "pivots": {"pivot_id", "turning_date", "confirmation_date", "scale", "direction"},
}
PRICE_FIELDS = {"date", "close"}


def iso(value):
    value = value.strip()
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        return datetime.strptime(value, "%Y%m%d").date().isoformat()


def inspect_file(kind, path):
    p = Path(path)
    item = {"path": str(p), "exists": p.is_file(), "rows": 0, "issues": []}
    if not p.is_file():
        item["issues"].append("source file missing")
        return item, []
    raw = p.read_bytes()
    item["sha256"] = hashlib.sha256(raw).hexdigest()
    try:
        with p.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            fields = set(reader.fieldnames or [])
            if kind == "prices":
                required, schema = PRICE_FIELDS, "PRICE"
            elif EVENT_FIELDS.issubset(fields):
                required, schema = EVENT_FIELDS, "CANONICAL"
            elif LEGACY_FIELDS[kind].issubset(fields):
                required, schema = LEGACY_FIELDS[kind], "LEGACY"
            else:
                item["issues"].append("missing event columns: id,date,scale,direction or documented legacy aliases")
                return item, []
            if not required.issubset(fields):
                item["issues"].append("missing required columns")
                return item, []
            item["schema"] = schema
            item["fields"] = sorted(fields)
            normalized, seen = [], set()
            previous = None
            for number, row in enumerate(reader, 2):
                item["rows"] += 1
                try:
                    if any(not (row.get(c) or "").strip() for c in required):
                        raise ValueError("blank required field")
                    stamp = iso(row["turning_date"] if kind == "pivots" and schema == "LEGACY" else row["date"])
                    if kind == "prices":
                        price = float(row["close"])
                        if not 0 < price < float("inf"):
                            raise ValueError("invalid close")
                        if previous is not None and stamp <= previous:
                            raise ValueError("price calendar must be strictly ascending")
                        previous = stamp
                        normalized.append({"date": stamp, "close": str(price)})
                        continue
                    uid = (row["event_id"] if kind == "alerts" else row["pivot_id"]) if schema == "LEGACY" else row["id"]
                    if row["scale"] not in ("5", "9") or row["direction"] not in ("TOP", "BOTTOM"):
                        raise ValueError("invalid task dimension")
                    if uid in seen:
                        raise ValueError("duplicated ID")
                    seen.add(uid)
                    if kind == "pivots" and schema == "LEGACY" and iso(row["confirmation_date"]) < stamp:
                        raise ValueError("pivot confirmation before turning date")
                    if kind == "alerts" and any(k in row for k in ("event_type", "status", "signal_type")):
                        flag = row.get("event_type") or row.get("status") or row.get("signal_type")
                        if flag != "FORMAL_START":
                            raise ValueError("non-FORMAL_START notification")
                    normalized.append({"id": uid, "date": stamp,
                                       "scale": row["scale"], "direction": row["direction"]})
                except (ValueError, TypeError, KeyError) as error:
                    item["issues"].append(f"line {number}: {str(error)[:100]}")
    except (UnicodeDecodeError, csv.Error) as error:
        item["issues"].append("malformed CSV: " + str(error)[:100])
        return item, []
    if not item["rows"]:
        item["issues"].append("no rows")
    if len(item["issues"]) > 20:
        item["issues"] = item["issues"][:20] + ["further errors truncated"]
    if kind == "alerts" and not set(item.get("fields", [])) & {"event_type", "status", "signal_type"}:
        item["warnings"] = ["Source has no explicit FORMAL_START type; verify externally"]
    return item, normalized


def inspect_inputs(alerts, pivots, prices=None):
    report = {"status": "BLOCKED", "formal_backtest_allowed": False,
              "evaluation": "RESEARCH_ONLY", "files": {}, "issues": []}
    sets = {}
    for kind, path in (("alerts", alerts), ("pivots", pivots), ("prices", prices)):
        if path is None:
            report["issues"].append(f"{kind}: file not supplied")
            continue
        details, values = inspect_file(kind, path)
        report["files"][kind] = details
        sets[kind] = values
        report["issues"].extend(f"{kind}: {reason}" for reason in details["issues"])
    if not report["issues"]:
        dates = {r["date"] for r in sets["prices"]}
        for kind in ("alerts", "pivots"):
            unmatched = sorted({r["date"] for r in sets[kind]} - dates)
            if unmatched:
                report["issues"].append(f"{kind}: dates not in price calendar {unmatched[:5]}")
    if not report["issues"]:
        report["status"] = "INPUT_SCHEMA_READY_NOT_YET_AUDITED"
        report["note"] = ("Structure only; FORMAL_START provenance, PIT timestamps, "
                          "mature labels and embargo still require independent audit")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--alerts", default="research/data/v86_formal_alert_events.csv")
    parser.add_argument("--pivots", default="research/data/v86_objective_pivot_events.csv")
    parser.add_argument("--prices", default="research/data/v86_index_prices.csv")
    parser.add_argument("--output", default="research/status/v86_input_inventory.json")
    args = parser.parse_args(argv)
    report = inspect_inputs(args.alerts, args.pivots, args.prices)
    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "issues": report["issues"]}, ensure_ascii=False))
    return 0  # Missing inputs are research blockers, not workflow infrastructure errors


if __name__ == "__main__":
    raise SystemExit(main())
