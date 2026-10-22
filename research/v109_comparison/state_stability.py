#!/usr/bin/env python3
"""V109 descriptive year-by-year state stability, NOT predictive backtesting."""
import argparse
from collections import Counter,defaultdict
import csv
import json
from pathlib import Path
STATES={"UPTREND","DOWNTREND","BOUNCE_IN_WEAK_TREND","PULLBACK_IN_STRONG_TREND","MIXED"}

def analyze(rows):
    previous_date=None
    annual=defaultdict(Counter)
    transitions=Counter()
    previous_state=None
    for row in rows:
        d=row["asof_close_date"]
        state=row["state"]
        if previous_date is not None and d<=previous_date:
            raise ValueError("NON_INCREASING_DATES")
        if state not in STATES:raise ValueError("UNKNOWN_STATE")
        year=d[:4]
        annual[year][state]+=1
        if previous_state is not None:transitions[(previous_state,state)]+=1
        previous_date,previous_state=d,state
    if not annual:raise ValueError("EMPTY_STATE_HISTORY")
    return {
      "status":"DESCRIPTIVE_STATE_STABILITY_ONLY_NO_ALPHA_CLAIM",
      "sample_rows":sum(sum(x.values()) for x in annual.values()),
      "annual_frequency":[{"year":y,"n":sum(c.values()),**{
          s:round(c[s]/sum(c.values()),6) for s in sorted(STATES)}}
          for y,c in sorted(annual.items())],
      "transition_counts":[{"from":a,"to":b,"count":n}
          for (a,b),n in sorted(transitions.items())],
      "outcome_labels_used":False,
      "prospective_predictions_scored":False,
      "source_pit_certified":False,
      "double80_certified":False,
      "production_updated":False}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",default="research/v105_v107/observations/causal_states.csv")
    p.add_argument("--output",default="research/v109_comparison/observations/state_stability.json")
    args=p.parse_args()
    with open(args.input,newline="",encoding="utf-8") as f:
        output=analyze(csv.DictReader(f))
    dst=Path(args.output)
    dst.parent.mkdir(parents=True,exist_ok=True)
    dst.write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":output["status"],"years":len(output["annual_frequency"]),
                      "rows":output["sample_rows"]}))
if __name__=="__main__":main()
