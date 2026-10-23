#!/usr/bin/env python3
"""V113 fully-audited BaoStock *Shanghai/Shenzhen* stock-bar shard.

Historical source snapshots are research-only. Missing traded/suspended rows are
not forward-filled, and Beijing securities are explicitly outside BaoStock scope.
"""
import argparse,csv,gzip,hashlib,json,sys,time
from collections import Counter
from datetime import date
from decimal import Decimal,InvalidOperation
from pathlib import Path

FIELDS="date,code,open,high,low,close,preclose,volume,amount,tradestatus,isST"
COLUMNS=FIELDS.split(",")
def basic_list(path):
    with open(path,newline="",encoding="utf-8-sig") as f:rows=list(csv.DictReader(f))
    stocks={}
    for r in rows:
        if r.get("type")!="1" or not r["code"].startswith(("sh.","sz.")):continue
        if r["code"] in stocks:raise ValueError("DUPLICATE_BASIC_CODE")
        for col in ("ipoDate","outDate"):
            if r.get(col):date.fromisoformat(r[col])
        stocks[r["code"]]=r
    return stocks
def validate_one(code,rows,anchor):
    dates=set()
    counts=Counter()
    for r in rows:
        if r.get("code")!=code:raise ValueError("WRONG_SECURITY_CODE")
        d=r.get("date","")
        date.fromisoformat(d)
        if d in dates:raise ValueError("DUPLICATE_STOCK_DATE")
        dates.add(d)
        status=r.get("tradestatus")
        if status=="0":
            counts["suspended"]+=1
            continue
        if status!="1":raise ValueError("UNKNOWN_TRADESTATUS")
        try:
            close=Decimal(r["close"]);prev=Decimal(r["preclose"])
            volume=Decimal(r["volume"]);amount=Decimal(r["amount"])
            if not all(x.is_finite() for x in (close,prev,volume,amount)):raise ValueError("NONFINITE")
            if not (close>0 and prev>0 and volume>=0 and amount>=0):raise ValueError("INVALID_TRADING_VALUES")
        except (InvalidOperation,TypeError,KeyError) as e:raise ValueError("INVALID_PRICE_FIELDS") from e
        if close>prev:counts["up"]+=1
        elif close<prev:counts["down"]+=1
        else:counts["flat"]+=1
    if rows and rows[0]["date"]>rows[-1]["date"]:raise ValueError("UNSORTED_DATES")
    return counts,dates

def run(args):
    import baostock as bs
    stocks=basic_list(args.stock_basic)
    codes=sorted(stocks)
    selected=[c for i,c in enumerate(codes) if i%args.shards==args.shard]
    if args.limit is not None:selected=selected[:args.limit]
    if not selected:raise ValueError("EMPTY_SHARD")
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    anchor_dates=[]
    with open(args.anchor,newline="",encoding="utf-8") as f:
        anchor_dates=[r["source_trade_date"] for r in csv.DictReader(f)]
    if anchor_dates!=sorted(set(anchor_dates)):raise ValueError("BAD_ANCHOR")
    if len(anchor_dates)!=1129:raise ValueError("ANCHOR_DENOMINATOR_CHANGED")
    manifest=[];all_counts=Counter()
    raw_path=out/("stock_bars_shard_%02d.csv.gz"%args.shard)
    lg=bs.login()
    if lg.error_code!="0":raise RuntimeError("BAOSTOCK_LOGIN_FAILED_"+lg.error_msg)
    try:
        with gzip.open(raw_path,"wt",newline="",encoding="utf-8") as gz:
            writer=csv.DictWriter(gz,fieldnames=COLUMNS)
            writer.writeheader()
            for idx,code in enumerate(selected):
                basic=stocks[code]
                row={"code":code,"index":idx,"status":"FAILED","ipoDate":basic.get("ipoDate",""),
                     "outDate":basic.get("outDate",""),"shard":args.shard}
                for attempt in range(2):
                    try:
                        r=bs.query_history_k_data_plus(code,FIELDS,start_date="2022-02-23",
                            end_date="2026-10-21",frequency="d",adjustflag="3")
                        if r.error_code!="0":raise RuntimeError("PROVIDER_ERROR_"+r.error_code+"_"+r.error_msg[:90])
                        if r.fields!=COLUMNS:raise ValueError("PROVIDER_SCHEMA_CHANGED")
                        rows=[]
                        while r.next():rows.append(dict(zip(r.fields,r.get_row_data())))
                        counts,dates=validate_one(code,rows,anchor_dates)
                        active_days=[d for d in anchor_dates if (not basic.get("ipoDate") or d>=basic["ipoDate"])
                           and (not basic.get("outDate") or d<=basic["outDate"])]
                        observed_dates=dates.intersection(active_days)
                        # Any missing listed stock/date remains a real gap; never auto-label as suspended.
                        missing_days=len(active_days)-len(observed_dates)
                        for item in rows:writer.writerow(item)
                        row.update(status="VALIDATED_RESEARCH",raw_rows=len(rows),
                                   active_calendar_days=len(active_days),
                                   observed_listed_days=len(observed_dates),missing_listed_days=missing_days,
                                   trade_status_counts=dict(counts),first_date=rows[0]["date"] if rows else "",
                                   last_date=rows[-1]["date"] if rows else "",
                                   stock_rows_sha256=hashlib.sha256(("\n".join(",".join(x.get(col,"") for col in COLUMNS) for x in rows)).encode()).hexdigest())
                        for k,v in counts.items():all_counts[k]+=v
                        break
                    except Exception as exc:
                        row["error"]=type(exc).__name__+":"+str(exc)[:170]
                        if attempt==0:time.sleep(2)
                manifest.append(row)
                if idx%15==0 or idx==len(selected)-1:
                    print(json.dumps({"shard":args.shard,"completed":idx+1,
                       "total":len(selected),"failed":sum(x["status"]!="VALIDATED_RESEARCH" for x in manifest),
                       "date_gaps":sum(x.get("missing_listed_days",0) for x in manifest)},ensure_ascii=False),flush=True)
                time.sleep(args.delay)
    finally:
        bs.logout()
    report={"version":"V113","source":"BaoStock","scope":"SH_SZ_ONLY_EXCLUDES_BEIJING",
        "shard":args.shard,"shards":args.shards,"requested_stock_count":len(selected),
        "completed_stock_count":sum(x["status"]=="VALIDATED_RESEARCH" for x in manifest),
        "failed_stock_count":sum(x["status"]!="VALIDATED_RESEARCH" for x in manifest),
        "missing_listed_stock_days":sum(x.get("missing_listed_days",0) for x in manifest),
        "bar_counts":dict(all_counts),"raw_archive_sha256":hashlib.sha256(raw_path.read_bytes()).hexdigest(),
        "rows":manifest,"formal_signal_allowed":False,
        "historical_release_pit_certified":False}
    (out/("manifest_%02d.json"%args.shard)).write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="rows"},ensure_ascii=False),flush=True)
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--anchor",required=True);p.add_argument("--stock-basic",required=True)
    p.add_argument("--out",required=True);p.add_argument("--shard",type=int,required=True)
    p.add_argument("--shards",type=int,required=True);p.add_argument("--limit",type=int)
    p.add_argument("--delay",type=float,default=.15);a=p.parse_args()
    if a.shards<1 or a.shards>64 or not(0<=a.shard<a.shards):raise SystemExit("BAD_SHARD")
    if a.limit is not None and not(1<=a.limit<=500):raise SystemExit("BAD_LIMIT")
    run(a)
if __name__=="__main__":main()
