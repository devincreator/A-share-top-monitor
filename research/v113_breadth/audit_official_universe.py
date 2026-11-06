#!/usr/bin/env python3
"""V113 independent issuer count benchmark at exact month-end snapshots."""
import csv,json
from pathlib import Path
def get(path):
 with open(path,newline="",encoding="utf-8") as f:return list(csv.DictReader(f))
shsz=[r for r in get("basic/stock_basic.csv") if r["type"]=="1"]
bj=get("bj_registry/beijing_historical_registry.csv")
official={
 "2022-12-30":{"sh":2174,"sz":2743,"bj":162,"origin":"CSRC: Chinese listed companies statistical development 2024"},
 "2024-12-31":{"sh":2278,"sz":2852,"bj":262,"origin":"CSRC 2024 year-end listed-company counts"},
 "2025-04-30":{"sh":2284,"sz":2871,"bj":265,"origin":"2024 listed companies development report, 2025-04-30"},
 "2026-09-30":{"sh":2323,"sz":2908,"bj":348,"origin":"SSE 2026 September monthly; SZSE 2026 September monthly; Guosen BSE 2026 September report"}
}
out={}
for d,v in official.items():
 counts={"sh":0,"sz":0,"bj":0}
 for r in shsz:
  if r["ipoDate"] and r["ipoDate"]>d:continue
  if r["outDate"] and r["outDate"]<d:continue
  counts[r["code"].split(".")[0]]+=1
 for r in bj:
  if r["listed"]>d:continue
  if r["delisted"] and r["delisted"]<d:continue
  counts["bj"]+=1
 out[d]={"predicted":counts,"official":{k:v[k] for k in ("sh","sz","bj")},
  "delta":{k:counts[k]-v[k] for k in ("sh","sz","bj")},
  "matched":all(counts[k]==v[k] for k in ("sh","sz","bj")),
  "source":v["origin"]}
report={"version":"V113","status":"CHECKED_WITH_OFFICIAL_AGGREGATES","audits":out,
  "all_official_counts_match":all(x["matched"] for x in out.values()),
  "certified_historical_pit":False,"formal_signal_allowed":False}
Path("v113_month_end_audit").mkdir(exist_ok=True)
Path("v113_month_end_audit/audit.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(report,ensure_ascii=False))
