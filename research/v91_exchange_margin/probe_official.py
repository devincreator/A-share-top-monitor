#!/usr/bin/env python3
"""V91 read-only exchange margin source pilot; no backfills and no official alerts.

SZSE AKShare stock_margin_szse() reports *100 million CNY* (亿元).
SSE AKShare stock_margin_sse() reports CNY (元). Do not conflate.
A request-bound date without a response date is not independently certified.
"""
import argparse
import datetime as dt
import decimal
import hashlib
import json
import math
import time
from pathlib import Path

PILOTS=("2024-08-08","2023-09-22","2024-06-20",
        "2025-01-07","2026-10-20")


def normalize_day(value):
    s=str(value).strip()
    if len(s)==8 and s.isdigit():
        return dt.datetime.strptime(s,"%Y%m%d").date().isoformat()
    return dt.date.fromisoformat(s[:10]).isoformat()


def decimal_number(value):
    x=decimal.Decimal(str(value).replace(",","").strip())
    if not x.is_finite() or x<=0:
        raise ValueError("nonpositive/nonfinite balance")
    return x


def parse_summary(exchange, df, requested_date):
    """Return a tentative official-site extraction, never a formal PIT record."""
    if df is None or len(df)!=1:
        raise ValueError(f"{exchange}: expected exactly one summary row, got {0 if df is None else len(df)}")
    rows=df.to_dict(orient="records")
    row=rows[0]
    names=set(str(k) for k in row)
    if "融资余额" not in names:
        raise ValueError(f"{exchange}: financing balance column missing: {sorted(names)}")
    value=decimal_number(row["融资余额"])
    request=normalize_day(requested_date)
    output={"exchange":exchange,"requested_date":request,
            "source_kind":"AKShare wrapper of exchange financing market summary",
            "source_response_date_verified":False,
            "research_only":True,"formal_signal_allowed":False}
    if exchange=="SSE":
        # See AKShare stock_margin_sse documentation: 元
        yuan=value
        output["reported_unit"]="CNY"
    elif exchange=="SZSE":
        # See AKShare stock_margin_szse documentation: 亿元
        yuan=value*decimal.Decimal(100_000_000)
        output["reported_unit"]="100M_CNY"
        output["original_balance_100M_CNY"]=str(value)
        output["rounded_balance_not_exact_yuan"]=True
    else:
        raise ValueError("unsupported exchange")
    if not decimal.Decimal("100000000000")<yuan<decimal.Decimal("3000000000000"):
        raise ValueError(f"{exchange}: balance magnitude inconsistent with expected unit")
    explicit_dates=[]
    for name in ("信用交易日期","日期","交易日期","tradeDate"):
        if name in row:
            explicit_dates.append(normalize_day(row[name]))
    if any(day!=request for day in explicit_dates):
        raise ValueError(f"{exchange}: response date disagrees with requested {request}")
    output["source_response_date_verified"]=bool(explicit_dates)
    output["balance_yuan_from_source"]=str(yuan)
    output["date_provenance"]="RESPONSE_DATE_MATCHED" if explicit_dates else "REQUEST_PARAMETER_ONLY"
    output["status"]="EXCHANGE_WRAPPER_SCHEMA_CANDIDATE_NOT_PIT"
    return output


def compare_jin10(extracted, original_record):
    if original_record is None:
        return {"status":"NO_JIN10_DATE_TO_COMPARE"}
    name="balance_sh_yuan" if extracted["exchange"]=="SSE" else "balance_sz_yuan"
    try:
        historical=decimal_number(original_record[name])
    except (ValueError,KeyError,decimal.InvalidOperation) as exc:
        return {"status":"JIN10_INVALID_SOURCE_VALUE",
                "error":type(exc).__name__}
    official=decimal.Decimal(extracted["balance_yuan_from_source"])
    diff=abs(official-historical)
    # 100M CNY display-unit roundoff is at most 0.5M CNY
    # if the source has 2 decimal digits. Do not claim exact equality.
    limit=decimal.Decimal("500000") if extracted["exchange"]=="SZSE" else decimal.Decimal("1")
    if diff<=limit:
        flag="CONSISTENT_WITH_SOURCE_ROUNDING"
    else:
        flag="SOURCE_DISAGREEMENT"
    return {"status":flag,
            "absolute_disagreement_yuan":str(diff),
            "requested_jin10_balance_yuan":str(historical),
            "tolerance_yuan":str(limit)}


