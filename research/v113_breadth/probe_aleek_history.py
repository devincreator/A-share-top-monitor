#!/usr/bin/env python3
"""Probe historic multi-day breadth table independently via one publicly accessible page."""
import urllib.request,re,hashlib,json
from html.parser import HTMLParser
from pathlib import Path
class Table(HTMLParser):
    def __init__(self):super().__init__();self.tr=False;self.cell=None;self.row=[];self.rows=[]
    def handle_starttag(self,tag,attrs):
        if tag=="tr":self.tr=True;self.row=[]
        if self.tr and tag in ("td","th"):self.cell=[]
    def handle_data(self,data):
        if self.cell is not None:self.cell.append(data)
    def handle_endtag(self,tag):
        if tag in ("td","th") and self.cell is not None:self.row.append("".join(self.cell).strip());self.cell=None
        if tag=="tr" and self.tr:
            if self.row:self.rows.append(self.row)
            self.tr=False
p=Path("v113_aleek_probe");p.mkdir(exist_ok=True)
obj={}
try:
    req=urllib.request.Request("https://aleek.top/",headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req,timeout=30) as r:b=r.read(1200001)
    (p/"source.html").write_bytes(b)
    s=b.decode("utf-8","replace")
    parser=Table();parser.feed(s)
    rows=[r for r in parser.rows if any(re.fullmatch("2026-(09|10)-[0-9]{2}",v) for v in r)]
    obj={"status":"RAW_OBSERVED","size":len(b),"sha256":hashlib.sha256(b).hexdigest(),
         "all_table_rows":len(parser.rows),"target_month_rows":len(rows),"sample":rows[:8],
         "matched_dates":sorted({v for r in rows for v in r if re.fullmatch("2026-(09|10)-[0-9]{2}",v)})}
except Exception as e:obj={"status":"FAILED","error":str(e)[:300]}
(p/"probe.json").write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(obj,ensure_ascii=False))
