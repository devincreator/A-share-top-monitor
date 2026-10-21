#!/usr/bin/env python3
"""V89 independent primitive data source probe. Never updates production."""
import argparse
import datetime as dt
import hashlib
import json
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

from strict_gate import CODES, assess


def latest_research_source_day(ledger):
    root=Path(ledger)
    if not root.is_dir():
        return None
    dates=[]
    for f in root.glob("*.json"):
        try:
            obj=json.loads(f.read_text(encoding="utf-8"))
            iso=dt.date.fromisoformat(obj["observation_date"])
            if obj.get("source_format_verified") is True and obj.get("source_raw_sha256"):
                dates.append(iso)
        except (OSError,KeyError,ValueError,json.JSONDecodeError):
            continue
    if not dates:
        return None
    return max(dates).isoformat()


def source_official_csi(code,asof,out, *, open_url=urllib.request.urlopen):
    start=dt.date.fromisoformat(asof)-dt.timedelta(days=45)
    params=urllib.parse.urlencode({"indexCode":code,
        "startDate":start.strftime("%Y%m%d"),
        "endDate":asof.replace("-","")})
    url="https://www.csindex.com.cn/csindex-home/perf/index-perf?"+params
    row={"source":"csindex official performance endpoint",
         "index":code,"status":"FAILED","url":url,"formal_signal_allowed":False}
    try:
        request=urllib.request.Request(url,headers={
            "User-Agent":"Mozilla/5.0",
            "Referer":"https://www.csindex.com.cn/"})
        with open_url(request,timeout=25) as resp:
            payload=resp.read(3_000_001)
        if len(payload)>3_000_000:
            raise ValueError("response exceeds bounded sample size")
        name=f"official_csi_{code}_raw.json"
        (out/name).write_bytes(payload)
        row["sha256"]=hashlib.sha256(payload).hexdigest()
        doc=json.loads(payload)
        if not isinstance(doc,dict):
            raise ValueError("response top level not object")
        data=doc.get("data")
        row["response_top_level_fields"]=sorted(str(k) for k in doc)[:30]
        row["raw_rows"]=len(data) if isinstance(data,list) else None
        if isinstance(data,list) and data and isinstance(data[0],dict):
            row["row_field_names"]=sorted(data[0])[:50]
            row["first_raw_trade_date"]=str(data[0].get("tradeDate",""))
        row["status"]="RAW_DOWNLOADED_NOT_YET_MAPPED" if isinstance(data,list) and data else "EMPTY_OR_UNKNOWN_PAYLOAD"
    except Exception as exc:
        row["error"]=f"{type(exc).__name__}: {str(exc)[:180]}"
    return row


def normalize_akshare_index(data, code, asof):
    required={"日期","收盘","成交额","换手率"}
    if not required.issubset(data.columns):
        raise ValueError("required AKShare index columns missing")
    records=[]
    for raw in data.to_dict("records"):
        day=str(raw["日期"])[:10]
        if day>asof:
            continue
        records.append({
            "code":code,"date":day,
            "close":raw["收盘"],"amount":raw["成交额"],"turnover":raw["换手率"]})
    if not records:
        raise ValueError("index provider returned zero eligible observations")
    return records


def normalize_finance(data_sh,data_sz,asof):
    def one(data,name):
        x=data.reset_index()
        cols=[str(c) for c in x.columns]
        date_col="日期" if "日期" in cols else cols[0]
        options=[c for c in cols if "融资余额" in c and "融券" not in c]
        if len(options)!=1:
            raise ValueError(f"{name}: ambiguous financing columns {options}")
        result={}
        for item in x[[date_col,options[0]]].to_dict("records"):
            k=str(item[date_col])[:10]
            if k<=asof:
                if k in result:
                    raise ValueError(f"{name}: duplicate financing date {k}")
                result[k]=item[options[0]]
        return result
    sh=one(data_sh,"sh");sz=one(data_sz,"sz")
    return [{"date":d,"balance_sh_yuan":sh[d],"balance_sz_yuan":sz[d]}
            for d in sorted(sh.keys() & sz.keys())]


