#!/usr/bin/env python3
"""V95: 1-day observed-traded-sample C50, NOT a PIT whole-market C50.

Price-only and current hindsight membership cannot certify true eligible
listing episodes. This script only analyzes source-native traded A-share rows.
"""
import argparse
import csv
from decimal import Decimal, InvalidOperation, getcontext
import hashlib
import io
import json
from pathlib import Path
import re

getcontext().prec=40
SH_RE=re.compile(r"6[0-9]{5}\.SH$")
SZ_RE=re.compile(r"(00|30)[0-9]{4}\.SZ$")
DATE_RE=re.compile(r"20[0-9]{6}$")
NEEDED={"symbol","trade_date","amount"}


def is_ordinary_sh_sz(symbol):
    return bool(SH_RE.fullmatch(symbol) or SZ_RE.fullmatch(symbol))


def audit_sample(raw,asof,expected_sha):
    source_hash=hashlib.sha256(raw).hexdigest()
    if source_hash!=expected_sha:
        raise ValueError("source SHA256 mismatch")
    expected_date=asof.replace("-","")
    if not DATE_RE.fullmatch(expected_date):
        raise ValueError("date invalid")
    records=list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    if not records or not NEEDED.issubset(records[0]):
        raise ValueError("missing required original source columns")
    seen=set();ordinary=[];excluded={}
    for row in records:
        symbol=(row.get("symbol") or "").strip()
        if row.get("trade_date")!=expected_date:
            raise ValueError("a source row does not belong to expected trading date")
        if symbol in seen:
            raise ValueError(f"duplicated security trade symbol {symbol}")
        seen.add(symbol)
        try:
            money=Decimal(row["amount"])
            if not money.is_finite() or money<=0:
                raise ValueError("nonpositive/nonfinite source turnover amount")
        except (InvalidOperation,TypeError,KeyError) as exc:
            raise ValueError(f"invalid source turnover amount for {symbol}") from exc
        if is_ordinary_sh_sz(symbol):
            ordinary.append((symbol,money))
        else:
            exchange=symbol.rsplit(".",1)[-1] if "." in symbol else "INVALID"
            excluded[exchange]=excluded.get(exchange,0)+1
    if len(ordinary)<50:
        raise ValueError("fewer than 50 traded ordinary SH/SZ A shares")
    ordinary.sort(key=lambda r:(-r[1],r[0]))
    all_amount=sum((m for _,m in ordinary),Decimal(0))
    top_amount=sum((m for _,m in ordinary[:50]),Decimal(0))
    result={
        "schema_version":1,
        "observed_trade_date":asof,
        "source_raw_sha256":source_hash,
        "original_source_row_count":len(records),
        "traded_ordinary_sh_sz_rows":len(ordinary),
        "excluded_source_rows_by_exchange":excluded,
        "c50_traded_source_sample_pct":str(top_amount/all_amount*100),
        "top50_source_native_amount_sum":str(top_amount),
        "all_traded_source_native_amount_sum":str(all_amount),
        "top50_source_symbols":[s for s,_ in ordinary[:50]],
        "source_native_amount_unit":"UNKNOWN; ratio dimensionless",
        "top50_rule":"ordinary SH codes 6xxxxx, SZ codes 00xxxx or 30xxxx; tie code ascending",
        "C50_market_PIT_certified":False,
        "eligible_listed_universe_independently_verified":False,
        "suspended_or_source_gaps_certified":False,
        "C50_d20_available":False,
        "C50_prior504_or_756_rank_available":False,
        "formal_signal_allowed":False,
        "use_scope":"ONE_DAY_TRADED_SOURCE_SAMPLE_ONLY_NOT_C50_FORMAL",
        "warning":"Only traded rows from one retrospective source; denominator is not a PIT-certified all-eligible A share universe."
    }
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--csv",required=True)
    p.add_argument("--asof",required=True)
    p.add_argument("--sha256",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    raw=Path(a.csv).read_bytes()
    result=audit_sample(raw,a.asof,a.sha256)
    dest=Path(a.out)
    dest.parent.mkdir(parents=True,exist_ok=True)
    content=json.dumps(result,ensure_ascii=False,indent=2)+"\n"
    if dest.exists():
        if dest.read_text(encoding="utf8")!=content:
            raise ValueError("first-capture C50 research report conflict, refusing overwrite")
    else:
        dest.write_text(content,encoding="utf8")
    print(json.dumps({k:result[k] for k in
       ("observed_trade_date","original_source_row_count",
        "traded_ordinary_sh_sz_rows","c50_traded_source_sample_pct",
        "formal_signal_allowed")},ensure_ascii=False))


if __name__=="__main__":
    main()
