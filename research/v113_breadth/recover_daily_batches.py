#!/usr/bin/env python3
"""V113 actual free daily-stock files for a bounded range of observed index trading dates."""
import argparse,csv,json,time,hashlib
from pathlib import Path
from probe_daily_stock_source import probe
from reconstruct_breadth import calculate
def run(master,out,begin,end,limit):
    with open(master,newline="",encoding="utf-8") as f:
        days=[r["source_trade_date"] for r in csv.DictReader(f)
              if begin<=r["source_trade_date"]<=end]
    days=days[:limit]
    if not days:raise ValueError("NO_MATCHED_ANCHOR_DAYS")
    folder=Path(out);folder.mkdir(parents=True,exist_ok=True)
    done=[];fails=[]
    for day in days:
        response=probe(day,folder)
        for attempt in range(3):
            if "429" not in response.get("error",""):break
            time.sleep(4*(attempt+1))
            response=probe(day,folder)
        if response["status"]!="SOURCE_BYTES_OBSERVED_NOT_YET_VALIDATED":
            fails.append({"date":day,"reason":response.get("error","SOURCE_UNAVAILABLE")})
        else:
            try:
                breadth=calculate(folder/("daily_"+day.replace("-","")+".csv"),day)
                done.append(breadth)
            except Exception as e:
                fails.append({"date":day,"reason":"INVALID_RAW_"+str(e)[:120]})
        print(json.dumps({"day":day,"raw_ok":len(done),"failed":len(fails)},ensure_ascii=False),flush=True)
        time.sleep(2)
    if done:
        with (folder/"stock_breadth_reconstructed.csv").open("w",newline="",encoding="utf-8") as f:
            w=csv.DictWriter(f,fieldnames=list(done[0]));w.writeheader();w.writerows(done)
    report={"status":"RESEARCH_CANDIDATE_ONLY","requested_days":len(days),"validated_days":len(done),
        "failed_dates":fails,"range":[begin,end],"survivorship_and_suspensions_certified":False,
        "source_release_pit_certified":False,"formal_signal_allowed":False}
    (folder/"batch_coverage.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(report,ensure_ascii=False))
    return report
if __name__=="__main__":
    p=argparse.ArgumentParser()
    for name in ("master","out","begin","end"):p.add_argument("--"+name,required=True)
    p.add_argument("--limit",type=int,default=25);a=p.parse_args()
    if not 1<=a.limit<=40:raise SystemExit("LIMIT_EXCEEDED")
    run(a.master,a.out,a.begin,a.end,a.limit)
