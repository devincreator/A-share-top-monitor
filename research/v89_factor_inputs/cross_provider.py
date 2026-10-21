#!/usr/bin/env python3
"""Research-only CSI official versus Eastmoney index-data cross-provider audit.

Official index-perf can contain NON-trading dates (e.g. 2026-09-05 Saturday).
Quarantine those dates: do not count as a real trading session.
"""
import datetime as dt
import json
import math
from pathlib import Path

CODES=("000985","000300","000852")
VALUE_UNIT_TO_YUAN=100_000_000  # CSI index-perf tradingValue is in RMB 100 million
PRICE_TOLERANCE=0.02
REL_AMOUNT_TOLERANCE=0.0001


def parsed_day(stamp):
    s=str(stamp).strip()
    if len(s)==8 and s.isdigit():
        return dt.datetime.strptime(s,"%Y%m%d").date()
    return dt.date.fromisoformat(s)


def compare_one(code,official,alternate,asof):
    result={"code":code,"status":"BLOCKED","matched":0,
            "mismatches":[],"quarantined_non_trading_dates":[],
            "official_valid_sessions":0,"provider_independence_certified":False}
    if not isinstance(official,dict) or not isinstance(official.get("data"),list):
        result["mismatches"].append("missing official data list")
        return result
    observed={}
    for row in alternate:
        try:
            d=parsed_day(row["date"])
            if row.get("code")!=code or d in observed:
                raise ValueError("wrong/duplicate alternate index code or date")
            observed[d]=row
        except (KeyError,ValueError,TypeError) as e:
            result["mismatches"].append("alternate data identity/date: "+str(e))
            return result
    known=set()
    for item in official["data"]:
        try:
            if str(item["indexCode"])!=code:
                raise ValueError("wrong official indexCode")
            d=parsed_day(item["tradeDate"])
            if d in known:
                raise ValueError("duplicated official date")
            known.add(d)
            if d.weekday()>=5:
                result["quarantined_non_trading_dates"].append(d.isoformat())
                continue
            if d>parsed_day(asof):
                raise ValueError("date later than selected asof")
            result["official_valid_sessions"]+=1
            if d not in observed:
                result["mismatches"].append(d.isoformat()+": no alternate price")
                continue
            p=float(item["close"])
            q=float(observed[d]["close"])
            if not (math.isfinite(p) and math.isfinite(q) and abs(p-q)<=PRICE_TOLERANCE):
                result["mismatches"].append(d.isoformat()+": close disagreement")
                continue
            v=float(item["tradingValue"])*VALUE_UNIT_TO_YUAN
            w=float(observed[d]["amount"])
            if not (math.isfinite(v) and math.isfinite(w)
                    and v>0 and w>0 and abs(v-w)/w<=REL_AMOUNT_TOLERANCE):
                result["mismatches"].append(d.isoformat()+": amount disagreement after RMB 100m conversion")
                continue
            result["matched"]+=1
        except (ValueError,TypeError,KeyError) as e:
            result["mismatches"].append("official row invalid: "+str(e)[:130])
    if len(result["mismatches"])==0 and result["matched"]>=10 and parsed_day(asof) in known:
        result["status"]="RESEARCH_CROSS_PROVIDER_PASS_WITH_QUARANTINE" if result["quarantined_non_trading_dates"] else "RESEARCH_CROSS_PROVIDER_PASS"
    else:
        result["status"]="BLOCKED"
    return result


def compare_all(output_dir, *, asof):
    root=Path(output_dir)
    inputs=json.loads((root/"candidate_inputs.json").read_text(encoding="utf8"))
    results={}
    for code in CODES:
        name=root/f"official_csi_{code}_raw.json"
        if name.is_file() and inputs.get("indices",{}).get(code):
            try:
                results[code]=compare_one(code,json.loads(name.read_text(encoding="utf8")),inputs["indices"][code],asof)
            except (ValueError,KeyError,TypeError) as e:
                results[code]={"code":code,"status":"BLOCKED","error":type(e).__name__+": "+str(e)[:180]}
        else:
            results[code]={"code":code,"status":"BLOCKED","error":"missing original source and/or normalized candidate"}
    finance=inputs.get("financing",[])
    anomalies=[{"date":x.get("date"),"reason":"one or both exchange financing balances nonpositive",
                "sh_balance":x.get("balance_sh_yuan"),"sz_balance":x.get("balance_sz_yuan")}
               for x in finance if x.get("balance_sh_yuan") is None or x.get("balance_sz_yuan") is None
               or float(x.get("balance_sh_yuan") or 0)<=0 or float(x.get("balance_sz_yuan") or 0)<=0]
    output={"schema_version":1,"asof":asof,
            "cross_index_source_status":"RESEARCH_PRICE_AMOUNT_CROSS_PROVIDER_PASS"
                if all(results[c]["status"].startswith("RESEARCH_CROSS_PROVIDER_PASS") for c in CODES)
                else "BLOCKED",
            "results":results,"financing_history_anomalies":anomalies,
            "finance_PIT_certified":False,"turnover_independently_verified":False,
            "formal_signal_allowed":False,
            "warning":"Matching CSI and Eastmoney may share upstream data; does not imply independent PIT proof or formal signal."}
    (root/"cross_provider_audit.json").write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    return output


if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--output-dir",default="v89_source_audit_output")
    p.add_argument("--asof",required=True)
    args=p.parse_args()
    print(json.dumps(compare_all(args.output_dir,asof=args.asof),ensure_ascii=False))
