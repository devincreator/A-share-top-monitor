#!/usr/bin/env python3
"""V93: test whether exact-Yuan SZSE detail aggregation equals whole-market margin.

The sum of currently disclosed securities can differ from whole-market summary.
No automatic replacement of Jin10 or production financing is ever allowed.
"""
import argparse
from decimal import Decimal,InvalidOperation
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"v91_exchange_margin"))
from probe_official import parse_summary

PILOT_DATES=("2024-08-08","2025-01-07","2026-10-20")


def sum_detail_yuan(frame):
    required={"证券代码","融资余额"}
    if frame is None or not required.issubset(set(frame.columns)):
        raise ValueError("SZSE detail security code and balance columns required")
    records=frame.to_dict(orient="records")
    if len(records)<50 or len(records)>12000:
        raise ValueError("implausibly small/large SZSE detail securities")
    total=Decimal(0)
    codes=set()
    zeros=0
    for row in records:
        name=str(row["证券代码"]).strip()
        if name.endswith(".0"):
            name=name[:-2]
        if not name.isdigit() or len(name)>6:
            raise ValueError("invalid security code in detail")
        code=name.zfill(6)
        if code in codes:
            raise ValueError(f"duplicate security code {code}; would double count")
        codes.add(code)
        try:
            amount=Decimal(str(row["融资余额"]).replace(",","").strip())
        except (ValueError,InvalidOperation):
            raise ValueError(f"invalid numeric detail balance at {code}")
        if not amount.is_finite() or amount<0:
            raise ValueError("nonfinite/negative security financing")
        if amount==0:
            zeros+=1
        total+=amount
    if not (Decimal("100000000000")<total<Decimal("3000000000000")):
        raise ValueError("detail-sum financing implausible for complete SZ market")
    return {"security_rows":len(records),"distinct_security_codes":len(codes),
            "zero_security_balance_rows":zeros,"detail_balance_sum_yuan":str(total),
            "source_precision":"per-security Yuan as provided, not independently PIT-certified"}


def compare_sources(detail,summary,reference):
    total=Decimal(detail["detail_balance_sum_yuan"])
    out={"status":"DETAIL_ONLY_NO_VERIFIED_SUMMARY"}
    if summary is not None:
        aggregate=Decimal(summary["balance_yuan_from_source"])
        difference=total-aggregate
        out.update(summary_display_yuan=str(aggregate),
                   detail_minus_summary_display_yuan=str(difference),
                   summary_display_precision="100M CNY, normally two decimal places")
        if abs(difference)<=Decimal(1000000):
            out["status"]="DETAIL_CONSISTENT_WITH_SUMMARY_DISPLAY_PRECISION"
        else:
            out["status"]="DETAIL_NOT_WHOLE_MARKET_SUMMARY"
    if reference is not None:
        try:
            ref=Decimal(str(reference.get("balance_sz_yuan")))
            if ref.is_finite() and ref>0:
                out["Jin10_original_yuan"]=str(ref)
                out["detail_minus_Jin10_yuan"]=str(total-ref)
                out["detail_equals_Jin10_exactly"]=total==ref
        except (ValueError,TypeError,InvalidOperation):
            pass
    out["formal_signal_allowed"]=False
    out["PIT_certified"]=False
    return out


def pilot(input_json,output_dir,dates=PILOT_DATES,*,api=None):
    raw=Path(input_json).read_bytes()
    inputs=json.loads(raw)
    originals={row["date"]:row for row in inputs.get("financing",[])}
    idx={row["date"] for row in inputs["indices"]["000985"]}
    target=Path(output_dir)
    target.mkdir(parents=True,exist_ok=True)
    report={"schema_version":1,"source_candidate_sha256":hashlib.sha256(raw).hexdigest(),
            "formal_signal_allowed":False,"PIT_certified":False,"dates":[]}
    if api is None:
        import akshare as api
        report["akshare_version"]=getattr(api,"__version__","unknown")
    for day in dates:
        record={"date":day,"status":"BLOCKED","in_source_index_calendar":day in idx}
        if day not in idx:
            record["error"]="requested date absent from V89 000985 observation sessions"
            report["dates"].append(record)
            continue
        try:
            frame=api.stock_margin_detail_szse(date=day.replace("-",""))
            path=target/f"szse_detail_{day}_raw.csv"
            frame.to_csv(path,index=False)
            record["detail_raw_sha256"]=hashlib.sha256(path.read_bytes()).hexdigest()
            record["detail_columns"]=list(map(str,frame.columns))
            detail=sum_detail_yuan(frame)
            record["detail"]=detail
        except Exception as exc:
            record["detail_error"]=f"{type(exc).__name__}: {str(exc)[:240]}"
            report["dates"].append(record)
            continue
        summary=None
        try:
            summary_frame=api.stock_margin_szse(date=day.replace("-",""))
            summ_path=target/f"szse_summary_{day}_raw.csv"
            summary_frame.to_csv(summ_path,index=False)
            record["summary_raw_sha256"]=hashlib.sha256(summ_path.read_bytes()).hexdigest()
            summary=parse_summary("SZSE",summary_frame,day)
            record["summary"]={k:summary[k] for k in (
                "balance_yuan_from_source","reported_unit","date_provenance")}
        except Exception as exc:
            record["summary_error"]=f"{type(exc).__name__}: {str(exc)[:240]}"
        record["comparison"]=compare_sources(detail,summary,originals.get(day))
        record["status"]="DETAIL_AGGREGATE_COMPUTED_RESEARCH_ONLY"
        record["publication_time_verified"]=False
        record["market_completeness_proven"]=record["comparison"]["status"]=="DETAIL_CONSISTENT_WITH_SUMMARY_DISPLAY_PRECISION"
        # Even matching a rounded market summary cannot prove historical PIT.
        record["PIT_certified"]=False
        report["dates"].append(record)
    (target/"szse_detail_pilot.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--candidate",required=True)
    p.add_argument("--out",default="v93_szse_detail_pilot")
    a=p.parse_args()
    result=pilot(a.candidate,a.out)
    print(json.dumps({"days":[{"date":x["date"],"status":x["status"],
                                "comparison":x.get("comparison",{}).get("status")}
                               for x in result["dates"]],
                      "formal_signal_allowed":False},ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
