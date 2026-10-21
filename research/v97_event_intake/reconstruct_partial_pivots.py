#!/usr/bin/env python3
"""Independently reconstruct retrospective objective pivots from REAL CSI index prices.

This is the V52 report's frozen 5%/9% ZigZag rule independently implemented
for a truncated 2022-2026 index source. Pivots are LABELS, NEVER preopen alerts.
Confirmation-date close is hindsight at that day's preopen; it can only be a
candidate historical known label from a later date after publication evidence.
"""
import argparse
import csv
from datetime import date
import hashlib
import io
import json
import math
from pathlib import Path

SOURCE_SHA="00fde1c9602b02be19b4c061f80041a9eda9d114addd845644c770ea3ceabce9"
SOURCE_RUN=39540193090
SCALES={"5":0.05,"9":0.09}
REFERENCE_LAST_TOP={
    "5":("2026-08-17","2026-09-11"),
    "9":("2026-08-17","2026-10-08")
}


def index_prices(data,asof):
    rows=data["indices"]["000985"]
    if len(rows)<800:
        raise ValueError("too short for this historical comparison")
    output=[]
    previous=None
    for row in rows:
        if str(row.get("code"))!="000985":
            raise ValueError("wrong historical index identity")
        d=date.fromisoformat(row["date"])
        close=float(row["close"])
        if d.weekday()>=5 or (previous is not None and d<=previous):
            raise ValueError("duplicate/out of order/weekend source price date")
        if not math.isfinite(close) or close<=0:
            raise ValueError("invalid historical index close")
        if d>date.fromisoformat(asof):
            raise ValueError("future price beyond frozen evaluation asof")
        previous=d
        output.append({"date":d.isoformat(),"close":close})
    if output[-1]["date"]!=asof:
        raise ValueError("source endpoint not equal to frozen asof")
    return output


def label_one(records,scale,threshold):
    """Alternating close-price reversal thresholds; initial pivot left-censored.

    First extreme is not treated as a fully mature, left-context-complete
    event. Equal extremes keep the earliest observation date.
    """
    if len(records)<3:
        raise ValueError("need >=3 real prices")
    high=low=records[0]["close"]
    hi=lo=0
    state="UNKNOWN"
    pivots=[]
    for i in range(1,len(records)):
        p=records[i]["close"]
        if state=="UNKNOWN":
            if p>high:
                high=p;hi=i
            if p<low:
                low=p;lo=i
            if hi>lo and p<=high*(1-threshold):
                pivots.append((hi,i,"TOP",True))
                state="DOWN";low=p;lo=i
            elif lo>hi and p>=low*(1+threshold):
                pivots.append((lo,i,"BOTTOM",True))
                state="UP";high=p;hi=i
        elif state=="UP":
            if p>high:
                high=p;hi=i
            elif p<=high*(1-threshold):
                pivots.append((hi,i,"TOP",False))
                state="DOWN";low=p;lo=i
        else:
            if p<low:
                low=p;lo=i
            elif p>=low*(1+threshold):
                pivots.append((lo,i,"BOTTOM",False))
                state="UP";high=p;hi=i
    output=[]
    for pivot_idx,confirm_idx,direction,left in pivots:
        if confirm_idx<=pivot_idx:
            raise ValueError("confirmation on/before historical turning extreme")
        next_observed_date=(records[confirm_idx+1]["date"]
                            if confirm_idx+1<len(records) else "")
        output.append({
            "id":f"{scale}_{direction}_{records[pivot_idx]['date']}",
            "date":records[pivot_idx]["date"],
            "scale":scale,
            "direction":direction,
            "confirmation_date":records[confirm_idx]["date"],
            "extreme_close":str(records[pivot_idx]["close"]),
            "earliest_possible_preopen_day_after_confirmation":next_observed_date,
            "first_segment_left_censored":"true" if left else "false",
            "source_label_status":"RETROSPECTIVE_REDERIVED_NOT_ORIGINAL_V52_SOURCE",
        })
    if len(output)!=len({p["id"] for p in output}):
        raise ValueError("duplicated objective pivot identity")
    return output