def probe_all(ledger,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    asof=latest_research_source_day(ledger)
    report={"schema_version":1,"asof_selected_from_raw_ledger":asof,
        "research_only":True,"formal_signal_generated":False,"attempts":[],
        "gate_status":"BLOCKED"}
    if asof is None:
        report["reason"]="No independently SHA-audited observed raw trading date"
        return report
    inputs={"indices":{},"source_labels":{},"financing":[]}
    for code in CODES:
        report["attempts"].append(source_official_csi(code,asof,out))
    try:
        import akshare as ak
        report["akshare_version"]=getattr(ak,"__version__","unknown")
        start=(dt.date.fromisoformat(asof)-dt.timedelta(days=1700)).strftime("%Y%m%d")
        end=asof.replace("-","")
        for code in CODES:
            item={"source":"akshare.index_zh_a_hist / Eastmoney",
                  "index":code,"status":"FAILED","formal_signal_allowed":False}
            try:
                raw=ak.index_zh_a_hist(symbol=code,period="daily",start_date=start,end_date=end)
                raw_path=out/f"eastmoney_index_{code}_raw.csv"
                raw.to_csv(raw_path,index=False)
                item["raw_sha256"]=hashlib.sha256(raw_path.read_bytes()).hexdigest()
                inputs["indices"][code]=normalize_akshare_index(raw,code,asof)
                inputs["source_labels"][code]="akshare Eastmoney, instrument by query param (NOT independently ID-certified)"
                item.update(status="SOURCE_OBSERVED_RESEARCH_ONLY",raw_rows=len(raw),normalized_rows=len(inputs["indices"][code]))
            except Exception as exc:
                item["error"]=f"{type(exc).__name__}: {str(exc)[:200]}"
            report["attempts"].append(item)
        finance={"source":"akshare Jin10 SH/SZ exchange-specific margin reports",
                 "status":"FAILED","formal_signal_allowed":False}
        try:
            sh=ak.macro_china_market_margin_sh()
            sz=ak.macro_china_market_margin_sz()
            for label,frame in (("sh",sh),("sz",sz)):
                p=out/f"jin10_finance_{label}_raw.csv"
                frame.to_csv(p,index=True)
                finance[f"source_sha256_{label}"]=hashlib.sha256(p.read_bytes()).hexdigest()
            inputs["financing"]=normalize_finance(sh,sz,asof)
            inputs["source_labels"]["financing"]="AKShare Jin10 - not independently verified official exchange PIT"
            finance.update(status="SOURCE_OBSERVED_RESEARCH_ONLY",
                           sh_rows=len(sh),sz_rows=len(sz),overlap_rows=len(inputs["financing"]))
        except Exception as exc:
            finance["error"]=f"{type(exc).__name__}: {str(exc)[:200]}"
        report["attempts"].append(finance)
    except Exception as exc:
        report["attempts"].append({"source":"akshare dependency",
            "status":"UNAVAILABLE","error":f"{type(exc).__name__}: {str(exc)[:200]}"})
    input_file=out/"candidate_inputs.json"
    input_file.write_text(json.dumps(inputs,ensure_ascii=False,indent=2,default=str)+"\n")
    report["candidate_input_sha256"]=hashlib.sha256(input_file.read_bytes()).hexdigest()
    gate=assess(inputs,asof=asof)
    gate["candidate_input_sha256"]=report["candidate_input_sha256"]
    (out/"strict_gate.json").write_text(json.dumps(gate,ensure_ascii=False,indent=2)+"\n")
    report["gate_status"]=gate["status"]
    report["gate_errors"]=gate["errors"]
    # Official and third-party sources are audited separately; agreement is not PIT certification.
    from cross_provider import compare_all
    compare=compare_all(out,asof=asof)
    report["cross_provider_status"]=compare["cross_index_source_status"]
    report["cross_provider_by_index"]={code:{"status":a["status"],"matched":a.get("matched",0),
        "quarantined_non_trading_dates":a.get("quarantined_non_trading_dates",[])}
        for code,a in compare["results"].items()}
    report["financing_source_anomalies"]=compare["financing_history_anomalies"]
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--raw-ledger",default="research/v88_daily_observations/ledger")
    parser.add_argument("--output-dir",default="v89_source_audit_output")
    args=parser.parse_args()
    output=Path(args.output_dir);output.mkdir(parents=True,exist_ok=True)
    result=probe_all(args.raw_ledger,output)
    (output/"source_matrix.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"asof":result["asof_selected_from_raw_ledger"],
        "status":result["gate_status"],
        "attempts":[{"source":p["source"],"index":p.get("index"),"status":p["status"],
                     "rows":p.get("raw_rows") } for p in result["attempts"]]},ensure_ascii=False))
    return 0  # Routine probe may be scientifically BLOCKED yet infrastructure successful.


if __name__=="__main__":
    raise SystemExit(main())
