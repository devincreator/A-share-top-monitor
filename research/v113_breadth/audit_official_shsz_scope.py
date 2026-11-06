#!/usr/bin/env python3
"""Scoped SH/SZ membership audit: separate issuer-vs-equity ticker metrics and exact dates."""
import argparse,csv,json,hashlib
from pathlib import Path
def audit(basics):
    if len({r["code"] for r in basics})!=len(basics):raise ValueError("DUPLICATE_CODE")
    equity=[r for r in basics if r.get("type")=="1" and r["code"].startswith(("sh.","sz."))]
    # Official SSE 'listed company count' is NOT the same as listed-stock count (A+B).
    # Do not report discrepancies as missing securities until instrument scope matches.
    official=[{"date":"2026-09-30","exchange":"sh","metric":"LISTED_COMPANIES_ALL_SHARE_CLASSES",
               "value":2323,"source_url":"https://star.sse.com.cn/aboutus/publication/monthly/overview/"},
              {"date":"2026-09-30","exchange":"sh","metric":"LISTED_STOCKS_ALL_SHARE_CLASSES",
               "value":2361,"source_url":"https://star.sse.com.cn/aboutus/publication/monthly/overview/"}]
    compared=[]
    for record in official:
        d=record["date"]
        observed=sum(r["code"].startswith("sh.") and
             (not r.get("ipoDate") or r["ipoDate"]<=d) and
             (not r.get("outDate") or r["outDate"]>=d) for r in equity)
        compared.append({**record,"vendor_type1_equity_tickers":observed,
          "metric_same_definition":False,
          "numeric_difference_descriptive_only":observed-record["value"],
          "conclusion":"NOT_COMPARABLE_ISSUER_OR_ALL_CLASS_AGAINST_A_TICKERS"})
    return {"version":"V113-SHSZ","audit":"HISTORICAL_UNIVERSE_DEFINITION",
      "scope":"SH_SZ_ONLY","official_comparisons":compared,
      "independent_stock_identity_reconciliation_certified":False,
      "formal_signal_allowed":False}
def main():
    p=argparse.ArgumentParser();p.add_argument("--basic",required=True);p.add_argument("--out",required=True)
    a=p.parse_args()
    with open(a.basic,newline="",encoding="utf-8-sig") as f:rows=list(csv.DictReader(f))
    result=audit(rows);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    result["input_sha256"]=hashlib.sha256(Path(a.basic).read_bytes()).hexdigest()
    (out/"scope_audit.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(result,ensure_ascii=False))
if __name__=="__main__":main()
