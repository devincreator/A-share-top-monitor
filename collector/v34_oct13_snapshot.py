#!/usr/bin/env python3
"""Append-only public market check for 2026-10-12 and 2026-10-13. Never publishes strategy logic."""
import json,requests
from pathlib import Path
P=Path('out');P.mkdir(exist_ok=True)
END='2026-10-13'
a={'end':END,'sources':{},'errors':[]}
s=requests.Session()
for code in ['sh000985','sh000300','sh000852']:
 try:
  resp=s.get('https://api.ashareapi.com/v1/kline',params={'code':code,'period':'day','count':8,'end':END},timeout=25)
  resp.raise_for_status();d=resp.json()
  a['sources']['ashareapi_'+code]=d.get('data',[])
 except Exception as e:a['errors'].append(code+': '+repr(e))
try:
 import akshare as ak
 for code in ['000985','000300','000852']:
  try:
   f=ak.stock_zh_index_daily_tx(symbol='sh'+code,start_date='20261008',end_date='20261013')
   a['sources']['tencent_'+code]=f.to_dict('records')
  except Exception as e:a['errors'].append('tencent '+code+': '+repr(e))
 for date in ['20261009','20261012','20261013']:
  try:
   f=ak.stock_margin_bse(date=date)
   a['sources']['bse_'+date]=f.to_dict('records')
  except Exception as e:a['errors'].append('bse '+date+': '+repr(e))
 for place in ['sh','sz']:
  try:
   f=getattr(ak,'macro_china_market_margin_'+place)().reset_index()
   a['sources']['financing_'+place+'_tail']=f.tail(7).to_dict('records')
  except Exception as e:a['errors'].append('financing '+place+': '+repr(e))
except Exception as e:a['errors'].append('akshare '+repr(e))
try:
 resp=s.get('https://www.csindex.com.cn/csindex-home/perf/index-perf',params={'indexCode':'000985','startDate':'20261009','endDate':END},timeout=30)
 resp.raise_for_status();a['sources']['csindex']=resp.json()
except Exception as e:a['errors'].append('csindex '+repr(e))
(P/'v34_20261013_public_snapshot.json').write_text(json.dumps(a,ensure_ascii=False,indent=2,default=str),encoding='utf8')
print(json.dumps(a,ensure_ascii=False,default=str)[:25000],flush=True)
