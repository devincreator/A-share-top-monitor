#!/usr/bin/env python3
"""V105 hindsight diagnosis + V106/V107 causal, research-only regime features."""
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FP = ROOT / "research/v102_fresh_forensics/observations/false_positives_descriptive.csv"
FN = ROOT / "research/v102_fresh_forensics/observations/missed_mature_pivots.csv"
EVENTS = ROOT / "research/v101_fresh_start/observations/fresh_formal_start_events.csv"
PRICES = ROOT / "research/v97_event_intake/observations/index_000985_prices_20220223_20261020.csv"
OUTPUT = Path(__file__).with_name("observations")
FROZEN_SHA = "f18bb93b38e6648fbd72bad53dc7fa06333cd63a01858063e1dfa50b14e7fc41"

def read(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def diagnose(fp, fn, events):
    ids = [r["id"] for r in events]
    if len(ids) != len(set(ids)):
        raise ValueError("DUPLICATE_ALERT_ID")
    mapped = set(ids)
    if any(r["alert_id"] not in mapped for r in fp):
        raise ValueError("FP_NOT_IN_FROZEN_ALERTS")
    if any(r.get("type") != "HINDSIGHT_DIAGNOSTIC_NOT_PREOPEN_FACTOR" for r in fp + fn):
        raise ValueError("HINDSIGHT_BOUNDARY_VIOLATION")
    fp_count = Counter((r["task"], r["expost_diagnostic"]) for r in fp)
    fn_count = Counter((r["task"], r["expost_rule_diagnostic"]) for r in fn)
    return {
      "classification": "EXPOST_ONLY_NEVER_A_PREDICTOR",
      "frozen_alert_count": len(events), "diagnosed_fp_count": len(fp),
      "diagnosed_fn_count": len(fn),
      "fp_by_task_and_cause": [{"task":t,"cause":c,"count":n} for (t,c),n in sorted(fp_count.items())],
      "fn_by_task_and_cause": [{"task":t,"cause":c,"count":n} for (t,c),n in sorted(fn_count.items())],
      "fp_next_pivot_gap_is_hindsight": True,
      "source_files": {"events":str(EVENTS.relative_to(ROOT)),
                       "fp":str(FP.relative_to(ROOT)), "fn":str(FN.relative_to(ROOT))}}
 
def trailing_features(closes, lookback=63):
    """Only values at/before asof; no labels and no future observations."""
    if len(closes) < lookback + 1:
        return None
    a = closes[-1]
    window = closes[-lookback:]
    hi,lo = max(window),min(window)
    ret5 = a/closes[-6]-1
    ret20 = a/closes[-21]-1
    ret63 = a/closes[-64]-1
    pos = 0.5 if hi == lo else (a-lo)/(hi-lo)
    # Descriptive states, not fitted forecasts, thresholds fixed a priori.
    if pos >= .8 and ret20 > 0 and ret5 > 0: state="UPTREND"
    elif pos <= .2 and ret20 < 0 and ret5 < 0: state="DOWNTREND"
    elif ret20 < 0 and ret5 > 0: state="BOUNCE_IN_WEAK_TREND"
    elif ret20 > 0 and ret5 < 0: state="PULLBACK_IN_STRONG_TREND"
    else: state="MIXED"
    return {"position_63":round(pos,8),"ret5":round(ret5,8),
            "ret20":round(ret20,8),"ret63":round(ret63,8),"state":state}

def parse_price_table(rows):
    """Discover known archive column names, fail closed rather than invent."""
    if not rows: raise ValueError("EMPTY_PRICE_ARCHIVE")
    cols=set(rows[0])
    date=next((c for c in ("date","trade_date","tradeDate") if c in cols),None)
    close=next((c for c in ("close","close_price","closePrice") if c in cols),None)
    if not date or not close: raise ValueError("UNKNOWN_PRICE_SCHEMA:"+",".join(sorted(cols)))
    found=[]
    for r in rows:
        found.append((r[date], float(r[close])))
    if len({d for d,_ in found})!=len(found): raise ValueError("DUPLICATE_PRICE_DATE")
    if any(p<=0 for _,p in found): raise ValueError("NONPOSITIVE_CLOSE")
    if found != sorted(found): raise ValueError("UNSORTED_PRICE_DATES")
    return found

def states_asof(prices):
    results=[]
    for i in range(len(prices)):
        features=trailing_features([x[1] for x in prices[:i+1]])
        if features:
            # This is an after-close feature date; D+1 may use it,
            # only if the D close was available by D+1 decision time.
            results.append({"asof_close_date":prices[i][0],**features})
    return results


def event_state_crosswalk(events, states):
    """Join by the event's archived D-1 source date, never by later pivot outcome."""
    by_date = {r["asof_close_date"]: r for r in states}
    output=[]
    for event in events:
        d=event["last_price_observation_date"]
        row=by_date.get(d)
        if row is None:
            raise ValueError("MISSING_ASOF_STATE:"+d)
        if d >= event["date"]:
            raise ValueError("SAME_DAY_OR_FUTURE_STATE_FOR_PREOPEN")
        output.append({"alert_id":event["id"],"task":event["task"],
            "decision_date":event["date"],"asof_close_date":d,
            "historical_source_time_certified":False,
            "retrospective_state_only":True,"state":row["state"],
            "ret5":row["ret5"],"ret20":row["ret20"],"ret63":row["ret63"],
            "position_63":row["position_63"]})
    if len({r["alert_id"] for r in output}) != len(output):
        raise ValueError("DUPLICATE_CROSSWALK_IDS")
    return output

def hindsight_error_by_state(crosswalk, false_positives):
    """Diagnostic contingency only; ex-post FP membership never input to model."""
    fp_ids={r["alert_id"] for r in false_positives}
    known={r["alert_id"] for r in crosswalk}
    if not fp_ids.issubset(known):
        raise ValueError("ORPHAN_FALSE_POSITIVE")
    totals=Counter((r["task"],r["state"]) for r in crosswalk)
    fps=Counter((r["task"],r["state"]) for r in crosswalk if r["alert_id"] in fp_ids)
    # Other alerts include TP and PENDING: never call the complement TP.
    return [{"task":t,"state":state,"alerts":n,
             "retrospective_fp":fps[(t,state)],
             "not_identified_as_fp_in_this_file":n-fps[(t,state)],
             "non_fp_may_include_pending":True}
            for (t,state),n in sorted(totals.items())]

def main():
    for p in (FP,FN,EVENTS,PRICES):
        if not p.is_file(): raise FileNotFoundError(p)
    if sha(PRICES) != FROZEN_SHA: raise ValueError("PRICE_ARCHIVE_SHA_MISMATCH")
    diagnostic=diagnose(read(FP),read(FN),read(EVENTS))
    prices=parse_price_table(read(PRICES))
    states=states_asof(prices)
    crosswalk=event_state_crosswalk(read(EVENTS),states)
    if not states: raise ValueError("NO_ELIGIBLE_STATE_ROWS")
    OUTPUT.mkdir(exist_ok=True)
    (OUTPUT/"diagnosis.json").write_text(json.dumps(diagnostic,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    with (OUTPUT/"causal_states.csv").open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(states[0]))
        writer.writeheader();writer.writerows(states)
    with (OUTPUT/"event_state_crosswalk.csv").open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(crosswalk[0]))
        writer.writeheader();writer.writerows(crosswalk)
    aligned=sum(1 for r in crosswalk if (r["task"].endswith("TOP") and r["state"]=="UPTREND") or
                (r["task"].endswith("BOTTOM") and r["state"]=="DOWNTREND"))
    error_by_state=hindsight_error_by_state(crosswalk,read(FP))
    (OUTPUT/"hindsight_error_by_state.json").write_text(
        json.dumps({"classification":"EXPOST_CONTINGENCY_NOT_MODEL_PERFORMANCE",
                    "cells":error_by_state},ensure_ascii=False,indent=2)+"\\n",encoding="utf-8")
    summary={"crosswalk_events":len(crosswalk),"crosswalk_state_counts":dict(Counter(r["state"] for r in crosswalk)),
        "alert_direction_state_overlap_count":aligned,
        "alert_direction_state_overlap_fraction":round(aligned/len(crosswalk),6),
        "overlap_warning":"STATE_REUSES_PRICE_AND_IS_NOT_AN_INDEPENDENT_FEATURE",
        "historical_event_state_join_is_expost":True,"status":"RETROSPECTIVE_DESCRIPTIVE_ONLY_NOT_PIT_NOT_MODEL_VALIDATION",
        "price_sha256":sha(PRICES),"feature_rows":len(states),
        "first_asof":states[0]["asof_close_date"],"last_asof":states[-1]["asof_close_date"],
        "state_counts":dict(Counter(r["state"] for r in states)),
        "v107_limit":"NO_CERTIFIED_BREADTH_TURNOVER_FINANCING_INPUTS_USED",
        "future_labels_in_features":False,"production_updated":False,"formal_signal_allowed":False}
    (OUTPUT/"state_summary.json").write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False))
if __name__=="__main__":main()
