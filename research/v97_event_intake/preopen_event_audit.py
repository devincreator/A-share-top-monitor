#!/usr/bin/env python3
"""Research-only one-to-one top/bottom event replay at a strict pre-open clock.

Unlike legacy descriptive V86, market regime attribution ends at t-1 and
unmatured unmatched events are PENDING rather than retroactively called FP.
Original dated FORMAL_START and pivot records are required; no fake events.
"""
import argparse
import csv
from collections import Counter
from datetime import date
import hashlib
import json
import math
from pathlib import Path

from preopen_clock import inspect_prediction

SCALES={"5":10,"9":20}
DIRECTIONS=("TOP","BOTTOM")
MATURITY_BUFFER=140


def normalized_price_days(rows,asof):
    dates=[];closes=[]
    for row in rows:
        d=date.fromisoformat(row["date"])
        v=float(row["close"])
        if not math.isfinite(v) or v<=0:
            raise ValueError("price close missing/invalid")
        if dates and d<=dates[-1]:
            raise ValueError("price days not strictly increasing")
        dates.append(d);closes.append(v)
    cutoff=date.fromisoformat(asof)
    if cutoff not in dates:
        raise ValueError("evaluation date must exist in price trading observations")
    n=dates.index(cutoff)+1
    return dates[:n],closes[:n]


def market_regime_asof(last_observable_close_index,closes):
    """Descriptive regime ends at the source-observation date actually available.

    Do not silently use D-1 when only D-2 (or an older close) had already
    been published at the historical D pre-open decision.
    """
    if last_observable_close_index is None:
        return "NO_INDEX_CLOSE_ASOF_SOURCE"
    last=last_observable_close_index
    if last<120:
        return "INSUFFICIENT_PREOPEN_HISTORY"
    r60=closes[last]/closes[last-60]-1
    r120=closes[last]/closes[last-120]-1
    if r60<-0.10 and r120<0:
        return "DOWNTREND_RALLY_RISK"
    if r60>0.10 and r120>0:
        return "UPTREND"
    return "MIXED_OR_RANGE"


def validate_events(alerts,pivots,days,asof):
    pos={day:i for i,day in enumerate(days)}
    seen=set()
    for row in alerts:
        for field in ("id","date","scale","direction","event_type","decision_at"):
            if not row.get(field):
                raise ValueError(f"alert missing {field}")
        if row["event_type"]!="FORMAL_START":
            raise ValueError("ACTIVE/continuation events cannot count as formal starts")
        if row["scale"] not in SCALES or row["direction"] not in DIRECTIONS:
            raise ValueError("invalid alert task")
        if row["id"] in seen:
            raise ValueError("duplicate formal alert id")
        seen.add(row["id"])
        d=date.fromisoformat(row["date"])
        if d not in pos:
            raise ValueError("formal alert day outside price index calendar/asof")
    seen=set()
    for row in pivots:
        for field in ("id","date","scale","direction","confirmation_date"):
            if not row.get(field):
                raise ValueError(f"pivot missing {field}")
        if row["scale"] not in SCALES or row["direction"] not in DIRECTIONS:
            raise ValueError("invalid pivot task")
        if str(row.get("first_segment_left_censored","false")).lower()=="true":
            raise ValueError("left-censored initial label cannot enter objective pivot denominator")
        if row["id"] in seen:
            raise ValueError("duplicate pivot id")
        seen.add(row["id"])
        d=date.fromisoformat(row["date"])
        confirmation=date.fromisoformat(row["confirmation_date"])
        if d not in pos or confirmation not in pos:
            raise ValueError("pivot or confirmation beyond observed evaluation calendar")
        if confirmation<d:
            raise ValueError("pivot confirmed before turning date")


def max_match(alerts,pivots,pos,max_lead):
    """Deterministic max-cardinality bipartite matching."""
    arcs=[]
    for a in alerts:
        options=[]
        for i,p in enumerate(pivots):
            gap=pos[date.fromisoformat(p["date"])]-pos[date.fromisoformat(a["date"])]
            if 1<=gap<=max_lead:
                options.append((gap,i))
        arcs.append([index for _,index in sorted(options)])
    assigned={}
    def dfs(ai,used):
        for pi in arcs[ai]:
            if pi in used:
                continue
            used.add(pi)
            if pi not in assigned or dfs(assigned[pi],used):
                assigned[pi]=ai
                return True
        return False
    for i in range(len(alerts)):
        dfs(i,set())
    return {ai:pi for pi,ai in assigned.items()}


