#!/usr/bin/env python3
"""Audit historical Beijing daily trade observations and code migrations."""
import argparse,csv,gzip,hashlib,json
from datetime import date
from collections import Counter
from pathlib import Path
from decimal import Decimal,InvalidOperation
def main():
 p=argparse.ArgumentParser()
 for name in ("registry","anchor","source-dir","out"):p.add_argument("--"+name,required=True)
 a=p.parse_args()
 out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
 with open(a.registry,newline="",encoding="utf-8") as f:
  regs={r["code"]:r for r in csv.DictReader(f)}
 with open(a.anchor,newline="",encoding="utf-8") as f:
  days=[r["source_trade_date"] for r in csv.DictReader(f)]
 if len(days)!=1129 or len(set(days))!=1129:raise ValueError("BAD_CALENDAR")
 src=Path(a.source_dir)
 by_day={d:Counter() for d in days}
 counted=set();ticker_codes=set();issues=[];manifests=[]
 for shard in range(8):
  mp=src/("beijing_manifest_%02d.json"%shard)
  bars=src/("beijing_bars_%02d.csv.gz"%shard)
  if not mp.is_file() or not bars.is_file():
   issues.append("MISSING_BJ_SHARD_"+str(shard));continue
  manifest=json.loads(mp.read_text(encoding="utf-8"))
  if manifest["shard"]!=shard or manifest["shards"]!=8:raise ValueError("BAD_SHARD_ID")
  if hashlib.sha256(bars.read_bytes()).hexdigest()!=manifest["archive_sha256"]:raise ValueError("BAD_ARCHIVE_SHA")
  for row in manifest["individual_stock_evidence"]:
   code=row["code"]
   if code in ticker_codes:raise ValueError("DUPLICATED_BJ_TICKER")
   if code not in regs:raise ValueError("UNKNOWN_BJ_TICKER")
   ticker_codes.add(code)
   if row["status"]!="OBSERVED_TRADING_BARS_ONLY":issues.append("FAILED_BJ_STOCK_"+code)
  with gzip.open(bars,"rt",encoding="utf-8") as f:
   for r in csv.DictReader(f):
    code=r["symbol"];d=r["date"]
    if code not in regs or d not in by_day:raise ValueError("INVALID_CODE_OR_DATE")
    info=regs[code]
    if d<info["listed"] or (info["delisted"] and d>info["delisted"]):raise ValueError("BJ_BAR_OUTSIDE_LISTING")
    key=(code,d)
    if key in counted:raise ValueError("DUPLICATE_BJ_SECURITY_DAY")
    counted.add(key)
    pct=Decimal(r["pct_change"])
    amount=Decimal(r["amount"])
    if not pct.is_finite() or not amount.is_finite() or amount<0:raise ValueError("BAD_BJ_PRICE")
    label="up" if pct>0 else "down" if pct<0 else "flat"
    by_day[d][label]+=1;by_day[d]["bars"]+=1
  manifests.append({"shard":shard,"sha256":manifest["archive_sha256"],"successful":manifest["successful"],
                    "requested":manifest["requested"]})
 if set(regs)!=ticker_codes:issues.append("BJ_REGISTRY_NOT_FULLY_ARCHIVED")
 records=[]
 for d in days:
  expected=sum(x["listed"]<=d and (not x["delisted"] or d<=x["delisted"]) for x in regs.values())
  observed=by_day[d]["bars"]
  if observed>expected:raise ValueError("BJ_OVER_EXPECTED_"+d)
  records.append({"date":d,"bj_expected_listed":expected,"bj_trading_bars":observed,
    "bj_up":by_day[d]["up"],"bj_down":by_day[d]["down"],"bj_flat":by_day[d]["flat"],
    "bj_unknown_not_traded":expected-observed,
    "bj_suspended_verified":0,
    "fully_resolved":int(expected==observed and expected>0)})
 with (out/"daily_beijing_breadth.csv").open("w",newline="",encoding="utf-8") as f:
  w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
 report={"version":"V113","scope":"BSE_HISTORY_RESEARCH",
 "target_days":len(days),"registry_count":len(regs),"captured_tickers":len(ticker_codes),
 "fully_resolved_days_if_no_suspensions":sum(r["fully_resolved"] for r in records),
 "unresolved_beijing_security_days":sum(r["bj_unknown_not_traded"] for r in records),
 "missing_bj_suspension_audit":True,"issues":issues[:100],"issue_count":len(issues),
 "suspension_and_historical_pit_certified":False,"formal_signal_allowed":False,
 "sha256":hashlib.sha256((out/"daily_beijing_breadth.csv").read_bytes()).hexdigest(),
 "shards":manifests}
 (out/"coverage.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps({k:v for k,v in report.items() if k not in ("shards","issues")},ensure_ascii=False))
if __name__=="__main__":main()
