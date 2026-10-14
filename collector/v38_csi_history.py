#!/usr/bin/env python3
"""CSI official daily historical amount/volume archive 2015-2026.
Data only; no proprietary models or scoring. Raw market index values are source/audit.
"""
import json, requests, pandas as pd, time
from pathlib import Path
P=Path('out');P.mkdir(exist_ok=True)
ROOT='https://www.csindex.com.cn/csindex-home/perf/index-perf'
records=[];audit=[]
s=requests.Session();s.headers.update({'User-Agent':'Mozilla/5.0','Referer':'https://www.csindex.com.cn/'})
for yr in range(2015,2027):
    row={'year':yr,'status':'FAIL'}
    try:
        e='20261013' if yr==2026 else f'{yr}1231'
        r=s.get(ROOT,params={'indexCode':'000985','startDate':f'{yr}0101','endDate':e},timeout=40)
        r.raise_for_status()
        data=r.json().get('data',[])
        if not isinstance(data,list): raise ValueError(f'not list: {type(data)}')
        good=[x for x in data if isinstance(x,dict) and str(x.get('tradeDate','')).startswith(str(yr))]
        # Keep all records as returned in raw file; explicitly report schema.
        if data:records.extend(data)
        pd.DataFrame(data).to_csv(P/f'csi_000985_{yr}.csv',index=False)
        row.update(status='retrieved',rows=len(data),columns=list(data[0])[:35] if data else [])
    except Exception as e:row['error']=f'{type(e).__name__}: {str(e)[:220]}'
    audit.append(row)
    print(json.dumps(row,ensure_ascii=False),flush=True)
    time.sleep(.35)
try:
    f=pd.DataFrame(records)
    f.to_csv(P/'csi_000985_combined_unfiltered.csv',index=False)
except Exception as e:audit.append({'combine_error':repr(e)})
(P/'csi_2015_2026_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
