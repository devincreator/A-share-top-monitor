#!/usr/bin/env python3
"""V111: strict assumed-release-lag dataset from existing V89 captured sources.
No interpolation, imputation, inferred provider publication clock, or trading signals.
"""
import argparse,csv,json,hashlib,math
from pathlib import Path
from datetime import date
from collections import Counter

REQUIRED=("000985","000300","000852")
def load(path):
    obj=json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(obj,dict) or not isinstance(obj.get("indices"),dict):
        raise ValueError("INVALID_CANDIDATE_SOURCE")
    return obj
def build(obj):
    byindex={}
    for code in REQUIRED:
        rows=obj["indices"].get(code,[])
        valid={}
        for r in rows:
            if str(r.get("code"))!=code:raise ValueError("CODE_MISMATCH_"+code)
            d=date.fromisoformat(str(r["date"]))
            x={k:float(r[k]) for k in ("close","amount","turnover")}
            if not all(math.isfinite(v) for v in x.values()) or x["close"]<=0 or x["amount"]<0 or x["turnover"]<0:raise ValueError("INVALID_INDEX_VALUE")
            if d.isoformat() in valid:raise ValueError("DUPLICATE_INDEX_DATE")
            valid[d.isoformat()]=x
        byindex[code]=valid
    raw_fin={}
    invalid=Counter()
    for r in obj.get("financing",[]):
        d=date.fromisoformat(str(r["date"])).isoformat()
        if d in raw_fin:raise ValueError("DUPLICATE_FINANCE_DATE")
        try:
            sh=float(r["balance_sh_yuan"]);sz=float(r["balance_sz_yuan"])
            if not (math.isfinite(sh) and math.isfinite(sz) and sh>0 and sz>0):raise ValueError("NONPOSITIVE_FINANCING")
            raw_fin[d]=(sh,sz)
        except (TypeError,KeyError,ValueError,OverflowError):
            invalid[d]+=1
    # Price canonical calendar is 000985 observed dates; not certified national calendar.
    days=sorted(byindex["000985"])
    if not days:raise ValueError("NO_ANCHOR_DATES")
    features=[]
    for i,d in enumerate(days):
        # D is the last *source* trade date, not the prediction decision date.
        row={"source_trade_date":d}
        for code in REQUIRED:
            data=byindex[code].get(d)
            for name in ("close","amount","turnover"):
                row[code+"_"+name]=data[name] if data else ""
        fin=raw_fin.get(d)
        row["balance_sh_yuan"]=fin[0] if fin else ""
        row["balance_sz_yuan"]=fin[1] if fin else ""
        row["balance_total_yuan"]=sum(fin) if fin else ""
        row["financing_status"]="OK" if fin else ("INVALID" if d in invalid else "MISSING")
        # Guaranteed lag in *anchor trading sessions*, not calendar days.
        row["decision_date_for_price_assuming_D_minus_1"]=days[i+1] if i+1<len(days) else ""
        row["decision_date_for_financing_assuming_D_minus_2"]=days[i+2] if i+2<len(days) else ""
        features.append(row)
    return features,{"anchor":"000985 observed dates (not certified trading calendar)",
        "row_count":len(features),"first_date":days[0],"last_date":days[-1],
        "index_observations_by_code":{c:len(byindex[c]) for c in REQUIRED},
        "index_matched_anchor_by_code":{c:sum(d in byindex[c] for d in days) for c in REQUIRED},
        "financing_ok_anchor":sum(r["financing_status"]=="OK" for r in features),
        "financing_missing_anchor":sum(r["financing_status"]=="MISSING" for r in features),
        "financing_invalid_anchor":sum(r["financing_status"]=="INVALID" for r in features),
        "financing_invalid_dates":sorted(invalid),
        "lag_assumptions":{"daily_price_trading_sessions":1,"margin_trading_sessions":2,
            "financial_report":"actual_disclosure_date_plus_1_trading_session",
            "weekly":"next_week_first_trading_session_after_full_week",
            "monthly":"next_month_first_trading_session_after_full_month"},
        "source_status":"RESEARCH_ASSUMED_RELEASE_LAG_NOT_ACTUAL_PIT",
        "imputation_used":False,"production_updated":False,"formal_signal_allowed":False}
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input",required=True)
    ap.add_argument("--out",required=True)
    a=ap.parse_args()
    source=Path(a.input)
    rows,report=build(load(source))
    dest=Path(a.out);dest.mkdir(parents=True,exist_ok=True)
    out=dest/"daily_unified.csv"
    with out.open("w",newline="",encoding="utf8") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    report["source_file_sha256"]=hashlib.sha256(source.read_bytes()).hexdigest()
    report["daily_unified_sha256"]=hashlib.sha256(out.read_bytes()).hexdigest()
    (dest/"data_coverage.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print(json.dumps(report,ensure_ascii=False))
if __name__=="__main__":main()
