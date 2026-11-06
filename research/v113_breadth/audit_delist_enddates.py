#!/usr/bin/env python3
"""Compare observed final bar against vendor outDate for every archived delisted SH/SZ stock."""
import argparse,json,csv
from collections import Counter
from pathlib import Path
def main():
 p=argparse.ArgumentParser();p.add_argument("--source-dir",required=True);p.add_argument("--out",required=True)
 a=p.parse_args();root=Path(a.source_dir);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
 records=[]
 for shard in range(24):
  doc=json.loads((root/("manifest_%02d.json"%shard)).read_text())
  for r in doc["rows"]:
   o=r.get("outDate","");last=r.get("last_date","");first=r.get("first_date","")
   if not o:continue
   if not last:kind="NO_BAR_HISTORY"
   elif last==o:kind="LAST_BAR_ON_OUTDATE"
   elif last<o:kind="LAST_BAR_BEFORE_OUTDATE"
   else:kind="BAR_AFTER_OUTDATE"
   records.append({"code":r["code"],"outDate":o,"last_bar":last,"first_bar":first,
       "classification":kind,"missing_listed_days":r.get("missing_listed_days",0)})
 counts=Counter(x["classification"] for x in records)
 res={"version":"V113-SHSZ","delisted_stock_count":len(records),"classifications":dict(counts),
      "examples":{c:[x for x in records if x["classification"]==c][:15] for c in counts},
      "outdate_missing_stock_days":sum(int(x["missing_listed_days"]) for x in records),
      "formal_signal_allowed":False}
 (out/"outdate_boundary_report.json").write_text(json.dumps(res,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps(res,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
