#!/usr/bin/env python3
"""V114 assumed-lag as-of master, explicit validity, no ex-post labels."""
import argparse,csv,json,hashlib
from pathlib import Path
from datetime import date
def readcsv(path):
    with Path(path).open(newline="",encoding="utf-8") as f:return list(csv.DictReader(f))
def build(daily,breadth=None):
    days=[r["source_trade_date"] for r in daily]
    if days!=sorted(set(days)):raise ValueError("NON_UNIQUE_PRICE_CALENDAR")
    breadth=breadth or []
    bmap={}
    for r in breadth:
        d=r["date"]
        if d in bmap:raise ValueError("DUPLICATE_BREADTH_DAY")
        bmap[d]=r
    rows=[]
    for i in range(1,len(days)):
        decision=days[i]
        prior=days[i-1]
        # Two *trading sessions* ago; current day never appears in candidate data.
        finance=days[i-2] if i>=2 else ""
        weekly=next((days[j] for j in range(i-1,-1,-1)
                     if date.fromisoformat(days[j]).isocalendar()[:2] <
                        date.fromisoformat(decision).isocalendar()[:2]),"")
        monthly=next((days[j] for j in range(i-1,-1,-1)
                      if days[j][:7]<decision[:7]),"")
        source=daily[i-1]
        fr=daily[i-2] if i>=2 else None
        bd=bmap.get(prior)
        row={"decision_date":decision,"price_asof":prior,"finance_asof":finance,
             "week_last_closed_day":weekly,"month_last_closed_day":monthly}
        for code in ("000985","000300","000852"):
            for col in ("close","amount","turnover"):
                row[code+"_"+col]=source.get(code+"_"+col,"")
        row["breadth_up"]=bd["up"] if bd else ""
        row["breadth_down"]=bd["down"] if bd else ""
        row["breadth_flat"]=bd.get("flat","") if bd else ""
        row["breadth_valid"]=bool(bd)
        row["finance_status_at_asof"]=fr.get("financing_status") if fr else "UNAVAILABLE"
        row["finance_total_exact_yuan"]=fr.get("balance_total_yuan","") if fr and fr["financing_status"]=="OK" else ""
        row["formal_signal_allowed"]=False
        if not(prior<decision and (not finance or finance<prior) and
               (not weekly or weekly<decision) and (not monthly or monthly<decision)):
            raise ValueError("ASOF_LEAKAGE")
        rows.append(row)
    return rows,{"version":"V114","status":"RESEARCH_FEATURES_ONLY_NOT_ACCEPTED",
       "target_decisions":len(rows),"breadth_present":sum(x["breadth_valid"] for x in rows),
       "price_asof_violations":0,"finance_delay_violations":0,
       "weekly_monthly_future_use_violations":0,"production_updated":False,
       "formal_signal_allowed":False,
       "note":"V112 rounded-financing candidates excluded from exact amounts; breadth partial."}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--daily",required=True);p.add_argument("--breadth")
    p.add_argument("--out",required=True)
    a=p.parse_args()
    rows,report=build(readcsv(a.daily),readcsv(a.breadth) if a.breadth and Path(a.breadth).is_file() else [])
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    with (out/"asof_master.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    report["asof_sha256"]=hashlib.sha256((out/"asof_master.csv").read_bytes()).hexdigest()
    (out/"acceptance.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(report,ensure_ascii=False))
if __name__=="__main__":main()
