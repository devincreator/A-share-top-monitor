#!/usr/bin/env python3
"""Unattended weekly gate check; strictly research-only, never a trading engine."""
import argparse
import hashlib
import importlib.util
import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

START = date(2026, 10, 20)
END = date(2027, 4, 20)


def import_from(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_json(path):
    b = Path(path).read_bytes()
    return json.loads(b), hashlib.sha256(b).hexdigest()


def report_on(root, today, *, inventory_fn=None):
    root = Path(root)
    if isinstance(today, str):
        today = date.fromisoformat(today)
    gates, gsha = read_json(root/"research/status/quality_gates.json")
    state, ssha = read_json(root/"data/latest_state.json")
    market, msha = read_json(root/"data/latest_verified_market.json")
    readiness = import_from(root/"research/v84_live_readiness/readiness.py", "v84_readiness")
    if inventory_fn is None:
        inventory = import_from(root/"research/v86_event_models/input_inventory.py", "v86_inventory")
        inventory_fn = inventory.inspect_inputs
    current = readiness.build_report(state, market, today=today, state_sha=ssha, market_sha=msha)
    event = inventory_fn(root/"research/data/v86_formal_alert_events.csv",
                         root/"research/data/v86_objective_pivot_events.csv",
                         root/"research/data/v86_index_prices.csv")
    raw = gates["versions"].get("V85_2006", {}).get("status") == "RAW_241_241_VERIFIED_NOT_PIT"
    pit = gates["data_quality"].get("2005_asof_listing_universe_independently_verified") is True and gates["data_quality"].get("2005_suspension_vs_source_gap_resolved") is True
    live = current["status"] == "FORMAL_INPUTS_READY_FOR_SEPARATE_SIGNAL_ENGINE"
    event_ready = event["status"] == "INPUT_SCHEMA_READY_NOT_YET_AUDITED"
    stage = "BEFORE_START" if today < START else "ENDED" if today > END else "RESEARCH_RUNNING"
    return {
        "schema_version": 1, "asof": today.isoformat(),
        "window": {"start":START.isoformat(), "end":END.isoformat(), "status":stage},
        "research_only":True, "formal_signals_generated":False, "production_changed":False,
        "source_sha256":{"quality_gates":gsha,"latest_state":ssha,"latest_verified_market":msha},
        "gates":{
            "current_full_model":{"passed":live,"status":current["status"]},
            "2006_raw_integrity":{"passed":raw,"PIT_certified":False},
            "2005_listing_suspension_PIT":{"passed":pit},
            "V86_event_inputs":{"passed":event_ready,"status":event["status"]},
            "formal_double80":{"passed":False,"status":"NOT_VALIDATED"},
            "prospective_frozen_sample":{"passed":gates["spec"].get("new_forward_unseen_validation") is True}
        },
        "readiness_channels":current["channels"],
        "event_input_issues":event["issues"][:20],
        "next_task":("Restore independently verified current index/volume/turnover/financing feeds"
                     if not live else "Recover actual formal-start and mature pivot event records"
                     if not event_ready else "Independently certify listed securities, suspension and corporate actions"),
        "warning":"Passing an Actions job never means PIT, forecast quality, dual80 or signal deployment passed."
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--today", default=datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat())
    parser.add_argument("--output", default="v87_review/weekly_report.json")
    parser.add_argument("--checkpoint-dir", default="research/v87_automation/checkpoints")
    parser.add_argument("--initial", action="store_true")
    args = parser.parse_args(argv)
    today = date.fromisoformat(args.today)
    report = report_on(args.repo, today)
    s = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)+"\n"
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(s, encoding="utf-8")
    monthly = START <= today <= END and (today.day <= 7 or (args.initial and today == START))
    if monthly:
        checkpoint = Path(args.checkpoint_dir)/(today.strftime("%Y-%m")+".json")
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        checkpoint.write_text(s, encoding="utf-8")
    print(json.dumps({"date":today.isoformat(),"stage":report["window"]["status"],
                      "current_model":report["gates"]["current_full_model"]["status"],
                      "checkpoint_written":monthly}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
