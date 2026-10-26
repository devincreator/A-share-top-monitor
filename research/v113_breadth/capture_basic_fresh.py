#!/usr/bin/env python3
"""Read and archive a fresh complete BaoStock stock_basic response, including source SHA."""
import csv,hashlib,json,argparse
from pathlib import Path
import baostock as bs
def main():
 p=argparse.ArgumentParser();p.add_argument("--out",required=True);a=p.parse_args()
 out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
 s=bs.login()
 if s.error_code!="0":raise RuntimeError("LOGIN_FAILED_"+s.error_msg)
 try:
  rs=bs.query_stock_basic()
  if rs.error_code!="0":raise RuntimeError("QUERY_STOCK_BASIC_FAILED_"+rs.error_msg)
  rows=[]
  while rs.next():rows.append(dict(zip(rs.fields,rs.get_row_data())))
 finally:bs.logout()
 if len(rows)<7000:raise ValueError("IMPLAUSIBLY_SHORT_BASIC_SOURCE")
 with (out/"stock_basic.csv").open("w",newline="",encoding="utf-8") as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 report={"source":"baostock.query_stock_basic()","rows":len(rows),
 "fields":list(rows[0]),"sha256":hashlib.sha256((out/"stock_basic.csv").read_bytes()).hexdigest()}
 (out/"source_audit.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps(report,ensure_ascii=False))
if __name__=="__main__":main()