def audit_preopen(alerts,pivots,price_rows,availability,required_factors,asof):
    days,closes=normalized_price_days(price_rows,asof)
    pos={d:i for i,d in enumerate(days)}
    validate_events(alerts,pivots,days,asof)
    if not isinstance(availability,dict) or not required_factors:
        raise ValueError("real per-alert factor publication evidence required")
    clock={}
    price_asof_idx={}
    bad=[]
    for alert in alerts:
        aid=alert["id"]
        report=inspect_prediction(
            {"id":aid,"prediction_date":alert["date"],"decision_at":alert["decision_at"]},
            availability.get(aid,[]),required_factors)
        clock[aid]=report
        if report["status"]!="PREOPEN_SCHEMA_VALID_REQUIRES_SOURCE_AUTHENTICATION":
            bad.append({"id":aid,"issues":report["errors"]})
            continue
        # The disclosure gate proves a *candidate* index close at a specific
        # observation date, not automatically the last D-1 close. If no price
        # factor was part of the prediction contract, regime must stay unknown.
        price_evidence=next((row for row in availability.get(aid,[])
                             if row.get("factor")=="INDEX_CLOSE"),None)
        if price_evidence is None:
            price_asof_idx[aid]=None
        else:
            observed=date.fromisoformat(price_evidence["observation_date"])
            if observed not in pos:
                bad.append({"id":aid,"issues":["INDEX_CLOSE source observation date absent from archived price calendar"]})
            else:
                last=pos[observed]
                if last>=pos[date.fromisoformat(alert["date"])]:
                    bad.append({"id":aid,"issues":["INDEX_CLOSE source observation is not strictly earlier than forecast"]})
                else:
                    price_asof_idx[aid]=last
    baseline={"research_only":True,"formal_signal_allowed":False,
        "evaluation_asof":asof,"maturity_buffer_sessions":MATURITY_BUFFER,
        "clock_verification":"CANDIDATE_SOURCE_METADATA_NOT_INDEPENDENT_PIT_AUDIT",
        "market_regime_clock":"EFFECTIVE_INDEX_CLOSE_SOURCE_OBSERVATION_DATE_NOT_ASSUMED_D_MINUS_1",
        "scored_legacy_results_not_portable_to_preopen":True}
    if bad:
        return {**baseline,"status":"BLOCKED_FEATURE_CLOCK_OR_PROVENANCE",
                "invalid_alert_clock_examples":bad[:20],"invalid_alert_count":len(bad),
                "tasks":{}}
    data={}
    for scale,max_lead in SCALES.items():
        for direction in DIRECTIONS:
            key=f"{scale}_{direction}"
            aa=sorted((a for a in alerts if a["scale"]==scale and a["direction"]==direction),
                      key=lambda a:(a["date"],a["id"]))
            pp=sorted((p for p in pivots if p["scale"]==scale and p["direction"]==direction),
                      key=lambda p:(p["date"],p["id"]))
            # Pivots are scored only once both their confirmation date and
            # an additional conservative maturity buffer have elapsed.
            mature_p=[p for p in pp if
                      pos[date.fromisoformat(p["confirmation_date"])]+MATURITY_BUFFER<len(days)]
            mapping=max_match(aa,mature_p,pos,max_lead)
            immature_p=[p for p in pp if p not in mature_p]
            events=[]
            for i,a in enumerate(aa):
                a_idx=pos[date.fromisoformat(a["date"])]
                pivot=mature_p[mapping[i]] if i in mapping else None
                if pivot is not None:
                    kind="TP"
                elif any(1 <= pos[date.fromisoformat(p["date"])]-a_idx <= max_lead
                         for p in immature_p):
                    # A retrospectively observed turning label may still be
                    # awaiting its own confirmation maturity. Never call the
                    # matching alert a false positive before it matures.
                    kind="PENDING"
                elif a_idx+max_lead+MATURITY_BUFFER<len(days):
                    kind="FP"
                else:
                    kind="PENDING"
                events.append({
                    "alert_id":a["id"],"decision_at":a["decision_at"],
                    "alert_date":a["date"],"result":kind,
                    "regime_at_available_price":market_regime_asof(price_asof_idx.get(a["id"]),closes),
                    "regime_using_prior_day":market_regime_asof(price_asof_idx.get(a["id"]),closes),
                    "last_feature_price_date":(days[price_asof_idx[a["id"]]].isoformat()
                                               if price_asof_idx.get(a["id"]) is not None else None),
                    "market_regime_provenance":"SOURCE_TIME_SCHEMA_CANDIDATE_NOT_INDEPENDENT_PIT_CERTIFICATION",
                    "pivot_id":pivot["id"] if pivot else None,
                    "lead_trading_days":pos[date.fromisoformat(pivot["date"])]-a_idx if pivot else None})
            tp=sum(e["result"]=="TP" for e in events)
            fp=sum(e["result"]=="FP" for e in events)
            pending=sum(e["result"]=="PENDING" for e in events)
            fn=len(mature_p)-tp
            data[key]={
                "status":"RESEARCH_EVENT_REPLAY_ONLY_NOT_PIT",
                "tp":tp,"fp":fp,"fn":fn,"pending":pending,
                "formal_alerts":len(aa),"mature_pivots":len(mature_p),
                "precision_scored":tp/(tp+fp) if tp+fp else None,
                "recall_mature":tp/len(mature_p) if mature_p else None,
                "error_regimes":dict(Counter(e["regime_using_prior_day"]
                                  for e in events if e["result"]=="FP")),
                "events":events
            }
    return {**baseline,"status":"RESEARCH_PREOPEN_SCHEMA_REPLAY_UNCERTIFIED",
            "tasks":data,
            "warning":"Not proof of authentic source event identity, raw factor PIT, matured label completeness or out-of-sample model performance."}


def read_csv(path):
    with open(path,encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--alerts",required=True)
    p.add_argument("--pivots",required=True)
    p.add_argument("--prices",required=True)
    p.add_argument("--availability-json",required=True)
    p.add_argument("--asof",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    paths=[a.alerts,a.pivots,a.prices,a.availability_json]
    out=Path(a.output)
    out.parent.mkdir(parents=True,exist_ok=True)
    if any(not Path(s).is_file() for s in paths):
        result={"status":"BLOCKED_ORIGINAL_EVENTS_OR_AVAILABILITY_MISSING",
                "required_inputs":paths,"present":[Path(s).is_file() for s in paths],
                "tasks":{},"formal_signal_allowed":False}
    else:
        original={s:hashlib.sha256(Path(s).read_bytes()).hexdigest() for s in paths}
        availability=json.loads(Path(a.availability_json).read_text())
        result=audit_preopen(read_csv(a.alerts),read_csv(a.pivots),read_csv(a.prices),
                             availability["by_alert_id"],availability["required_factors"],a.asof)
        result["input_sha256"]=original
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print(json.dumps({"status":result["status"],
                      "formal_signal_allowed":False},ensure_ascii=False))


if __name__=="__main__":
    main()
