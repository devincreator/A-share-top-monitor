#!/usr/bin/env python3
"""Bridge historical financing gaps from audited V92 raw records, without invented Yuan precision."""
import argparse,csv,hashlib,json
from pathlib import Path
from decimal import Decimal,InvalidOperation

def inspect_pair(root,day):
    values={}
    proofs={}
    for exchange in ("SSE","SZSE"):
        meta=Path(root)/"records"/day/(exchange+".json")
        path=Path(root)/"raw"/exchange/(day+".csv")
        if not meta.is_file() or not path.is_file():return None
        doc=json.loads(meta.read_text(encoding="utf-8"))
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=doc["source_raw_sha256"]:
            raise ValueError("RAW_HASH_CHANGED:"+day+":"+exchange)
        if doc["date"]!=day or doc["exchange"]!=exchange:
            raise ValueError("WRONG_SOURCE_DAY:"+day)
        if doc["PIT_certified"] is not False or doc["formal_signal_allowed"] is not False:
            raise ValueError("UNEXPECTED_RESEARCH_GATE")
        entries=list(csv.DictReader(raw.decode("utf-8-sig").splitlines()))
        if len(entries)!=1:raise ValueError("EXPECTED_ONE_SUMMARY_ROW")
        value=Decimal(entries[0]["融资余额"])
        if not value.is_finite() or value<=0:raise ValueError("INVALID_EXCHANGE_BALANCE")
        if exchange=="SSE":
            if doc["source_unit"]!="CNY" or entries[0].get("信用交易日期")!=day.replace("-",""):
                raise ValueError("SSE_DATE_UNIT_MISMATCH")
            yuan=value
            bounds=(yuan,yuan)
        else:
            if (doc["source_unit"]!="100M_CNY" or
                doc["date_provenance"]!="REQUEST_PARAMETER_ONLY" or
                doc["display_value_not_exact_yuan"] is not True):
                raise ValueError("SZSE_PROVENANCE_MISMATCH")
            yuan=value*Decimal(100000000)
            # Two-decimal yi Yuan data: display only, use conservative half-step bounds.
            delta=Decimal(500000)
            bounds=(yuan-delta,yuan+delta)
        if yuan!=Decimal(str(doc["balance_yuan_from_display"])):
            raise ValueError("SOURCE_DISPLAY_VALUE_CHANGED")
        values[exchange]=(yuan,bounds)
        proofs[exchange]=doc["source_raw_sha256"]
    sh,sz=values["SSE"],values["SZSE"]
    return {"date":day,"sse_exact_yuan":str(sh[0]),
            "szse_display_yuan":str(sz[0]),
            "total_display_yuan_not_exact":str(sh[0]+sz[0]),
            "total_lower_bound_yuan":str(sh[1][0]+sz[1][0]),
            "total_upper_bound_yuan":str(sh[1][1]+sz[1][1]),
            "status":"DUAL_EXCHANGE_SOURCE_RESEARCH_ROUNDED_SZSE",
            "sse_raw_sha256":proofs["SSE"],"szse_raw_sha256":proofs["SZSE"],
            "may_replace_exact_financing_factor":False}

def bridge(root, daily):
    allrows=list(csv.DictReader(Path(daily).open(newline="",encoding="utf-8")))
    result=[];failures=[]
    for row in allrows:
        if row["financing_status"]=="OK":continue
        d=row["source_trade_date"]
        try:
            out=inspect_pair(root,d)
            if out:result.append(out)
        except (ValueError,KeyError,InvalidOperation,OSError,TypeError) as exc:
            failures.append({"date":d,"reason":str(exc)})
    return result,failures

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--ledger",required=True)
    ap.add_argument("--daily",required=True)
    ap.add_argument("--out",required=True)
    a=ap.parse_args()
    restored,failures=bridge(a.ledger,a.daily)
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    p=out/"v92_financing_gap_candidates.csv"
    if restored:
        with p.open("w",newline="",encoding="utf-8") as f:
            writer=csv.DictWriter(f,fieldnames=list(restored[0]))
            writer.writeheader();writer.writerows(restored)
    status={"research_only":True,"restored_source_evidence_count":len(restored),
            "uncertain_szse_precision":True,"exact_usable_from_v92":0,
            "failed_pairs":failures,"formal_signal_allowed":False,
            "note":"Supplementary bounded observations; original financing missing/invalid flags remain untouched."}
    (out/"v92_bridge_report.json").write_text(json.dumps(status,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(status,ensure_ascii=False))
if __name__=="__main__":main()
