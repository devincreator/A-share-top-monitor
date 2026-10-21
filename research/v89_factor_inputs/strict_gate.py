#!/usr/bin/env python3
"""Fail-closed V89 primitive-factor gate. This never certifies a trading signal."""
import datetime as dt
import hashlib
import json
import math
from pathlib import Path

CODES=("000985","000300","000852")
ANCHORS={"2026-08-04":5766.33,"2026-09-30":5648.25,"2026-10-08":5560.01}
MIN_HISTORY=756
MIN_FINANCE_HISTORY=850


def day(v):
    if isinstance(v,dt.date):
        return v.isoformat()
    s=str(v).strip()
    try:
        return dt.date.fromisoformat(s).isoformat()
    except ValueError:
        return dt.datetime.strptime(s,"%Y%m%d").date().isoformat()


def number(v):
    f=float(v)
    if not math.isfinite(f):
        raise ValueError("non-finite numeric field")
    return f


def validate_index(code,records, *, asof):
    if code not in CODES:
        raise ValueError("unsupported index")
    if not isinstance(records,list) or not records:
        raise ValueError("empty index source")
    cleaned,seen=[],set()
    for r in records:
        if not isinstance(r,dict):
            raise ValueError("index row not object")
        if not {"date","close","amount","turnover"}.issubset(r):
            raise ValueError("index row missing date/close/amount/turnover")
        if "code" not in r or str(r["code"]) != code:
            raise ValueError("unverified index identity: code must be bound to every row")
        d=day(r["date"])
        if d in seen:
            raise ValueError("duplicate index trading date")
        seen.add(d)
        close,amount,turnover=(number(r[k]) for k in ("close","amount","turnover"))
        if not (close>0 and amount>0 and 0<=turnover<=100):
            raise ValueError("invalid close/amount/turnover")
        cleaned.append({"date":d,"close":close,"amount":amount,"turnover":turnover})
    cleaned.sort(key=lambda r:r["date"])
    if len(cleaned)<MIN_HISTORY:
        raise ValueError("index history below 756 sessions")
    history={r["date"]:r for r in cleaned}
    if code=="000985":
        for d,v in ANCHORS.items():
            if d not in history or abs(history[d]["close"]-v)>1:
                raise ValueError(f"price index anchor failed at {d}")
    if asof not in history:
        raise ValueError("no index record on independently selected as-of session")
    # All historical dates must be available as-of: no future prices.
    if max(history)>asof:
        raise ValueError("future price row beyond requested as-of")
    return {"code":code,"rows":len(cleaned),"latest":max(history),
            "earliest":min(history),"asof_close":history[asof]["close"],
            "asof_amount":history[asof]["amount"],
            "asof_turnover":history[asof]["turnover"],
            "dates":list(history)}


def validate_financing(records, *, asof):
    if not isinstance(records,list) or not records:
        raise ValueError("empty SH+SZ financing data")
    got=set();lst=[]
    for row in records:
        if not {"date","balance_sh_yuan","balance_sz_yuan"}.issubset(row):
            raise ValueError("missing SH/SZ separate financing in yuan")
        d=day(row["date"])
        if d in got:
            raise ValueError("duplicated financing date")
        got.add(d)
        sh,sz=number(row["balance_sh_yuan"]),number(row["balance_sz_yuan"])
        if sh<=0 or sz<=0:
            raise ValueError("invalid financing balances")
        lst.append((d,sh+sz))
    if len(lst)<MIN_FINANCE_HISTORY:
        raise ValueError("financing history below 850 sessions")
    hist=dict(lst)
    if asof not in hist:
        raise ValueError("financing not released on requested as-of session")
    if max(hist)>asof:
        raise ValueError("future financing row beyond as-of")
    if not 1e12<hist[asof]<1e13:
        raise ValueError("financing yuan unit mismatch")
    return {"rows":len(hist),"latest":max(hist),"earliest":min(hist),
            "asof_balance_sh_sz_yuan":hist[asof]}


def assess(inputs, *, asof):
    asof=day(asof)
    output={"asof":asof,"status":"BLOCKED","research_only":True,
            "formal_signal_allowed":False,"errors":[],"components":{},
            "source_labels":inputs.get("source_labels",{}),
            "scope":"Primitive factors only, NOT actual frozen four-module model"}
    idx=inputs.get("indices",{})
    summaries={}
    for code in CODES:
        try:
            summaries[code]=validate_index(code,idx.get(code),asof=asof)
            output["components"][code]={k:v for k,v in summaries[code].items() if k!="dates"}
        except (TypeError,ValueError,KeyError) as exc:
            output["errors"].append(f"index {code}: {exc}")
    try:
        fin=validate_financing(inputs.get("financing"),asof=asof)
        output["components"]["financing"]=fin
    except (TypeError,ValueError,KeyError) as exc:
        output["errors"].append(f"financing: {exc}")
    if len(summaries)==len(CODES):
        dates=[set(summaries[code]["dates"]) for code in CODES]
        if any(asof not in ds for ds in dates):
            output["errors"].append("cross-index date mismatch")
    if not output["errors"]:
        output["status"]="PRIMITIVE_INPUTS_SCHEMA_VALID_RESEARCH_ONLY"
        output["caveats"]=[
            "Provider responses may not be independent or official historical PIT data.",
            "Same-date observed factors do not prove all fields were published before an actual signal.",
            "Additional 756-session historical factor windows and frozen strategy replication required.",
            "Signals remain disabled regardless of input success."
        ]
    return output


def main():
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--input",required=True)
    p.add_argument("--asof",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    raw=Path(a.input).read_bytes()
    result=assess(json.loads(raw),asof=a.asof)
    result["input_sha256"]=hashlib.sha256(raw).hexdigest()
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"status":result["status"],"errors":result["errors"]},ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
