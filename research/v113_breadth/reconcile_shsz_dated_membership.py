#!/usr/bin/env python3
"""V113 SH/SZ only: resolve 41 legal outDate boundaries with true dated stock-list status."""
import argparse,csv,hashlib,json
from pathlib import Path
from collections import defaultdict
def read_csv(path):
 with open(path,newline="",encoding="utf-8") as f:return list(csv.DictReader(f))
def reclassify_day(old,items):
 original=int(old["security_days_with_status"])
 expected=int(old["expected_listed_shsz"])
 o=int(old["unresolved"])
 if o!=len(items):raise ValueError("ORIGINAL_MISSING_COUNT_DISAGREES")
 missing_code_dates=[r for r in items if r["status"] not in ("NOT_IN_HISTORICAL_LIST","0")]
 removed=sum(r["status"]=="NOT_IN_HISTORICAL_LIST" for r in items)
 suspended=sum(r["status"]=="0" for r in items)
 remaining=len(missing_code_dates)
 adjusted=expected-removed
 observed=original+suspended
 if adjusted-observed!=remaining or adjusted<observed:raise ValueError("MEMBERSHIP_RECONCILIATION_INVARIANT")
 if any(r["status"] not in ("NOT_IN_HISTORICAL_LIST","0","1","SOURCE_FAILED") for r in items):
  raise ValueError("UNEXPECTED_STATUS")
 return {"date":old["date"],"expected_shsz_in_dated_membership":adjusted,
  "all_observed_or_verified_suspend":observed,
  "up":int(old["up"]),"down":int(old["down"]),"flat":int(old["flat"]),
  "suspended":int(old["suspended"])+suspended,
  "not_listed_as_of_source_day":removed,
  "original_baostock_bars":original,
  "unresolved":remaining,
  "fully_reconciled":int(remaining==0)}
def main():
 p=argparse.ArgumentParser()
 for n in ("anchor","baseline","gaps","source-dir","out"):p.add_argument("--"+n,required=True)
 a=p.parse_args()
 with open(a.anchor,newline="",encoding="utf-8") as f:
  calendar=[r["source_trade_date"] for r in csv.DictReader(f)]
 if len(calendar)!=1129 or calendar!=sorted(set(calendar)):raise ValueError("FROZEN_CALENDAR_INVALID")
 original={r["date"]:r for r in read_csv(a.baseline)}
 gaps=read_csv(a.gaps)
 if len(gaps)!=41 or len(set((x["code"],x["date"]) for x in gaps))!=41:
  raise ValueError("SOURCE_EXACT_GAPS_CHANGED")
 listed=defaultdict(dict);proof=[]
 for shard in range(8):
  pth=Path(a.source_dir)/("dated_membership_shard_%02d.json"%shard)
  if not pth.is_file():raise ValueError("MISSING_DATED_MEMBERSHIP_SHARD_"+str(shard))
  source=json.loads(pth.read_text())
  if source["shard"]!=shard or source["shards"]!=8:raise ValueError("MEMBERSHIP_SHARD_CHANGED")
  for r in source["results"]:
   if r["date"] in listed:raise ValueError("DUPLICATED_SNAPSHOT_DATE")
   if r["status"]!="VERIFIED_HISTORICAL_DATE_LIST":
    raise ValueError("HISTORICAL_SNAPSHOT_FETCH_FAILED_"+r["date"])
   if r["full_source_rows"]<3000 or not r.get("raw_source_response_digest_sha256"):
    raise ValueError("HISTORICAL_SNAPSHOT_UNVERIFIED")
   listed[r["date"]]=r["code_status"]
   proof.append({"date":r["date"],"source_digest_sha256":r["raw_source_response_digest_sha256"],
     "source_full_records":r["full_source_rows"]})
 if len(listed)!=32:raise ValueError("NOT_ALL_32_HISTORICAL_DATES_CAPTURED")
 per_day=defaultdict(list);source_cases=[]
 for r in gaps:
  d=r["date"];code=r["code"]
  if r.get("outDate")!=d:raise ValueError("NOT_AN_OUTDATE_BOUNDARY")
  status=listed.get(d,{}).get(code)
  if status is None:raise ValueError("MISSING_CODE_FROM_HISTORICAL_DATE_REQUEST")
  info={"date":d,"code":code,"status":status,"outDate":r["outDate"]}
  per_day[d].append(info);source_cases.append(info)
 result=[reclassify_day(original[d],per_day[d]) for d in calendar]
 complete=sum(r["fully_reconciled"] for r in result)
 boundary_counts={status:sum(x["status"]==status for x in source_cases)
   for status in sorted({x["status"] for x in source_cases})}
 out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
 with (out/"daily_shsz_dated_membership.csv").open("w",newline="",encoding="utf-8") as f:
  w=csv.DictWriter(f,fieldnames=list(result[0]));w.writeheader();w.writerows(result)
 with (out/"41_boundary_cases.csv").open("w",newline="",encoding="utf-8") as f:
  w=csv.DictWriter(f,fieldnames=list(source_cases[0]));w.writeheader();w.writerows(source_cases)
 (out/"32_historical_snapshot_source_digests.json").write_text(json.dumps(proof,ensure_ascii=False,indent=2)+"\n")
 acceptance={"version":"V113-SHSZ","scope":"SHANGHAI_SHENZHEN_ONLY_EXCLUDES_BEIJING",
  "target_dates":len(calendar),"complete_days":complete,
  "coverage_fraction":round(complete/len(calendar),8),
  "source_dated_snapshots":len(listed),"source_boundary_41_cases":boundary_counts,
  "missing_stock_days_after_snapshot_join":sum(r["unresolved"] for r in result),
  "scoped_98_percent_data_coverage_pass":(complete*100>=98*len(calendar)),
  "shsz_all_dates_reconciled":(complete==len(calendar)),
  "historical_release_PIT_certified":False,
  "independent_exchange_universe_fully_certified":False,
  "formal_signal_allowed":False,
  "all_A_scope_pass":False}
 acceptance["daily_sha256"]=hashlib.sha256((out/"daily_shsz_dated_membership.csv").read_bytes()).hexdigest()
 (out/"acceptance.json").write_text(json.dumps(acceptance,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps(acceptance,ensure_ascii=False))
if __name__=="__main__":main()
