#!/usr/bin/env python3
"""V113 third-party breadth candidate audit: no certified listings or survivorship claims."""
import argparse,csv,json,hashlib
from pathlib import Path

def validate(reference_dates, candidate_rows):
    expected=set(reference_dates)
    observed={}
    reasons=[]
    for row in candidate_rows:
        day=row["date"]
        if day in observed:raise ValueError("DUPLICATE_BREADTH_DAY")
        try:
            up=float(row["up"]);down=float(row["down"])
            if not (up>=0 and down>=0 and up+down>0 and up.is_integer() and down.is_integer()):
                raise ValueError("INVALID_UP_DOWN")
            observed[day]=dict(row)
        except (TypeError,ValueError,KeyError) as exc:
            reasons.append({"date":day,"reason":str(exc)[:100]})
    valid=set(observed)&expected
    n=len(expected)
    if n==0:raise ValueError("EMPTY_REFERENCE_DATES")
    coverage=len(valid)/n
    return {"version":"V113","status":"PARTIAL" if valid else "BLOCKED",
       "research_candidate_98pct_coverage_reached":len(valid)*100>=n*98,
       "observed_reference_days":len(valid),"reference_days":n,
       "coverage_fraction":round(coverage,8),"missing_reference_days":sorted(expected-valid),
       "invalid_records":reasons,
       "listed_security_universe_verified":False,
       "new_high_new_low_from_raw_security_bars":False,
       "suspended_and_flat_distinguished":False,
       "survivorship_bias_excluded":False,
       "full_v113_pass":False,
       "formal_signal_allowed":False,
       "warning":"Third-party aggregate advancers/decliners only; not a rebuilt audited historical full-market universe."}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--daily",required=True);p.add_argument("--breadth",required=True);p.add_argument("--out",required=True)
    a=p.parse_args()
    with open(a.daily,newline="",encoding="utf-8") as f: ref=[x["source_trade_date"] for x in csv.DictReader(f)]
    file=Path(a.breadth)
    rows=list(csv.DictReader(file.open(newline="",encoding="utf-8"))) if file.is_file() else []
    result=validate(ref,rows)
    result["candidate_source_sha256"]=hashlib.sha256(file.read_bytes()).hexdigest() if file.is_file() else None
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:v for k,v in result.items() if k not in ("missing_reference_days","invalid_records")},ensure_ascii=False))
if __name__=="__main__":main()
