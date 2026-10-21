#!/usr/bin/env python3
"""Second-pass independent 5/9% close-reversal stream audit on archived data.

Unlike chronology checks that only inspect EXISTING labels, this pass walks
every archived price close and independently enumerates ALL qualifying
reversal events in this bounded series, then compares the frozen event list.

Result is RETROSPECTIVE OBJECTIVE LABEL completeness within archived window
only; it does not recover original FORMAL_START alerts, historical PIT clocks,
or certify the full original V52 2015-2026 event population.
"""
import argparse
import csv
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
from pathlib import Path

SCALES={"5":Decimal("0.05"),"9":Decimal("0.09")}
PREFIX="index_000985_prices_20220223_20261020.csv"
LABELS="partial_v52_derived_objective_pivots.csv"
MANIFEST="partial_v52_pivot_manifest.json"


def load_csv(raw):
    reader=csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    if not reader.fieldnames:
        raise ValueError("missing CSV header")
    return list(reader)


def calculate_all_reversals(price_rows,scale):
    """Alternative streaming state machine. Never imports prior V52 replayer."""
    threshold=SCALES[scale]
    points=[]
    prev=None
    for row in price_rows:
        day=row["date"]
        try:
            value=Decimal(str(row["close"]))
        except (ValueError,InvalidOperation,TypeError) as exc:
            raise ValueError("invalid source close") from exc
        if prev is not None and day<=prev:
            raise ValueError("price sessions not strictly increasing")
        if not value.is_finite() or value<=0:
            raise ValueError("nonpositive or nonfinite original close")
        points.append((day,value))
        prev=day
    if len(points)<3:
        raise ValueError("less than three source closing prices")
    max_idx=min_idx=0
    state="SEARCH"
    found=[]
    for k in range(1,len(points)):
        current=points[k][1]
        peak=points[max_idx][1]
        trough=points[min_idx][1]
        if state=="SEARCH":
            down_cross=current<=peak*(Decimal(1)-threshold)
            up_cross=current>=trough*(Decimal(1)+threshold)
            if down_cross and (not up_cross or max_idx>min_idx):
                found.append((max_idx,k,"TOP",True))
                min_idx=k
                state="FALL"
            elif up_cross:
                found.append((min_idx,k,"BOTTOM",True))
                max_idx=k
                state="RISE"
            else:
                if current>peak:
                    max_idx=k
                if current<trough:
                    min_idx=k
        elif state=="RISE":
            if current>peak:
                max_idx=k
            elif current<=peak*(Decimal(1)-threshold):
                found.append((max_idx,k,"TOP",False))
                min_idx=k
                state="FALL"
        else:
            if current<trough:
                min_idx=k
            elif current>=trough*(Decimal(1)+threshold):
                found.append((min_idx,k,"BOTTOM",False))
                max_idx=k
                state="RISE"
    events=[]
    for extreme,confirmed,direction,left in found:
        extreme_date,extreme_price=points[extreme]
        next_day=points[confirmed+1][0] if confirmed+1<len(points) else ""
        events.append({
            "id":f"{scale}_{direction}_{extreme_date}",
            "date":extreme_date,"scale":scale,"direction":direction,
            "confirmation_date":points[confirmed][0],
            "extreme_close":str(extreme_price),
            "first_segment_left_censored":"true" if left else "false",
            "earliest_possible_preopen_day_after_confirmation":next_day
        })
    if state=="SEARCH":
        trailing={"status":"NO_CONFIRMED_DIRECTION","date":points[-1][0]}
    else:
        idx=max_idx if state=="RISE" else min_idx
        trailing={"status":"UNCONFIRMED_TRAILING_EXTREME",
                  "candidate_direction":"TOP" if state=="RISE" else "BOTTOM",
                  "candidate_date":points[idx][0],
                  "candidate_close":str(points[idx][1]),
                  "not_an_objective_confirmed_pivot":True}
    return events,trailing


