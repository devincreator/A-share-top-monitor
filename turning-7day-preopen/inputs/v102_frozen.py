#!/usr/bin/env python3
"""V102: independent frozen V101 signal + matched-event replay, no model tuning.

Recomputes preopen price eligibility and all 59 signal dates without importing
V101 code. Checks all V101 event outcomes, detects impossible-to-predict
left-hand warmup labels, and produces immutable retrospective FP/FN evidence.
Not historical PIT or an independent blind sample.
"""
import csv
from datetime import date
from decimal import Decimal
from functools import lru_cache
import hashlib
import io
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FILES={
"prices":(ROOT/"v97_event_intake/observations/index_000985_prices_20220223_20261020.csv","f18bb93b38e6648fbd72bad53dc7fa06333cd63a01858063e1dfa50b14e7fc41"),
"pivots":(ROOT/"v97_event_intake/observations/partial_v52_derived_objective_pivots.csv","39648f066b515c6ddc5b5853f9d1f691e3439fa04393a81e36b4c19e649262b1"),
"alerts":(ROOT/"v101_fresh_start/observations/fresh_formal_start_events.csv","5689519a88dce681c2032cae181386137e5f549481627441c8343dc2ac27ba53"),
"outcomes":(ROOT/"v101_fresh_start/observations/matched_or_pending_event_audit.csv","e180e3254e100d9ab352aa6ed74e7156c54f01350afad188fd5a00cc5ea578cc")
}
RULES={
"5_TOP":(63,20,Decimal(".90"),Decimal(".015"),10,10,"5","TOP"),
"5_BOTTOM":(63,20,Decimal(".10"),Decimal(".015"),10,10,"5","BOTTOM"),
"9_TOP":(126,60,Decimal(".95"),Decimal(".055"),20,20,"9","TOP"),
"9_BOTTOM":(126,60,Decimal(".05"),Decimal(".055"),20,20,"9","BOTTOM")
}
BUFFER=140

def rows_from_file(name):
    path,digest=FILES[name]
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=digest:
        raise ValueError("immutable source SHA mismatch: "+name)
    return list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))

def candidate(closes,dec,r):
    window,mom,limit,threshold,_,_,_,side=r
    end=dec-1
    if end<max(window-1,mom):return None
    look=closes[end-window+1:end+1]
    lo=min(look);hi=max(look)
    position=(closes[end]-lo)/(hi-lo) if hi>lo else Decimal(".5")
    growth=closes[end]/closes[end-mom]-1
    loc_ok=position>=limit if side=="TOP" else position<=limit
    mom_ok=growth>=threshold if side=="TOP" else growth<=-threshold
    return loc_ok,mom_ok,position,growth

def independent_alerts(dates,closes):
    out=[];state={}
    for task,r in RULES.items():
        previous=False;last=-100000;task_states={}
        for day in range(1,len(dates)):
            calc=candidate(closes,day,r)
            eligible=calc is not None and calc[0] and calc[1]
            edge=eligible and not previous
            signal=edge and day-last>r[4]
            task_states[day]={"computed":calc is not None,
                               "eligible":bool(eligible),"edge":bool(edge),"signal":bool(signal),
                               "position_ok":bool(calc and calc[0]),
                               "momentum_ok":bool(calc and calc[1])}
            if signal:
                out.append({"id":f"V101_{task}_{dates[day]}","date":dates[day],
                            "task":task,"asof":dates[day-1],"source_index":day-1,
                            "position":calc[2],"growth":calc[3]})
                last=day
            previous=bool(eligible)
        state[task]=task_states
    return sorted(out,key=lambda a:(a["date"],a["task"])),state

def independent_max_match(alerts,pivots,position,lead):
    """Dynamic programming with skip-alert/skip-pivot/match, not V101 greedy."""
    alarms=sorted(alerts,key=lambda x:(x["date"],x["id"]))
    goals=sorted(pivots,key=lambda x:(x["date"],x["id"]))
    @lru_cache(None)
    def dp(i,j):
        if i==len(alarms) or j==len(goals):return 0,()
        choices=[dp(i+1,j),dp(i,j+1)]
        lag=position[goals[j]["date"]]-position[alarms[i]["date"]]
        if 1<=lag<=lead:
            n,seq=dp(i+1,j+1)
            choices.append((1+n,((i,j),)+seq))
        maximum=max(x[0] for x in choices)
        return min((x for x in choices if x[0]==maximum),key=lambda x:x[1])
    _,pairs=dp(0,0)
    return {alarms[i]["id"]:goals[j] for i,j in pairs}

