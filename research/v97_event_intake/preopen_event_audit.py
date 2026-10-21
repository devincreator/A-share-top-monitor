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
from decimal import Decimal, InvalidOperation
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
    seen_task_day=set()
    pivots_by_scale={scale:[] for scale in SCALES}
    for row in pivots:
        for field in ("id","date","scale","direction","confirmation_date"):
            if not row.get(field):
                raise ValueError(f"pivot missing {field}")
        if row["scale"] not in SCALES or row["direction"] not in DIRECTIONS:
            raise ValueError("invalid pivot task")
        censor_flag=str(row.get("first_segment_left_censored","false")).lower()
        if censor_flag not in ("true","false"):
            raise ValueError("invalid left-censor flag")
        if row["id"] in seen:
            raise ValueError("duplicate pivot id")
        seen.add(row["id"])
        key=(row["scale"],row["date"])
        if key in seen_task_day:
            raise ValueError("duplicate scale/date objective pivot, possibly double-counted recall")
        seen_task_day.add(key)
        d=date.fromisoformat(row["date"])
        confirmation=date.fromisoformat(row["confirmation_date"])
        if d not in pos or confirmation not in pos:
            raise ValueError("pivot or confirmation beyond observed evaluation calendar")
        if confirmation<=d:
            raise ValueError("pivot confirmed on or before turning date")
        pivots_by_scale[row["scale"]].append(row)
    for scale, rows in pivots_by_scale.items():
        left=[p for p in rows if str(p.get("first_segment_left_censored","false")).lower()=="true"]
        if len(left)>1:
            raise ValueError(f"{scale}: multiple left-censored initial pivots")
        if left and left[0]["id"]!=min(rows,key=lambda p:(p["date"],p["id"]))["id"]:
            raise ValueError(f"{scale}: left-censored label must be earliest pivot in this scale")


