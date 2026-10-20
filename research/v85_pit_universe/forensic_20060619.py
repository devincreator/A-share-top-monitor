#!/usr/bin/env python3
"""Forensic preservation of failed raw OHLC file; do not normalize without evidence."""
import csv
import hashlib
import io
import json
import urllib.request
from pathlib import Path

DAY='20060619'
URI=f'https://money-tree.eyunzhu.com/daily_kline/date/{DAY}.csv'
def anomalies(data):
    rows=list(csv.DictReader(io.StringIO(data.decode('utf-8-sig'))))
    invalid=[]
    for i,r in enumerate(rows,1):
        if r.get('trade_date')!=DAY:
            invalid.append({'row':i,'symbol':r.get('symbol'),'error':'date mismatch','source':r});continue
        try:
            o,h,l,c=[float(r[k]) for k in ('open','high','low','close')]
            pct=float(r['pct_chg']);vol=float(r['vol'])
            if not (0<l<=min(o,c)<=max(o,c)<=h and vol>=0 and -100<pct<300):
                invalid.append({'row':i,'symbol':r.get('symbol'),'error':'OHLC/vol/pct outside strict gate','source':r})
        except Exception as e:
            invalid.append({'row':i,'symbol':r.get('symbol'),'error':str(e),'source':r})
    return {'source_rows':len(rows),'invalid_count':len(invalid),'invalid':invalid[:25]}


def main():
    p=Path('v85_anomaly_forensic');p.mkdir(exist_ok=True)
    req=urllib.request.Request(URI,headers={'User-Agent':'Mozilla/5.0 v85-source-forensic'})
    with urllib.request.urlopen(req,timeout=40) as res:data=res.read(14_000_001)
    if len(data)>14_000_000:raise ValueError('unexpected file size')
    (p/f'{DAY}_RAW_UNCERTIFIED.csv').write_bytes(data)
    report=anomalies(data)
    report.update(date=DAY,url=URI,sha256=hashlib.sha256(data).hexdigest(),status='RAW_FORENSIC_UNCERTIFIED',
                  PIT_CERTIFIED=False,FORMAL_MODEL_ALLOWED=False)
    (p/'forensic.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report,ensure_ascii=False)[:8000],flush=True)

if __name__=='__main__':main()
