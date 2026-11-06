#!/usr/bin/env python3
"""Historical Beijing exchange security registry assembled with separate provenance."""
import csv,hashlib,json,re,urllib.request,io
from datetime import date
from pathlib import Path
from html import unescape
from html.parser import HTMLParser

class Tabular(HTMLParser):
 def __init__(self):super().__init__();self.in_row=False;self.cell=None;self.row=[];self.rows=[]
 def handle_starttag(self,tag,attrs):
  if tag=="tr":self.in_row=True;self.row=[]
  if self.in_row and tag in ("th","td"):self.cell=[]
 def handle_data(self,data):
  if self.cell is not None:self.cell.append(data)
 def handle_endtag(self,tag):
  if tag in ("th","td") and self.cell is not None:
   self.row.append(unescape("".join(self.cell)).strip());self.cell=None
  if tag=="tr" and self.in_row:
   if self.row:self.rows.append(self.row)
   self.in_row=False

ROOT=Path("v113_beijing_registry");ROOT.mkdir(exist_ok=True)
URL="https://edu.cfsc.com.cn/www/html/412/2025-02-14/319FCA44F1631F78E063CB31A80AE4AC.html"
with urllib.request.urlopen(urllib.request.Request(URL,headers={"User-Agent":"Mozilla/5.0"}),timeout=30) as r:raw=r.read(3_000_000)
(ROOT/"code_mapping_source.html").write_bytes(raw)
html=raw.decode("utf-8","replace")
tables=Tabular();tables.feed(html)
mapping=[]
for cells in tables.rows:
 if len(cells)<5:continue
 for i in range(len(cells)-4):
  group=cells[i:i+5]
  if re.fullmatch(r"\d{1,3}",group[0]) and re.fullmatch(r"\d{6}",group[3]) and re.fullmatch(r"920\d{3}",group[4]):
   try:dt=date.fromisoformat(group[2])
   except ValueError:continue
   mapping.append({"code":group[4],"old_code":group[3],"name":group[1],"listed":dt.isoformat(),
      "delisted":"","source":"BROKER_PUBLISHED_BSE_MIGRATION_TABLE"})
   break
if len(mapping)<170:raise ValueError("MIGRATION_MAPPING_INCOMPLETE_"+str(len(mapping)))
with open("v113_beijing_pilot/stock_info_bj_name_code.csv",newline="",encoding="utf-8-sig") as f:rows=list(csv.DictReader(f))
stocks={}
for r in rows:
 code=r["证券代码"]
 if not re.fullmatch(r"920\d{3}",code):raise ValueError("BAD_CURRENT_CODE_"+code)
 listed=str(r.get("上市日期",""))[:10]
 if not re.fullmatch(r"\d{4}-\d{2}-\d{2}",listed):raise ValueError("NO_IPO_DATE_"+code)
 stocks[code]={"code":code,"listed":max(listed,"2021-11-15"),"delisted":"",
                "old_code":"","name":r["证券简称"],"source":"BSE_CURRENT_REGISTRY"}
for row in mapping:
 code=row["code"]
 if code in stocks:
  if stocks[code]["listed"]!=max(row["listed"],"2021-11-15"):
   raise ValueError("LISTING_DATE_CONFLICT_"+code)
  stocks[code]["old_code"]=row["old_code"]
 else:
  stocks[code]={**row,"listed":max(row["listed"],"2021-11-15")}
# End-dated BSE stocks are absent from current membership but present in code conversion table.
# Record only independently documented end dates; unknown termination remains explicitly uncertified.
for code,day in {"920305":"2026-07-30","920680":"2026-01-05"}.items():
 if code not in stocks:raise ValueError("KNOWN_DELISTED_MISSING_"+code)
 stocks[code]["delisted"]=day
 stocks[code]["delist_source"]="HISTORICAL_BSE_DELIST_NEEDS_OFFICIAL_CONFIRMATION"
# Three known board-transfer predecessor codes were no longer in the 2025 mapping/current registry.
# These are explicitly secondary evidence, not assumed to be new 920 tickers.
transfer=[
 {"code":"833994","listed":"2021-11-15","delisted":"2022-07-25","name":"翰博高新"},
 {"code":"833874","listed":"2021-11-15","delisted":"2022-07-18","name":"泰祥股份"},
 {"code":"832317","listed":"2021-11-15","delisted":"2022-04-26","name":"观典防务"}]
for x in transfer:
 x.update(old_code=x["code"],source="PUBLIC_SECONDARY_TRANSFER_HISTORY")
 stocks[x["code"]]=x
codes=list(stocks)
if len(codes)!=len(set(codes)):raise ValueError("DUPLICATE_REGISTRY")
out=sorted(stocks.values(),key=lambda x:x["code"])
keys=("code","old_code","name","listed","delisted","source")
with (ROOT/"beijing_historical_registry.csv").open("w",newline="",encoding="utf-8") as f:
 w=csv.DictWriter(f,fieldnames=keys,extrasaction="ignore");w.writeheader();w.writerows(out)
report={"version":"V113","current_registry":len(rows),"mapping":len(mapping),
  "total_unique_historical_bj_securities":len(out),"secondary_transfers":3,
  "code_source_url":URL,"code_source_sha256":hashlib.sha256(raw).hexdigest(),
  "registry_sha256":hashlib.sha256((ROOT/"beijing_historical_registry.csv").read_bytes()).hexdigest(),
  "pit_certified":False,"formal_signal_allowed":False}
(ROOT/"registry_audit.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(report,ensure_ascii=False))
