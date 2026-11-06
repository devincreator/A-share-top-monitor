#!/usr/bin/env python3
"""V113 SH/SZ official *A-share* issuer benchmark, not all-company total including B-only."""
import csv,json,hashlib,argparse
from pathlib import Path
URL="https://capcofile.oss-cn-beijing.aliyuncs.com/2026/yuebao/12/中上协统计月报（2025年12月）.pdf"
# CAPCO 2025-12 PDF page 1, A-share total columns by exchange (not total-company columns).
OFFICIAL={"2022-12-30":(2169,2736),"2023-12-29":(2258,2838),
"2024-12-31":(2274,2847),"2025-01-27":(2279,2853),
"2025-02-28":(2278,2853),"2025-03-31":(2278,2862),
"2025-04-30":(2280,2866),"2025-05-30":(2280,2867),
"2025-06-30":(2284,2868),"2025-07-31":(2282,2868),
"2025-08-29":(2283,2870),"2025-09-30":(2284,2875),
"2025-10-31":(2289,2875),"2025-11-28":(2293,2876),
"2025-12-31":(2299,2883)}
def eligible(row,day):
 return (not row.get("ipoDate") or row["ipoDate"]<=day) and (not row.get("outDate") or day<=row["outDate"])
def audit(stocks,targets=OFFICIAL):
 result=[]
 for day,(sh,sz) in sorted(targets.items()):
  for exchange,n in (("sh",sh),("sz",sz)):
   found=sum(r["code"].startswith(exchange+".") and eligible(r,day) for r in stocks)
   result.append({"date":day,"exchange":exchange,"official_a_issuers":n,
      "basic_a_issuers":found,"delta":found-n,"matches":found==n})
 return result
def main():
 p=argparse.ArgumentParser();p.add_argument("--basic",required=True);p.add_argument("--out",required=True);a=p.parse_args()
 with open(a.basic,encoding="utf-8-sig",newline="") as f:
  stocks=[r for r in csv.DictReader(f) if r["type"]=="1" and r["code"].startswith(("sh.","sz."))]
 results=audit(stocks);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
 with (out/"a_only_issuer_audit.csv").open("w",newline="",encoding="utf-8") as f:
  w=csv.DictWriter(f,fieldnames=list(results[0]));w.writeheader();w.writerows(results)
 bad=[x for x in results if not x["matches"]]
 report={"version":"V113-SHSZ","comparisons":len(results),"matching":len(results)-len(bad),
   "mismatches":bad,"official_a_share_source":URL,"benchmark_issuer_type":"A_SHARE_ISSUERS",
   "historical_exchange_universe_certified":False,"source_publication_pit_certified":False,
   "formal_signal_allowed":False,"status":"PASS" if not bad else "PARTIAL",
   "basic_sha256":hashlib.sha256(Path(a.basic).read_bytes()).hexdigest()}
 (out/"acceptance.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps(report,ensure_ascii=False))
if __name__=="__main__":main()