def max_match(alerts,pivots,pos,max_lead):
    """Chronological, maximum-cardinality one-to-one matching, no hindsight preference.

    All alerts in one scale/direction share the same STRICT lead window
    [1, max_lead] in index trading sessions. For this ordered interval
    matching problem, assign the earliest still-eligible pivot to each alert
    in alert-date order. This is maximum-cardinality (exchange argument):
    if an optimal assignment sends an earlier alert to a later pivot, swap
    it with any earlier pivot assigned to a later alert, or occupy the
    earlier available pivot; neither lead bound is violated by the swap.

    Unlike augmenting-path DFS, this preserves non-crossing chronological
    order among matched events, avoiding artificial reversal of which alarm
    preceded which turning point. Both input lists MUST be chronological;
    caller audit_preopen() sorts its four tasks before matching.
    """
    alert_days=[pos[date.fromisoformat(a["date"])] for a in alerts]
    pivot_days=[pos[date.fromisoformat(p["date"])] for p in pivots]
    if any(alert_days[k]<alert_days[k-1] for k in range(1,len(alert_days))):
        raise ValueError("one-to-one matcher alerts not chronological")
    if any(pivot_days[k]<pivot_days[k-1] for k in range(1,len(pivot_days))):
        raise ValueError("one-to-one matcher pivots not chronological")
    if not isinstance(max_lead,int) or max_lead<1:
        raise ValueError("positive integer lead window required")

    matched={}
    pi=0
    for ai,aday in enumerate(alert_days):
        while pi<len(pivot_days) and pivot_days[pi]<=aday:
            pi+=1  # Cannot predict a pivot on or before its own trading date.
        if pi<len(pivot_days) and 1<=pivot_days[pi]-aday<=max_lead:
            matched[ai]=pi
            pi+=1
    return matched


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
                    continue
                # A timestamp and source URL do NOT prove that a separately
                # archived retrospective close is the value seen at decision.
                # Require the claimed contemporaneous close itself and make
                # sure it agrees exactly (in decimal price units) with the
                # price record used to describe the market regime.
                claimed=price_evidence.get("observation_value")
                try:
                    if isinstance(claimed,bool) or claimed is None:
                        raise ValueError("INDEX_CLOSE source observed numeric value absent")
                    candidate=Decimal(str(claimed))
                    archived=Decimal(str(price_rows[last]["close"]))
                    if not candidate.is_finite() or candidate<=0:
                        raise ValueError("INDEX_CLOSE source observed value invalid")
                    if not archived.is_finite() or archived<=0:
                        raise ValueError("historical price archive close invalid")
                    if candidate!=archived:
                        raise ValueError("INDEX_CLOSE claimed source value disagrees with archived market-regime close")
                    price_asof_idx[aid]=last
                except (InvalidOperation,ValueError,TypeError) as exc:
                    bad.append({"id":aid,"issues":[str(exc)]})
    baseline={"research_only":True,"formal_signal_allowed":False,
        "evaluation_asof":asof,"maturity_buffer_sessions":MATURITY_BUFFER,
        "clock_verification":"CANDIDATE_SOURCE_METADATA_NOT_INDEPENDENT_PIT_AUDIT",
        "market_regime_clock":"EFFECTIVE_INDEX_CLOSE_SOURCE_OBSERVATION_DATE_NOT_ASSUMED_D_MINUS_1",
        "market_regime_endpoint_matches_claimed_source_value":not bool(bad),
        "market_regime_lookback_vintage_independently_PIT_certified":False,
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
            # Truncated price archives can have a left-boundary extreme with
            # unobserved prior trend. Such a label can never count as an FN/TP.
            # Exclude alerts whose lead window intersects it from FP as well.
            left_censored_p=[p for p in pp
                if str(p.get("first_segment_left_censored","false")).lower()=="true"]
            eligible_p=[p for p in pp if p not in left_censored_p]
            # A normal objective pivot enters the denominator only after its
            # actual confirmation day plus the 140-session maturity buffer.
            mature_p=[p for p in eligible_p if
                      pos[date.fromisoformat(p["confirmation_date"])]+MATURITY_BUFFER<len(days)]
            mapping=max_match(aa,mature_p,pos,max_lead)
            immature_p=[p for p in eligible_p if p not in mature_p]
            events=[]
            for i,a in enumerate(aa):
                a_idx=pos[date.fromisoformat(a["date"])]
                pivot=mature_p[mapping[i]] if i in mapping else None
                if pivot is not None:
                    kind="TP"
                elif any(1 <= pos[date.fromisoformat(p["date"])]-a_idx <= max_lead
                         for p in left_censored_p):
                    # Unknown pre-sample trend, so neither a confirmed hit nor
                    # a defensible false positive in this truncated archive.
                    kind="EXCLUDED_LEFT_CENSORED"
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
            excluded=sum(e["result"]=="EXCLUDED_LEFT_CENSORED" for e in events)
            fn=len(mature_p)-tp
            data[key]={
                "status":"RESEARCH_EVENT_REPLAY_ONLY_NOT_PIT",
                "tp":tp,"fp":fp,"fn":fn,"pending":pending,
                "excluded_left_censored_alerts":excluded,
                "excluded_left_censored_pivots":len(left_censored_p),
                "scored_formal_alerts":tp+fp,
                "formal_alerts":len(aa),"mature_pivots":len(mature_p),
                "precision_scored":tp/(tp+fp) if tp+fp else None,
                "recall_mature":tp/len(mature_p) if mature_p else None,
                "error_regimes":dict(Counter(e["regime_using_prior_day"]
                                  for e in events if e["result"]=="FP")),
                "events":events
            }
    return {**baseline,"status":"RESEARCH_PREOPEN_SCHEMA_REPLAY_UNCERTIFIED",
            "boundary_policy":"LEFT_CENSORED_PIVOT_EXCLUDED_AND_NEARBY_ALERT_NOT_FALSE_POSITIVE",
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
