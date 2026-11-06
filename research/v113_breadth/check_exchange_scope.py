#!/usr/bin/env python3
import csv,json,collections
from pathlib import Path
root=Path("v113_baostock_pilot")
def read(p):
 with (root/p).open(newline="",encoding="utf-8") as f:return list(csv.DictReader(f))
basic=read("stock_basic.csv")
def cs(rows):
 result=collections.Counter()
 for r in rows:
  if r.get("type") not in (None,"1"):continue
  code=r["code"]
  prefix=code.split(".")[0]
  if prefix=="sz":classification="SHENZHEN"
  elif prefix=="sh":classification="SHANGHAI"
  elif prefix=="bj":classification="BEIJING"
  else:classification="OTHER"
  result[classification]+=1
  if prefix in ("sh","sz") and code.split(".")[1][:1] in ("4","8","9"):
   result["NON_STANDARD_"+prefix+"_"+code.split(".")[1][:2]]+=1
 return result
stats={"basic_equity":cs(basic)}
for date in ("2022-06-20","2025-01-02","2026-09-21","2026-10-21"):
 stocks=read("stocks_"+date+".csv")
 bycode={r["code"] for r in basic if r["type"]=="1"}
 stats[date]=cs([{"code":r["code"],"type":"1"} for r in stocks if r["code"] in bycode])
print(json.dumps(stats,ensure_ascii=False))
