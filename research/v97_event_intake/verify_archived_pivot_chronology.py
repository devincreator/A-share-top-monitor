#!/usr/bin/env python3
"""Independently audit archived, RETROSPECTIVE 5/9% pivot chronology.

Only reads frozen original-source derivatives. Does not import the generator.
Pass means each reported label is structurally plausible and first confirmed
at its stated historical close, NOT that historical alerts existed or labels
were known at the turning-day preopen.
"""
import argparse
from collections import Counter
import csv
from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path

THRESHOLDS={"5":Decimal("0.05"),"9":Decimal("0.09")}
SOURCE_INDEX="000985.CSI"
EXPECTED_SESSION_COUNT=1128
EXPECTED_COUNTS={"5":39,"9":19}
EXPECTED_FIRST="2022-02-23"
EXPECTED_LAST="2026-10-20"


def rows(raw):
    content=raw.decode("utf-8-sig")
    reader=csv.DictReader(content.splitlines())
    if not reader.fieldnames:
        raise ValueError("CSV missing header")
    values=list(reader)
    if not values:
        raise ValueError("CSV has no records")
    return values


def indexed_prices(records):
    result=[]
    previous=None
    for row in records:
        day=date.fromisoformat(row["date"])
        if day.weekday()>=5 or (previous is not None and day<=previous):
            raise ValueError("duplicate/weekend/unsorted index price session")
        try:
            close=Decimal(row["close"])
        except (InvalidOperation, KeyError) as err:
            raise ValueError("unparseable price") from err
        if not close.is_finite() or close<=0:
            raise ValueError("nonpositive/nonfinite close")
        result.append((day.isoformat(),close))
        previous=day
    return result


def verify(prices,labels):
    prices=indexed_prices(prices)
    pos={d:i for i,(d,_) in enumerate(prices)}
    errors=[]
    summary={}
    for scale,threshold in THRESHOLDS.items():
        current=[p for p in labels if p.get("scale")==scale]
        last_confirm=None
        last_direction=None
        observed_ids=set()
        yearly=Counter()
        for j,p in enumerate(current):
            uid=p.get("id","")
            if uid in observed_ids:
                errors.append({"id":uid,"error":"duplicate pivot id"})
            observed_ids.add(uid)
            turning=p.get("date")
            confirm=p.get("confirmation_date")
            if turning not in pos or confirm not in pos:
                errors.append({"id":uid,"error":"unobserved label or confirmation date"})
                continue
            ti,ci=pos[turning],pos[confirm]
            if ti>=ci:
                errors.append({"id":uid,"error":"confirmation not later than extreme"})
                continue
            direction=p.get("direction")
            if direction not in ("TOP","BOTTOM") or last_direction==direction:
                errors.append({"id":uid,"error":"nonalternating direction"})
                continue
            if last_confirm is not None and ti<last_confirm:
                errors.append({"id":uid,"error":"turning extreme precedes prior confirmation"})
                continue
            if (p.get("first_segment_left_censored")=="true") != (j==0):
                errors.append({"id":uid,"error":"left censor flag inconsistent with sample start"})
                continue
            try:
                recorded_extreme=Decimal(p["extreme_close"])
            except (InvalidOperation,KeyError):
                errors.append({"id":uid,"error":"unparseable extreme"})
                continue
            if recorded_extreme!=prices[ti][1]:
                errors.append({"id":uid,"error":"recorded extreme not equal to original daily close"})
            if p.get("id")!=f"{scale}_{direction}_{turning}":
                errors.append({"id":uid,"error":"pivot identity does not match scale/direction/date"})
            if j>0:
                values=[v for _,v in prices[last_confirm:ti+1]]
                if ((direction=="TOP" and recorded_extreme!=max(values)) or
                    (direction=="BOTTOM" and recorded_extreme!=min(values))):
                    errors.append({"id":uid,"error":"not first-segment high/low after prior confirmation"})
            if direction=="TOP":
                if prices[ci][1]>recorded_extreme*(1-threshold):
                    errors.append({"id":uid,"error":"top reversal threshold not met on confirmation"})
                if any(v>recorded_extreme or v<=recorded_extreme*(1-threshold)
                       for _,v in prices[ti+1:ci]):
                    errors.append({"id":uid,"error":"earlier reversal or later higher high before confirmation"})
            else:
                if prices[ci][1]<recorded_extreme*(1+threshold):
                    errors.append({"id":uid,"error":"bottom reversal threshold not met on confirmation"})
                if any(v<recorded_extreme or v>=recorded_extreme*(1+threshold)
                       for _,v in prices[ti+1:ci]):
                    errors.append({"id":uid,"error":"earlier reversal or later lower low before confirmation"})
            next_day=prices[ci+1][0] if ci+1<len(prices) else ""
            if p.get("earliest_possible_preopen_day_after_confirmation")!=next_day:
                errors.append({"id":uid,"error":"incorrect earliest possible later-session date"})
            # A label is never observable by opening time on its own close-confirmation day.
            if next_day and not (turning<confirm<next_day):
                errors.append({"id":uid,"error":"confirmation chronology invalid"})
            yearly[turning[:4]]+=1
            last_confirm=ci
            last_direction=direction
        summary[scale]={"reported_labels":len(current),
            "left_censored":sum(x.get("first_segment_left_censored")=="true" for x in current),
            "labels_by_turning_year":dict(sorted(yearly.items()))}
    unknown=[p.get("id") for p in labels if p.get("scale") not in THRESHOLDS]
    if unknown:
        errors.append({"error":"unexpected scale","examples":unknown[:5]})
    return {"chronology_invariants_passed":not errors,"errors":errors,
            "observed_price_sessions":len(prices),
            "first_observed_price_day":prices[0][0],
            "last_observed_price_day":prices[-1][0],
            "scale_summary":summary,
            "formal_start_alerts_restored":False,
            "historical_feature_PIT_certified":False,
            "formal_signal_allowed":False,
            "double80_achieved":False,
            "limitations":"Checking reported labels cannot prove no labels were omitted; a confirmed label is an ex-post result, never a preopen signal."}


