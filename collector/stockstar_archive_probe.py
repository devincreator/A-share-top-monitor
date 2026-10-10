#!/usr/bin/env python3
"""Probe indexed public daily CSI turnover article archives.
Exploratory, source-preserving, low volume; no derived index turnover replacement.
"""
from pathlib import Path
import requests,json,re,time,urllib.parse
from bs4 import BeautifulSoup
P=Path("out");P.mkdir(exist_ok=True)
terms=['8月5日中证全指 000985 指数 换手率 证券之星', '7月31日中证全指 000985 指数 换手率 证券之星']
sources=[
 ('bing','https://www.bing.com/search', 'q'),
 ('baidu','https://www.baidu.com/s','wd'),
 ('sogou','https://www.sogou.com/web','query')
]
s=requests.Session();s.headers.update({"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"})
out=[]
for name,url,param in sources:
 for term in terms[:1]:
  item={"provider":name,"q":term}
  try:
   r=s.get(url,params={param:term},timeout=15,allow_redirects=True);item["http_code"]=r.status_code
   txt=BeautifulSoup(r.text,"html.parser").get_text(" ",strip=True)
   item["text_head"]=txt[:250]
   item["hits"] = sorted(set(re.findall(r'RB20\d{14}\.shtml',urllib.parse.unquote(r.text))))[:15]
   item["stockstar_mentions"]=r.text.lower().count("stockstar")
   item["rb_mentions"]=r.text.count("RB2026")
   item["bytes"]=len(r.content)
  except Exception as e:item["error"]=f"{type(e).__name__}: {str(e)[:170]}"
  out.append(item); print(json.dumps(item,ensure_ascii=False),flush=True)
url="https://stock.stockstar.com/RB2026080400030995.shtml"
r=s.get(url,timeout=15);r.encoding="gb18030";dom=BeautifulSoup(r.text,"html.parser")
text=dom.get_text(" ",strip=True)
indices=[m.start() for m in re.finditer('换手',text)]
out.append({"provider":"stockstar direct",
 "http_code":r.status_code,"final_url":r.url,"length":len(text),
 "title":dom.title.get_text(" ",strip=True) if dom.title else None,
 "turnover_context":[text[max(0,p-100):p+100] for p in indices[:5]]})
print(json.dumps(out[-1],ensure_ascii=False),flush=True)
(P/"stockstar_archive_probe.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