def compare_complete(price_rows,archived_labels):
    result={"status":"BLOCKED","research_only":True,"formal_signal_allowed":False,
        "original_formal_start_restored":False,
        "historical_price_publication_PIT_verified":False,
        "full_2015_2026_V52_reproduced":False,
        "comparison_scope":"2022-02-23 through 2026-10-20, 000985.CSI only",
        "independent_reversal_enumeration_complete_within_bounded_price_series":False,
        "scale_checks":{},"discrepancies":[]}
    expected_fields=("id","date","scale","direction","confirmation_date",
                     "extreme_close","first_segment_left_censored",
                     "earliest_possible_preopen_day_after_confirmation")
    for scale in SCALES:
        computed,trailing=calculate_all_reversals(price_rows,scale)
        recorded=[x for x in archived_labels if x.get("scale")==scale]
        expected={e["id"]:e for e in computed}
        observed={}
        for row in recorded:
            uid=row.get("id")
            if uid in observed:
                result["discrepancies"].append({"scale":scale,"id":uid,"reason":"DUPLICATE_ARCHIVED_ID"})
            observed[uid]=row
        omitted=sorted(set(expected)-set(observed))
        extra=sorted(set(observed)-set(expected))
        for uid in omitted:
            result["discrepancies"].append({"scale":scale,"id":uid,"reason":"MISSING_CONFIRMED_REVERSAL"})
        for uid in extra:
            result["discrepancies"].append({"scale":scale,"id":uid,"reason":"UNSUPPORTED_ARCHIVED_LABEL"})
        mismatched=[]
        for uid in sorted(set(expected)&set(observed)):
            for field in expected_fields:
                a=str(expected[uid].get(field,""))
                b=str(observed[uid].get(field,""))
                if field=="extreme_close":
                    try:
                        same=Decimal(a)==Decimal(b)
                    except InvalidOperation:
                        same=False
                else:
                    same=a==b
                if not same:
                    mismatched.append({"id":uid,"field":field,
                                      "derived":a,"archived":b})
        result["discrepancies"].extend(dict(scale=scale,reason="FIELD_MISMATCH",**m)
                                        for m in mismatched)
        result["scale_checks"][scale]={
            "independently_generated_confirmed_reversals":len(computed),
            "original_archived_candidate_labels":len(recorded),
            "missing_labels":len(omitted),
            "extra_labels":len(extra),
            "mismatched_fields":len(mismatched),
            "left_censored_initial":sum(e["first_segment_left_censored"]=="true"
                                        for e in computed),
            "unconfirmed_trailing_candidate":trailing,
            "original_formal_alerts_recovered":False
        }
    unknown=[x.get("id") for x in archived_labels if x.get("scale") not in SCALES]
    if unknown:
        result["discrepancies"].append({"reason":"UNEXPECTED_SCALE","ids":unknown[:12]})
    if not result["discrepancies"]:
        result["status"]="BOUNDED_LABEL_ENUMERATION_MATCHED_NOT_ORIGINAL_ALERTS_OR_PIT"
        result["independent_reversal_enumeration_complete_within_bounded_price_series"]=True
    return result


def audit_archive(folder):
    root=Path(folder)
    raw_price=(root/PREFIX).read_bytes()
    raw_labels=(root/LABELS).read_bytes()
    raw_manifest=(root/MANIFEST).read_bytes()
    manifest=json.loads(raw_manifest)
    if manifest.get("source_index")!="000985.CSI":
        raise ValueError("wrong market index identity")
    if manifest["price_csv_sha256"]!=hashlib.sha256(raw_price).hexdigest():
        raise ValueError("frozen price SHA mismatch")
    if manifest["objective_pivots_csv_sha256"]!=hashlib.sha256(raw_labels).hexdigest():
        raise ValueError("frozen label SHA mismatch")
    data=load_csv(raw_price)
    if (len(data)!=1128 or data[0]["date"]!="2022-02-23"
            or data[-1]["date"]!="2026-10-20"):
        raise ValueError("unexpected frozen price session boundary")
    result=compare_complete(data,load_csv(raw_labels))
    result.update(source_index=manifest["source_index"],
                  observed_price_sessions=len(data),
                  frozen_price_sha256=hashlib.sha256(raw_price).hexdigest(),
                  frozen_labels_sha256=hashlib.sha256(raw_labels).hexdigest(),
                  manifest_sha256=hashlib.sha256(raw_manifest).hexdigest())
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--observations",default="research/v97_event_intake/observations")
    parser.add_argument("--output",default="v97_label_completeness_output/completeness.json")
    args=parser.parse_args()
    status=audit_archive(args.observations)
    out=Path(args.output)
    out.parent.mkdir(parents=True,exist_ok=True)
    material=(json.dumps(status,ensure_ascii=False,indent=2)+"\n")
    if out.exists() and out.read_text(encoding="utf-8")!=material:
        raise ValueError("immutable completeness audit already exists with different content")
    if not out.exists():
        out.write_text(material,encoding="utf-8")
    print(json.dumps({"status":status["status"],"scales":status["scale_checks"],
                      "discrepancies":len(status["discrepancies"]),
                      "original_formal_start_restored":False,
                      "formal_signal_allowed":False},ensure_ascii=False))
    if status["discrepancies"]:
        raise SystemExit(2)


if __name__=="__main__":
    main()
