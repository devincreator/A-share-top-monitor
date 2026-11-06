#!/usr/bin/env python3
"""V113 derive independent observed traded breadth from free daily original stock bars."""
import argparse,csv,hashlib,json,math,re
from pathlib import Path
from decimal import Decimal,InvalidOperation
CODE=re.compile(r"^\d{6}\.(SH|SZ|BJ)$")
REQUIRED={"symbol","trade_date","close","pre_close","amount","vol"}
def calculate(path,expected_date):
    raw=Path(path).read_bytes()
    table=list(csv.DictReader(raw.decode("utf-8-sig").splitlines()))
    if not table or not REQUIRED.issubset(table[0]):raise ValueError("SOURCE_SCHEMA")
    seen=set();counts={"up":0,"down":0,"flat":0,"invalid":0,"non_a":0}
    for r in table:
        code=r["symbol"];d=r["trade_date"]
        if not CODE.fullmatch(code):
            counts["non_a"]+=1
            continue
        if d!=expected_date.replace("-",""):raise ValueError("WRONG_TRADE_DATE")
        if code in seen:raise ValueError("DUPLICATE_SECURITY")
        seen.add(code)
        try:
            close=Decimal(r["close"]);prev=Decimal(r["pre_close"])
            turnover=Decimal(r["amount"]);vol=Decimal(r["vol"])
            if not all(x.is_finite() for x in (close,prev,turnover,vol)) or close<=0 or prev<=0 or turnover<0 or vol<0:
                raise ValueError("BAD_VALUES")
            if close>prev:counts["up"]+=1
            elif close<prev:counts["down"]+=1
            else:counts["flat"]+=1
        except (ValueError,TypeError,InvalidOperation,KeyError):
            counts["invalid"]+=1
    eligible=counts["up"]+counts["down"]+counts["flat"]
    if eligible<500 or eligible>8000:raise ValueError("IMPLAUSIBLE_SECURITY_COUNT")
    return {"date":expected_date,**counts,"eligible_traded":eligible,
      "total_source_rows":len(table),"raw_sha256":hashlib.sha256(raw).hexdigest(),
      "scope":"TRADED_BARS_ONLY_NO_CERTIFIED_SUSPENSION_UNIVERSE",
      "reconstructed":True,"historical_publication_certified":False,
      "formal_signal_allowed":False}
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--raw-dir",required=True);ap.add_argument("--out",required=True);args=ap.parse_args()
    results=[]
    for p in sorted(Path(args.raw_dir).glob("daily_*.csv")):
        d=p.stem.split("_",1)[1];dt=d[:4]+"-"+d[4:6]+"-"+d[6:]
        results.append(calculate(p,dt))
    if not results:raise ValueError("NO_OBSERVED_BARS")
    out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
    with out.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(results[0]));w.writeheader();w.writerows(results)
    print(json.dumps(results,ensure_ascii=False))
if __name__=="__main__":main()