def audit_file_bundle(folder):
    root=Path(folder)
    manifest_raw=(root/"partial_v52_pivot_manifest.json").read_bytes()
    manifest=json.loads(manifest_raw)
    price_raw=(root/"index_000985_prices_20220223_20261020.csv").read_bytes()
    pivot_raw=(root/"partial_v52_derived_objective_pivots.csv").read_bytes()
    if (manifest.get("source_index")!=SOURCE_INDEX or
        hashlib.sha256(price_raw).hexdigest()!=manifest["price_csv_sha256"] or
        hashlib.sha256(pivot_raw).hexdigest()!=manifest["objective_pivots_csv_sha256"]):
        raise ValueError("original frozen label source identity/SHA check failed")
    prices=rows(price_raw)
    labels=rows(pivot_raw)
    result=verify(prices,labels)
    if result["observed_price_sessions"]!=EXPECTED_SESSION_COUNT or (
        result["first_observed_price_day"],result["last_observed_price_day"]
    )!=(EXPECTED_FIRST,EXPECTED_LAST):
        raise ValueError("price observation window has changed")
    for scale,count in EXPECTED_COUNTS.items():
        if result["scale_summary"][scale]["reported_labels"]!=count:
            raise ValueError("frozen label count mismatch")
        if result["scale_summary"][scale]["left_censored"]!=1:
            raise ValueError("initial truncated labels must remain explicitly censored")
    result["status"]=("ARCHIVED_OBJECTIVE_LABEL_CHRONOLOGY_VERIFIED_NOT_PIT"
                      if result["chronology_invariants_passed"]
                      else "BLOCKED_INCONSISTENT_RETROSPECTIVE_LABELS")
    result["price_csv_sha256"]=hashlib.sha256(price_raw).hexdigest()
    result["pivot_csv_sha256"]=hashlib.sha256(pivot_raw).hexdigest()
    result["source_manifest_sha256"]=hashlib.sha256(manifest_raw).hexdigest()
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--observations",default="research/v97_event_intake/observations")
    p.add_argument("--output",default="v97_chronology_verification/chronology_report.json")
    args=p.parse_args()
    report=audit_file_bundle(args.observations)
    out=Path(args.output)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":report["status"],
                      "labels":{x:y["reported_labels"] for x,y in report["scale_summary"].items()},
                      "errors":len(report["errors"]),"formal_signal_allowed":False},
                     ensure_ascii=False))
    if not report["chronology_invariants_passed"]:
        raise SystemExit(2)


if __name__=="__main__":
    main()
