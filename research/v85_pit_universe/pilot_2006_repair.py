#!/usr/bin/env python3
"""Bounded V85 2006 raw gap pilot. Five days ONLY, not PIT certified."""
import csv
import datetime as dt
import hashlib
import io
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

DAYS=['20060313','20060314','20060315','20060316','20060317']
URL='https://money-tree.eyunzhu.com/daily_kline/date/'


def validate(day, content):
    rows=list(csv.DictReader(io.StringIO(content.decode('utf-8-sig'))))
    if len(rows)<100:
        raise ValueError('fewer than 100 rows')
    necessary={'symbol','trade_date','open','high','low','close','pct_chg','vol'}
    if not necessary.issubset(rows[0]):
        raise ValueError('source schema missing fields')
    seen=set()
    for r in rows:
        ticker=r['symbol']
        if ticker in seen or r['trade_date']!=day:
            raise ValueError('duplicate ticker or wrong trade_date')
        seen.add(ticker)
        if ticker.endswith(('.SZ','.SH')):
            o,h,l,c=[float(r[k]) for k in ('open','high','low','close')]
            vol=float(r['vol']);pct=float(r['pct_chg'])
            if not 0<l<=min(o,c)<=max(o,c)<=h or vol<0 or not -100<pct<300:
                raise ValueError('invalid OHLC/vol/return')
    return len(rows)


def fetch(day):
    uri=URL+day+'.csv'
    for attempt in range(5):
        try:
            req=urllib.request.Request(uri,headers={'User-Agent':'Mozilla/5.0 v85-raw-pilot'})
            with urllib.request.urlopen(req,timeout=38) as response:
                content=response.read(14_000_001)
            if len(content)>14_000_000:
                raise ValueError('response too large')
            count=validate(day,content)
            return content,{'date':day,'source_url':uri,'status':'RAW_DAILY_INTEGRITY_PASS',
                            'rows':count,'bytes':len(content),'sha256':hashlib.sha256(content).hexdigest()}
        except Exception as exc:
            last=type(exc).__name__+': '+str(exc)[:160]
            if isinstance(exc,urllib.error.HTTPError) and exc.code==404:
                break
            if attempt<4:
                time.sleep(min(40,4*2**attempt))
    return None,{'date':day,'source_url':uri,'status':'DATA_UNAVAILABLE','error':last}


def main():
    root=Path('v85_2006_gap_pilot');raw=root/'raw';raw.mkdir(parents=True,exist_ok=True)
    audit=[]
    for day in DAYS:
        dt.datetime.strptime(day,'%Y%m%d')
        content,result=fetch(day)
        if content is not None:
            (raw/(day+'.csv')).write_bytes(content)
        audit.append(result)
        print(json.dumps(result),flush=True)
        time.sleep(2)
    report={'expected':len(DAYS),'received':sum(x['status']=='RAW_DAILY_INTEGRITY_PASS' for x in audit),
            'records':audit,'PIT_CERTIFIED':False,'FORMAL_MODEL_ALLOWED':False}
    (root/'gate.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    if report['received']!=report['expected']:
        raise SystemExit('Raw daily gap pilot incomplete; inspect gate.json and artifacts')

if __name__=='__main__':main()
