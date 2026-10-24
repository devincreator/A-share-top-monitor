#!/usr/bin/env python3
"""V113 TDX official multi-exchange historical .day archive extraction, strict retrospective research."""
import argparse,csv,hashlib,io,json,math,os,struct,time,urllib.request,zipfile
from collections import Counter,defaultdict,deque
from datetime import date
from pathlib import Path

URL="https://data.tdx.com.cn/vipdoc/hsjday.zip"
PACK=struct.Struct("<IIIIIfII")
FROZEN_BEGIN="2022-02-23";FROZEN_END="2026-10-21"

def catalog_basic(path):
    stocks={}
    with open(path,newline="",encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r.get("type")!="1" or not r["code"].startswith(("sh.","sz.")):continue
            if r["code"] in stocks:raise ValueError("DUPLICATE_BASE_CODE")
            stocks[r["code"]]={"listed":r.get("ipoDate",""),"out":r.get("outDate",""),
                               "canonical":r["code"],"market":r["code"].split(".")[0]}
    return stocks
def catalog_beijing(path,stocks):
    with open(path,newline="",encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            code="bj."+r["code"]
            if code in stocks:raise ValueError("DUPLICATE_BSE_CODE")
            stocks[code]={"listed":r["listed"],"out":r["delisted"],
                          "canonical":code,"market":"bj"}
    return stocks
def download(out):
    for i in range(4):
        start=out.stat().st_size if out.exists() else 0
        hdr={"User-Agent":"Mozilla/5.0 (noncommercial historical research)"}
        if start:hdr["Range"]="bytes=%d-"%start
        try:
            with urllib.request.urlopen(urllib.request.Request(URL,headers=hdr),timeout=95) as res:
                mode="ab" if res.status==206 and start else "wb"
                if res.status not in (200,206):raise RuntimeError("HTTP_"+str(res.status))
                with open(out,mode) as f:
                    while True:
                        chunk=res.read(4*1024*1024)
                        if not chunk:break
                        f.write(chunk)
                        if f.tell()>700_000_000:raise RuntimeError("UNEXPECTED_DOWNLOAD_SIZE")
            if zipfile.is_zipfile(out):return hashlib.sha256(out.read_bytes()).hexdigest()
            raise ValueError("INCOMPLETE_ZIP")
        except Exception as e:
            print(json.dumps({"source_retry":i+1,"partial_bytes":out.stat().st_size if out.exists() else 0,
                              "error":str(e)[:130]}),flush=True)
            if i==3:raise
            time.sleep(5*(i+1))
    raise RuntimeError("UNREACHABLE")
def parse_code(info):
    base=info.filename.replace("\\","/").split("/")[-1].lower()
    if len(base)==12 and base.endswith(".day") and base[:2] in ("sh","sz","bj") and base[2:8].isdigit():
        return base[:2]+"."+base[2:8]
    return None
def stats_per_stock(raw,anchor,canonical,meta,rec_info):
    if len(raw)%32:raise ValueError("BAD_DAY_MULTIPLE_"+canonical)
    seen=set();filtered=bytearray();bars=[];last_dt=0;prior_close=None
    for pos in range(0,len(raw),32):
        ymd,o,h,l,c,amt,vol,_=PACK.unpack_from(raw,pos)
        if ymd<=last_dt:raise ValueError("UNORDERED_OR_DUPLICATE_DATE_"+canonical)
        last_dt=ymd
        if not 19000101<=ymd<=20271031:raise ValueError("DATE_INVALID_"+canonical)
        d="%04d-%02d-%02d"%(ymd//10000,(ymd//100)%100,ymd%100)
        if d>FROZEN_END:break
        # Keep previous unadjusted close for directional proxy; no subsequent rows are consulted.
        current_close=c/100
        direction=None if prior_close is None else (1 if current_close>prior_close else -1 if current_close<prior_close else 0)
        prior_close=current_close
        if d<FROZEN_BEGIN or d not in anchor:continue
        if meta["listed"] and d<meta["listed"]:continue
        if meta["out"] and d>meta["out"]:continue
        if min(o,h,l,c)<=0 or l>h or not math.isfinite(amt) or amt<0:
            raise ValueError("BAD_PRICE_BAR_"+canonical+"_"+d)
        if d in seen:raise ValueError("DUPLICATE_BAR_DATE_"+canonical)
        seen.add(d)
        filtered+=raw[pos:pos+32]
        bars.append((d,current_close,h/100,l/100,amt,vol,direction))
    return filtered,bars
def main():
    p=argparse.ArgumentParser()
    for key in ("anchor","stock-basic","beijing-registry","out"):p.add_argument("--"+key,required=True)
    a=p.parse_args()
    root=Path(a.out);root.mkdir(parents=True,exist_ok=True)
    raw=root/"download_hsjday.zip"
    print(json.dumps({"stage":"start_download","source":URL}),flush=True)
    source_sha=download(raw)
    stocks=catalog_beijing(a.beijing_registry,catalog_basic(a.stock_basic))
    with open(a.anchor,newline="",encoding="utf-8") as f:
        dates=[r["source_trade_date"] for r in csv.DictReader(f)]
    if dates!=sorted(set(dates)) or len(dates)!=1129:raise ValueError("FROZEN_CALENDAR_CHANGED")
    anchor=set(dates)
    byday=defaultdict(Counter)
    registry_seen=defaultdict(set)
    reported=[];issues=[];members_seen=set()
    aliases={}
    with open(a.beijing_registry,newline="",encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("old_code") and r["old_code"]!=r["code"]:
                aliases["bj."+r["old_code"]]="bj."+r["code"]
    binary=root/"tdx_2022_2026_original_day_records.zip"
    skipped=Counter()
    with zipfile.ZipFile(raw) as src,zipfile.ZipFile(binary,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as dest:
        names=src.infolist()
        for ix,entry in enumerate(names):
            code=parse_code(entry)
            if not code:
                skipped["not_day_security"]+=1;continue
            canon=aliases.get(code,code)
            if canon not in stocks:
                skipped["security_outside_historical_registry"]+=1
                continue
            if entry.file_size>2_000_000 or entry.file_size%32:
                issues.append("BAD_ENTRY_SIZE_"+entry.filename);continue
            rawbytes=src.read(entry)
            try:
                narrowed,bars=stats_per_stock(rawbytes,anchor,canon,stocks[canon],entry)
            except ValueError as ex:
                issues.append(str(ex));continue
            if not bars:
                skipped["no_matching_sessions"]+=1;continue
            # Canonical modern and legacy codes may coexist: disjoint source days only.
            if canon in members_seen and any(d in registry_seen[canon] for d,*_ in bars):
                issues.append("LEGACY_MODERN_OVERLAP_"+canon);continue
            members_seen.add(canon)
            registry_seen[canon].update(x[0] for x in bars)
            dest.writestr(canon.replace(".","/")+".day",narrowed)
            hi=deque(maxlen=251);lo=deque(maxlen=251);cl=deque(maxlen=119)
            for d,close,high,low,amount,volume,direction in bars:
                row=byday[d]
                market=stocks[canon]["market"]
                row[market+"_bars"]+=1
                row[market+"_amount_cny"]+=amount
                row[market+"_volume_raw"]+=volume
                if direction is None:
                    row[market+"_new_listing_direction_unavailable"]+=1
                else:
                    row[market+"_"+("up" if direction>0 else "down" if direction<0 else "flat")]+=1
                if len(cl)>=19:
                    row[market+"_ma20_eligible"]+=1
                    if close>(sum(list(cl)[-19:])+close)/20:row[market+"_above_ma20"]+=1
                if len(cl)>=59:
                    row[market+"_ma60_eligible"]+=1
                    if close>(sum(list(cl)[-59:])+close)/60:row[market+"_above_ma60"]+=1
                if len(hi)>=59:
                    row[market+"_hi60_eligible"]+=1
                    if high>=max(list(hi)[-59:]):row[market+"_hi60"]+=1
                    if low<=min(list(lo)[-59:]):row[market+"_lo60"]+=1
                if len(hi)>=251:
                    row[market+"_hi252_eligible"]+=1
                    if high>=max(hi):row[market+"_hi252"]+=1
                    if low<=min(lo):row[market+"_lo252"]+=1
                cl.append(close);hi.append(high);lo.append(low)
            reported.append({"security":canon,"source":entry.filename,"rows":len(bars),
                "old_code_aliased":int(canon!=code),
                "original_file_sha256":hashlib.sha256(rawbytes).hexdigest()})
            if ix%2000==0:
                print(json.dumps({"source_files_seen":ix,"valid_stocks":len(reported)}),flush=True)
    # A missing historical K-line is unresolved, never assumed to be suspension.
    coverage=[]
    official_calendar=[]
    for d in dates:
        expected=Counter()
        for s in stocks.values():
            if (not s["listed"] or d>=s["listed"]) and (not s["out"] or d<=s["out"]):
                expected[s["market"]]+=1
        day=byday[d]
        counts={}
        for market in ("sh","sz","bj"):
            bars=day[market+"_bars"]
            if bars>expected[market]:issues.append("BARS_EXCEED_LISTED_"+market+"_"+d)
            counts[market+"_expected"]=expected[market]
            counts[market+"_traded_bars"]=bars
            counts[market+"_unknown_or_suspended"]=max(0,expected[market]-bars)
        all_expected=sum(expected.values())
        all_observed=sum(day[m+"_bars"] for m in ("sh","sz","bj"))
        coverage.append({"date":d,"listed_expected":all_expected,
            "original_trading_bars":all_observed,
            "unresolved_or_suspended":max(0,all_expected-all_observed),
            **counts,
            **{k:round(v,5) if "amount_cny" in k else v for k,v in day.items()}})
    f=root/"market_breadth_1129_days.csv"
    columns=["date","listed_expected","original_trading_bars","unresolved_or_suspended"]
    columns+=sorted({k for r in coverage for k in r if k not in columns})
    with f.open("w",newline="",encoding="utf-8") as h:
        w=csv.DictWriter(h,fieldnames=columns);w.writeheader();w.writerows(coverage)
    with (root/"stock_evidence_index.csv").open("w",newline="",encoding="utf-8") as h:
        w=csv.DictWriter(h,fieldnames=list(reported[0]));w.writeheader();w.writerows(reported)
    full=sum(row["unresolved_or_suspended"]==0 for row in coverage)
    report={"version":"V113","status":"PARTIAL",
      "source":"TDX_OFFICIAL_HSJDAY",
      "data_cutoff":FROZEN_END,"calendar_count":len(dates),
      "source_archive_zip_bytes":raw.stat().st_size,"source_archive_sha256":source_sha,
      "source_stock_file_count":len(reported),"known_historical_registry_count":len(stocks),
      "original_stock_bars":sum(r["original_trading_bars"] for r in coverage),
      "days_with_all_expected_traded":full,
      "unresolved_security_dates":sum(r["unresolved_or_suspended"] for r in coverage),
      "source_filtered_binary_sha256":hashlib.sha256(binary.read_bytes()).hexdigest(),
      "daily_sha256":hashlib.sha256(f.read_bytes()).hexdigest(),
      "skipped_source_codes":dict(skipped),"issue_count":len(issues),"issue_samples":issues[:100],
      "suspended_from_missing_records_certified":False,
      "preclose_ex_rights_adjustment_certified":False,
      "first_listing_day_direction_certified":False,
      "historical_release_time_pit_certified":False,
      "fully_accepted":False,"formal_signal_allowed":False}
    (root/"coverage.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="issue_samples"},ensure_ascii=False),flush=True)
    # Original 550MB full package can be redownloaded from URL, but exact immutable filtered binary is archived.
    raw.unlink()
if __name__=="__main__":main()
