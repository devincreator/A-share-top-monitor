#!/usr/bin/env python3
"""Keep one immutable research-only price observation per verified date."""
import argparse
import datetime as dt
import json
from pathlib import Path

REQUIRED=("date","index","close","ret5_pct","ret63_pct",
          "rv_ratio_percentile_prior756","ret63_percentile_prior756",
          "candidate_input_sha256","cross_provider_status")

def archive_first_capture(report, ledger_dir, *, timestamp=None, audit_dir=None):
    target=Path(ledger_dir)
    if any(name not in report for name in REQUIRED):
        return {"status":"BLOCKED_MISSING_FIELDS"}
    if report.get("cross_provider_status")!="RESEARCH_PRICE_AMOUNT_CROSS_PROVIDER_PASS":
        return {"status":"BLOCKED_NOT_CROSS_VERIFIED"}
    if report.get("formal_signal_allowed") is not False or report.get("index")!="000985.CSI":
        return {"status":"BLOCKED_NOT_RESEARCH_ONLY"}
    try:
        d=dt.date.fromisoformat(report["date"])
    except (ValueError,TypeError):
        return {"status":"BLOCKED_INVALID_DATE"}
    archive={k:report[k] for k in REQUIRED}
    archive["formal_signal_allowed"]=False
    archive["PIT_certified"]=False
    archive["four_module_recalculated"]=False
    archive["source_scope"]="Independent-source-checked price and amount, historical research only"
    archive["first_saved_at_utc"]=(timestamp or dt.datetime.now(dt.timezone.utc).isoformat())
    target.mkdir(parents=True,exist_ok=True)
    file=target/(d.isoformat()+".json")
    if file.exists():
        original=json.loads(file.read_text(encoding="utf8"))
        before={k:original.get(k) for k in REQUIRED}
        after={k:archive.get(k) for k in REQUIRED}
        if before!=after:
            if audit_dir is not None:
                out=Path(audit_dir);out.mkdir(parents=True,exist_ok=True)
                (out/"revision_conflict.json").write_text(json.dumps({
                    "status":"SOURCE_REVISION_CONFLICT","date":d.isoformat(),
                    "old":before,"new":after},ensure_ascii=False,indent=2)+"\n")
            return {"status":"SOURCE_REVISION_CONFLICT","date":d.isoformat(),
                    "existing_record_left_unchanged":True}
        return {"status":"UNCHANGED","date":d.isoformat()}
    file.write_text(json.dumps(archive,ensure_ascii=False,indent=2,sort_keys=True)+"\n")
    return {"status":"FIRST_CAPTURE_PERSISTED","date":d.isoformat(),"file":str(file)}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--report",default="v89_source_audit_output/price_only_research.json")
    p.add_argument("--ledger",default="research/v89_factor_inputs/observations")
    p.add_argument("--audit-dir",default="v89_source_audit_output")
    args=p.parse_args()
    f=Path(args.report)
    if not f.is_file():
        result={"status":"NO_PRICE_RESEARCH_REPORT"}
    else:
        result=archive_first_capture(json.loads(f.read_text(encoding="utf8")),
                                     args.ledger,audit_dir=args.audit_dir)
    print(json.dumps(result,ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