def run_pilot(input_file, output_dir, dates=PILOTS, *, api=None, sleep=time.sleep):
    root=Path(output_dir)
    root.mkdir(parents=True,exist_ok=True)
    raw=Path(input_file).read_bytes()
    candidate=json.loads(raw)
    jin10={r["date"]:r for r in candidate.get("financing",[])}
    indexdates={r["date"] for r in candidate.get("indices",{}).get("000985",[])}
    results={"version":1,"status":"RESEARCH_SOURCE_PILOT",
             "source_input_sha256":hashlib.sha256(raw).hexdigest(),
             "formal_signal_allowed":False,"PIT_certified":False,"production_updated":False,
             "date_scoping_warning":"SZSE summary has no explicit date in reported fields; request parameter only",
             "days":[]}
    if api is None:
        import akshare as api
        results["akshare_version"]=getattr(api,"__version__","unknown")
    for requested in dates:
        day=normalize_day(requested)
        record={"requested_date":day,"is_in_000985_index_calendar":day in indexdates,
                "in_jin10_financing":day in jin10,"sources":{}}
        if day not in indexdates:
            record["status"]="REJECTED_NOT_INDEX_DAY"
            results["days"].append(record)
            continue
        for exchange in ("SSE","SZSE"):
            entry={"status":"SOURCE_FAILED","exchange":exchange,
                   "formal_signal_allowed":False}
            try:
                # A transient network reset is not an observation. Retry at most twice.
                for attempt in range(1,4):
                    try:
                        if exchange=="SSE":
                            df=api.stock_margin_sse(start_date=day.replace("-",""),
                                                    end_date=day.replace("-",""))
                        else:
                            df=api.stock_margin_szse(date=day.replace("-",""))
                        break
                    except Exception as exc:
                        transient=(isinstance(exc,(ConnectionError,TimeoutError,OSError))
                                   or type(exc).__name__ in {
                                       "ConnectionError","ConnectTimeout","ReadTimeout",
                                       "Timeout","RemoteDisconnected"})
                        if attempt==3 or not transient:
                            raise
                        sleep(1.5*attempt)
                entry["network_attempts"]=attempt
                # Persist returned dataframe *before* schema checks, for audit.
                csv_path=root/f"{exchange.lower()}_{day}_raw.csv"
                df.to_csv(csv_path,index=False)
                entry["raw_csv_sha256"]=hashlib.sha256(csv_path.read_bytes()).hexdigest()
                entry["raw_rows"]=len(df)
                entry["raw_columns"]=[str(x) for x in df.columns]
                entry["source"]=parse_summary(exchange,df,day)
                entry["comparison_with_jin10"]=compare_jin10(entry["source"],jin10.get(day))
                entry["status"]="SOURCE_OBSERVED_CANDIDATE_NOT_PIT"
            except Exception as exc:
                entry["error"]=f"{type(exc).__name__}: {str(exc)[:300]}"
            record["sources"][exchange]=entry
            sleep(0.4)
        results["days"].append(record)
    results["exchange_source_success_count"]=sum(
        r["status"]=="SOURCE_OBSERVED_CANDIDATE_NOT_PIT"
        for item in results["days"] for r in item["sources"].values())
    results["exchange_source_failure_count"]=sum(
        r["status"]=="SOURCE_FAILED"
        for item in results["days"] for r in item["sources"].values())
    (root/"official_exchange_pilot.json").write_text(
        json.dumps(results,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return results


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",default="v89_source_audit_output/candidate_inputs.json")
    p.add_argument("--out",default="v91_exchange_pilot")
    p.add_argument("--dates",nargs="*",default=list(PILOTS))
    a=p.parse_args()
    report=run_pilot(a.input,a.out,dates=a.dates)
    print(json.dumps({"observed":report["exchange_source_success_count"],
                      "failed":report["exchange_source_failure_count"],
                      "formal_signal_allowed":False},ensure_ascii=False))
    return 0  # Running probe is not equivalent to passing science gates.


if __name__=="__main__":
    raise SystemExit(main())
