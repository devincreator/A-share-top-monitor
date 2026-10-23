#!/usr/bin/env python3
"""V113 observed 24-shard daily market reconstruction, fail-closed all-A audit."""
import argparse,csv,gzip,hashlib,json
from collections import Counter
from datetime import date
from pathlib import Path
from baostock_shard import basic_list, COLUMNS

def main():
    p=argparse.ArgumentParser()
    for key in ("anchor","stock-basic","source-dir","out"):p.add_argument("--"+key,required=True)
    args=p.parse_args()
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    with open(args.anchor,newline="",encoding="utf-8") as f:
        days=[r["source_trade_date"] for r in csv.DictReader(f)]
    if len(days)!=1129 or len(set(days))!=1129:raise ValueError("BAD_FROZEN_CALENDAR")
    stocks=basic_list(args.stock_basic)
    src=Path(args.source_dir);observed=Counter()
    statuses={d:Counter() for d in days}
    manifests=[];per_code={};fatal=[]
    for shard in range(24):
        fn=src/("manifest_%02d.json"%shard)
        if not fn.is_file():
            fatal.append("MISSING_MANIFEST_%02d"%shard)
            continue
        doc=json.loads(fn.read_text())
        if doc.get("shards")!=24 or doc.get("shard")!=shard:raise ValueError("BAD_MANIFEST_ID")
        gz=src/("stock_bars_shard_%02d.csv.gz"%shard)
        if not gz.is_file():raise ValueError("MISSING_RAW_SHARD_%02d"%shard)
        if hashlib.sha256(gz.read_bytes()).hexdigest()!=doc["raw_archive_sha256"]:
            raise ValueError("SHARD_RAW_SHA_MISMATCH_%02d"%shard)
        for r in doc["rows"]:
            if r["code"] in per_code:raise ValueError("DUPLICATE_CODE_ACROSS_SHARDS")
            per_code[r["code"]]=r
            if r["status"]!="VALIDATED_RESEARCH":fatal.append("FAILED_SOURCE_"+r["code"])
        rows=0
        with gzip.open(gz,"rt",encoding="utf-8",newline="") as f:
            reader=csv.DictReader(f)
            if reader.fieldnames!=COLUMNS:raise ValueError("RAW_SCHEMA_CHANGED")
            for r in reader:
                rows+=1
                code=r["code"];day=r["date"]
                if code not in stocks or code not in per_code:raise ValueError("UNKNOWN_BAR_SYMBOL")
                if day not in statuses:raise ValueError("OUTSIDE_ANCHOR_BAR_DATE")
                b=stocks[code]
                if (b.get("ipoDate") and day<b["ipoDate"]) or (b.get("outDate") and day>b["outDate"]):
                    raise ValueError("BAR_OUTSIDE_LISTING_INTERVAL")
                st=r["tradestatus"]
                if st=="0":kind="suspended"
                elif st=="1":
                    a=float(r["close"]);old=float(r["preclose"])
                    if not(a>0 and old>0):raise ValueError("INVALID_PRICE")
                    kind="up" if a>old else "down" if a<old else "flat"
                else:raise ValueError("UNKNOWN_TRADESTATUS")
                statuses[day][kind]+=1
                observed[day]+=1
        manifests.append({"shard":shard,"source_rows":rows,"manifest_count":len(doc["rows"]),
                          "sha256":doc["raw_archive_sha256"],"failed_count":doc["failed_stock_count"]})
    if set(per_code)!=set(stocks):
        fatal.append("BASIC_CODES_NOT_ALL_ARCHIVED_"+str(len(set(stocks)-set(per_code))))
    expected=Counter()
    for d in days:
        expected[d]=sum((not b.get("ipoDate") or b["ipoDate"]<=d)
            and (not b.get("outDate") or b["outDate"]>=d) for b in stocks.values())
    records=[]
    for d in days:
        o=observed[d];e=expected[d]
        if o>e:raise ValueError("OBSERVED_OVER_EXPECTED_"+d)
        records.append({"date":d,"expected_listed_shsz":e,
            "security_days_with_status":o,"up":statuses[d]["up"],
            "down":statuses[d]["down"],"flat":statuses[d]["flat"],
            "suspended":statuses[d]["suspended"],"unresolved":e-o,
            "fully_observed":int(e>0 and e==o)})
    expected_snapshots={"2022-06-20":4733,"2025-01-02":5122,
                        "2026-09-21":5221,"2026-10-21":5224}
    snapshot_differences={d:expected[d]-count for d,count in expected_snapshots.items()}
    if any(v!=0 for v in snapshot_differences.values()):
        fatal.append("HISTORIC_UNIVERSE_SNAPSHOT_MISMATCH")
    full=sum(r["fully_observed"] for r in records)
    report={"version":"V113","status":"PARTIAL" if any(observed.values()) else "BLOCKED",
            "source_scope":"SHANGHAI_AND_SHENZHEN_ONLY_BEIJING_EXCLUDED",
            "shsz_expected_basic_symbols":len(stocks),
            "full_daily_shsz_days":full,"target_days":len(days),
            "shsz_day_coverage":round(full/len(days),8),
            "all_shsz_ticker_archives_present":len(per_code)==len(stocks),
            "failed_stock_codes":sum(r["status"]!="VALIDATED_RESEARCH" for r in per_code.values()),
            "missing_shsz_security_date_observations":sum(r["unresolved"] for r in records),
            "shsz_snapshot_differences":snapshot_differences,
            "beijing_security_dates_present":0,
            "all_a_stock_universe_verified":False,
            "full_v113_pass":False,"formal_signal_allowed":False,
            "issues":fatal[:100],"total_issues":len(fatal),"shards":manifests,
            "data_date_start":days[0],"data_date_end":days[-1]}
    with (out/"daily_shsz_breadth.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]))
        w.writeheader();w.writerows(records)
    report["daily_sha256"]=hashlib.sha256((out/"daily_shsz_breadth.csv").read_bytes()).hexdigest()
    (out/"coverage.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k not in ("shards","issues")},ensure_ascii=False))
if __name__=="__main__":main()