def build():
    prices=rows_from_file("prices");pivots=rows_from_file("pivots")
    alerts_old=rows_from_file("alerts");scores_old=rows_from_file("outcomes")
    dates=[x["date"] for x in prices];closes=[Decimal(x["close"]) for x in prices]
    if len(dates)!=1128 or dates!=sorted(set(dates)):
        raise ValueError("unexpected index calendar")
    predicted,state=independent_alerts(dates,closes)
    old={a["id"]:a for a in alerts_old};oldscore={a["id"]:a for a in scores_old}
    if len(predicted)!=len(old) or len(predicted)!=59:
        raise ValueError("independent formal alert count mismatch")
    position={d:i for i,d in enumerate(dates)}
    for a in predicted:
        src=old.get(a["id"])
        if not src or src["date"]!=a["date"] or src["task"]!=a["task"] or src["last_price_observation_date"]!=a["asof"]:
            raise ValueError("independent formal alert date/source mismatch")
        if Decimal(src["position_rolling_close"])!=a["position"] or Decimal(src["momentum_prior_close"])!=a["growth"]:
            raise ValueError("historical first-capture price feature mismatch")
        if int(src["last_price_observation_index"])!=a["source_index"]:
            raise ValueError("same-day price source leakage")
    outputs={};fp_rows=[];fn_rows=[];warmup_rows=[]
    for task,r in RULES.items():
        window,mom,_,_,_,lead,scale,direction=r
        aa=sorted((x for x in predicted if x["task"]==task),key=lambda x:x["date"])
        pp=sorted((x for x in pivots if x["scale"]==scale and x["direction"]==direction),key=lambda x:x["date"])
        left=[p for p in pp if p["first_segment_left_censored"].lower()=="true"]
        eligible=[p for p in pp if p not in left]
        mature=[p for p in eligible if position[p["confirmation_date"]]+BUFFER<len(dates)]
        pending=[p for p in eligible if p not in mature]
        matched=independent_max_match(aa,mature,position,lead)
        matched_ids={p["id"] for p in matched.values()}
        first_computable=max(window-1,mom)+1
        first_complete=first_computable+lead
        excluded=[p for p in mature if position[p["date"]]<first_complete]
        fully_observable=[p for p in mature if p not in excluded]
        if any(p["id"] in matched_ids for p in excluded):
            raise ValueError("source warmup pivot matched despite no eligible signal")
        counts={"TP":0,"FP":0,"PENDING":0,"EXCLUDED_LEFT_CENSORED":0}
        for a in aa:
            i=position[a["date"]];p=matched.get(a["id"])
            if p:status="TP"
            elif any(1<=position[x["date"]]-i<=lead for x in left):status="EXCLUDED_LEFT_CENSORED"
            elif any(1<=position[x["date"]]-i<=lead for x in pending):status="PENDING"
            elif i+lead+BUFFER<len(dates):status="FP"
            else:status="PENDING"
            counts[status]+=1
            frozen=oldscore[a["id"]]
            gap=str(position[p["date"]]-i) if p else ""
            if any((frozen["event_result"]!=status,
                    frozen["matched_pivot_id"]!=(p["id"] if p else ""),
                    frozen["lead_trading_sessions"]!=gap)):
                raise ValueError("independent event result mismatch: "+a["id"])
            if status=="FP":
                next_same=sorted(((position[q["date"]]-i,q) for q in eligible
                    if position[q["date"]]>i),key=lambda x:x[0])
                next_gap=next_same[0][0] if next_same else None
                if next_gap is None:kind="NO_LATER_SAME_DIRECTION_LABEL_IN_ARCHIVE"
                elif next_gap<=lead:kind="REVIEW_MATCH_COLLISION"
                elif next_gap<=2*lead:kind="EXTREME_ONE_TO_TWO_WINDOWS_AFTER_ALERT"
                elif next_gap<=3*lead:kind="EXTREME_TWO_TO_THREE_WINDOWS_AFTER_ALERT"
                else:kind="NO_EXTREME_WITHIN_THREE_WINDOWS"
                fp_rows.append({"alert_id":a["id"],"task":task,"alert_date":a["date"],
                       "asof_date":a["asof"],"year":a["date"][:4],
                       "expost_diagnostic":kind,"next_same_direction_pivot_gap_sessions":next_gap,
                       "type":"HINDSIGHT_DIAGNOSTIC_NOT_PREOPEN_FACTOR"})
        tp=counts["TP"];fp=counts["FP"];fn=len(mature)-tp
        for p in mature:
            if p["id"] in matched_ids:continue
            i=position[p["date"]]
            days=range(max(1,i-lead),i)
            states=[state[task].get(day) for day in days]
            complete=[s for s in states if s is not None and day_has_computable(s)]
            eligible_days=sum(s["eligible"] for s in complete)
            if p in excluded:kind="NO_SUFFICIENT_PRIOR_PRICE_HISTORY"
            elif any(s["signal"] for s in complete):kind="SIGNAL_IN_WINDOW_ASSIGNED_TO_OTHER_PIVOT"
            elif any(s["edge"] for s in complete):kind="EDGE_BLOCKED_BY_COOLDOWN"
            elif eligible_days:kind="ELIGIBLE_BUT_NO_FRESH_EDGE"
            else:kind="NEVER_SIMULTANEOUSLY_MET_BOTH_PRICE_CONDITIONS"
            fn_rows.append({"pivot_id":p["id"],"task":task,"pivot_date":p["date"],
                       "confirmation_date":p["confirmation_date"],
                       "expost_rule_diagnostic":kind,
                       "any_valid_rule_computation_days":len(complete),
                       "rule_eligible_days":eligible_days,
                       "first_fully_eligible_lead_date":dates[first_complete],
                       "type":"HINDSIGHT_DIAGNOSTIC_NOT_PREOPEN_FACTOR"})
        for p in excluded:
            warmup_rows.append({"task":task,"pivot_id":p["id"],"pivot_date":p["date"],
                                "extreme_index":position[p["date"]],"minimum_full_lead_index":first_complete,
                                "reason":"INSUFFICIENT_SOURCE_PREHISTORY_FOR_FULL_LEAD_WINDOW"})
        outputs[task]={
            "original_replayed":{"tp":tp,"fp":fp,"fn":fn,"pending":counts["PENDING"],
                                 "mature_pivots":len(mature)},
            "full_forecast_opportunity_sensitivity":{
                "excluded_insufficient_history":len(excluded),
                "eligible_mature_pivots":len(fully_observable),
                "tp":tp,"fp":fp,"fn":len(fully_observable)-tp,
                "precision":tp/(tp+fp) if tp+fp else None,
                "recall":tp/len(fully_observable) if fully_observable else None},
            "preopen_rule_first_computable_index":first_computable,
            "full_forecast_window_first_eligible_pivot_index":first_complete}
    if len(fp_rows)!=32 or len(fn_rows)!=28 or len(warmup_rows)!=5:
        raise ValueError("frozen event/source forensic reconciliation failed")
    return {
        "schema":"V102_INDEPENDENT_NO_TUNING_REAL_HISTORICAL_DIAGNOSTIC",
        "source_SHA256":{k:v[1] for k,v in FILES.items()},
        "independent_new_formal_starts_reproduced":len(predicted),
        "independent_event_outcomes_reproduced":len(oldscore),
        "original_four_task_metrics_preserved":True,
        "full_lead_window_eligible_metrics":outputs,
        "total_mature_FP":len(fp_rows),"total_original_mature_FN":len(fn_rows),
        "newly_identified_unforecastable_warmup_FN":len(warmup_rows),
        "not_forecastability_improvement_only_denominator_correction":True,
        "source_asof_PIT_verified":False,
        "blind_sample":False,"formal_signal_allowed":False,
        "production_updated":False
    },fp_rows,fn_rows,warmup_rows

def day_has_computable(s):
    return bool(s["computed"])

def save_once(path,content):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        if path.read_bytes()!=content:raise ValueError("first-capture audit changed "+str(path))
        return
    path.write_bytes(content)

def csv_output(rows):
    if not rows:return b""
    buffer=io.StringIO(newline="")
    writer=csv.DictWriter(buffer,fieldnames=list(rows[0]),lineterminator="\n")
    writer.writeheader();writer.writerows(rows)
    return buffer.getvalue().encode()

def main():
    report,fp,fn,warmup=build()
    out=ROOT/"v102_fresh_forensics/observations"
    save_once(out/"independent_replay_and_warmup_audit.json",
              (json.dumps(report,ensure_ascii=False,indent=2)+"\n").encode())
    save_once(out/"false_positives_descriptive.csv",csv_output(fp))
    save_once(out/"missed_mature_pivots.csv",csv_output(fn))
    save_once(out/"unforecastable_early_pivots.csv",csv_output(warmup))
    print(json.dumps({"status":"RESEARCH_AUDIT_PASS_NOT_PIT",
                      "new_signals":59,"FP":32,"FN_V101":28,
                      "warmup_unforecastable":len(warmup),
                      "formal_signal_allowed":False}))

if __name__=="__main__":main()