def csv_bytes(cols,rows):
    output=io.StringIO(newline="")
    writer=csv.DictWriter(output,fieldnames=cols,lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


def append_only(path,payload):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.is_file():
        if path.read_bytes()!=payload:
            raise ValueError(f"historical evidence first-capture changed: {path}")
        return "UNCHANGED"
    path.write_bytes(payload)
    return "FIRST_CAPTURE_SAVED"


def regenerate(input_path,output_dir,asof="2026-10-20"):
    source=Path(input_path).read_bytes()
    digest=hashlib.sha256(source).hexdigest()
    if digest!=SOURCE_SHA:
        raise ValueError("original 2026-10-20 V89 candidate source SHA mismatch")
    prices=index_prices(json.loads(source),asof)
    pivots=[]
    for scale,threshold in SCALES.items():
        generated=label_one(prices,scale,threshold)
        tops=[p for p in generated if p["direction"]=="TOP"]
        if not tops or (tops[-1]["date"],tops[-1]["confirmation_date"])!=REFERENCE_LAST_TOP[scale]:
            raise ValueError(f"{scale}% final top does not reproduce published V52 reference")
        pivots.extend(generated)
    pivots.sort(key=lambda p:(p["date"],p["scale"],p["direction"]))
    price_csv=csv_bytes(["date","close"],prices)
    pivot_csv=csv_bytes(["id","date","scale","direction","confirmation_date",
        "extreme_close","earliest_possible_preopen_day_after_confirmation",
        "first_segment_left_censored","source_label_status"],pivots)
    report={
        "schema_version":1,"status":"REAL_PRICE_PARTIAL_PIVOTS_RECONSTRUCTED_V52_LAST_TOP_MATCH",
        "source_name":"V89 Eastmoney 000985 historical price rows, archived 2026-10-21",
        "source_run_id":SOURCE_RUN,"source_original_candidate_sha256":digest,
        "source_index":"000985.CSI",
        "source_first_date":prices[0]["date"],"source_last_date":prices[-1]["date"],
        "observed_price_sessions":len(prices),
        "label_rule":"V52 5/9 percent alternating closing-price reversal; separately reconstructed",
        "label_left_boundary_not_full_history":True,
        "report_2015_2026_full_V52_157_points_reproduced":False,
        "reference_last_top_confirmation_matched":True,
        "scales":{scale:{
            "confirmed_pivots":sum(x["scale"]==scale for x in pivots),
            "left_censored_initial_pivots":sum(x["scale"]==scale and
                                                  x["first_segment_left_censored"]=="true" for x in pivots),
            "mature_historical_predictions_verified":0
            } for scale in SCALES},
        "original_FORMAL_START_alerts_restored":False,
        "preopen_historical_feature_timestamps_restored":False,
        "historical_PIT_certified":False,
        "formal_signal_allowed":False,
        "confirmed_after_pivot_only_for_retrospective_scoring":True,
        "original_V68_or_V52_labels_certified":False,
        "price_csv_sha256":hashlib.sha256(price_csv).hexdigest(),
        "objective_pivots_csv_sha256":hashlib.sha256(pivot_csv).hexdigest(),
        "source_limitation":"2022+ truncated retrospective price source; do not substitute for original full V52 historical data or unavailable old alarm records"
    }
    root=Path(output_dir)
    root.mkdir(parents=True,exist_ok=True)
    files={
        "index_000985_prices_20220223_20261020.csv":price_csv,
        "partial_v52_derived_objective_pivots.csv":pivot_csv,
        "partial_v52_pivot_manifest.json":(json.dumps(report,ensure_ascii=False,indent=2)+"\n").encode("utf8")
    }
    result={}
    for name,payload in files.items():
        result[name]=append_only(root/name,payload)
    print(json.dumps({"source_sessions":len(prices),"pivots_total":len(pivots),
                      "five_pivots":report["scales"]["5"]["confirmed_pivots"],
                      "nine_pivots":report["scales"]["9"]["confirmed_pivots"],
                      "source_PIT":False,"formal_signal_allowed":False,
                      "files":result},ensure_ascii=False))
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",required=True)
    p.add_argument("--out-dir",default="research/v97_event_intake/observations")
    p.add_argument("--asof",default="2026-10-20")
    a=p.parse_args()
    regenerate(a.input,a.out_dir,asof=a.asof)


if __name__=="__main__":
    main()
