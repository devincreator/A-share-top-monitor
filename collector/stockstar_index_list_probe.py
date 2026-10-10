"""Probe public StockStar 'index analytics' listing pagination; no backtest rules."""
import requests,re,json
from bs4 import BeautifulSoup
from pathlib import Path
O=Path('out');O.mkdir(exist_ok=True)
s=requests.Session();s.headers.update({'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/122.0 Safari/537.36'})
urls=[
 'https://stock.stockstar.com/list/6571.shtml',
 'https://stock.stockstar.com/list/6571_2.shtml',
 'https://stock.stockstar.com/list/6571_5.shtml',
 'https://stock.stockstar.com/list/6571_25.shtml',
 'https://stock.stockstar.com/list/6571_100.shtml',
 'https://stock.stockstar.com/list/6571_200.shtml',
]
res=[]
for u in urls:
 row={'url':u}
 try:
  r=s.get(u,timeout=18);r.encoding='gb18030';html=r.text
  dom=BeautifulSoup(html,'html.parser')
  text=dom.get_text(' ',strip=True)
  links=[(a.get_text(' ',strip=True),a.get('href')) for a in dom.select('a[href]')]
  arts=[{'text':v,'href':h} for v,h in links if '中证全指' in v and '000985' in v]
  tails=[{'text':v[:45],'href':h} for v,h in links if re.search(r'6571[_-]?\d*\.shtml',h or '')][:18]
  row.update(status=r.status_code,bytes=len(r.content),title=dom.title.get_text(' ',strip=True) if dom.title else '',
             headlines=arts[:15],pagination=tails,text_head=text[:200],article_links=sum(bool(re.search(r'RB20\d{10,}\.shtml',h or '')) for _,h in links))
 except Exception as e:row['error']=str(e)[:250]
 res.append(row);print(json.dumps(row,ensure_ascii=False),flush=True)
(O/'stockstar_pagination.json').write_text(json.dumps(res,ensure_ascii=False,indent=2),encoding='utf8')
