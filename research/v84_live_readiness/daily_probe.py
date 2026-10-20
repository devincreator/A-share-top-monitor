#!/usr/bin/env python3
"""Pilot source availability probe for SH/SZ trading bars, research only.

No signal generation. A green GitHub job means the audit ran, not that data passed.
"""
import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

BASE='https://money-tree.eyunzhu.com/daily_kline/date/'


def validate(raw, day):
    rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
    if len(rows)<100:
        raise ValueError('source has fewer than 100 records')
    required={'symbol','trade_date','open','high','low','close','pct_chg','vol'}
    if not required.issubset(rows[0]):
        raise ValueError('source schema mismatch')
    seen=set();adv=0;total=0;invalid=0
    for row in rows:
        symbol=row['symbol']
        if row['trade_date']!=day or symbol in seen:
            invalid+=1;continue
        seen.add(symbol)
        if not symbol.endswith(('.SZ','.SH')):
            continue
        try:
            o,h,l,c=[float(row[k]) for k in ('open','high','low','close')]
            pct=float(row['pct_chg']);vol=float(row['vol'])
            if not (0<l<=min(o,c)<=max(o,c)<=h and vol>=0 and -100<pct<300):
                invalid+=1;continue
        except (ValueError,KeyError):
            invalid+=1;continue
        total+=1
        adv+=pct>0
    if invalid:
        raise ValueError(f'{invalid} duplicate, date-mismatch or invalid-price rows')
    if total<100:
        raise ValueError('too few SH/SZ bars')
    return {'source_rows':len(rows),'unique_sh_sz_traded_bars':total,
            'positive_raw_pct_chg_count':adv,
            'observed_traded_advance_share':round(adv/total,8),
            'observed_traded_breadth_is_PIT_certified':False}


def probe(day, *, request=urllib.request.urlopen):
    dt.datetime.strptime(day,'%Y%m%d')
    url=BASE+day+'.csv'
    result={'date':day,'source_url':url,'status':'DATA_UNAVAILABLE','scope':'OBSERVED_TRADING_BARS_ONLY',
            'PIT_CERTIFIED':False,'FORMAL_SIGNAL_ALLOWED':False}
    for i in range(3):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 v84-research-readiness'})
            with request(req,timeout=35) as response:
                raw=response.read(14_000_001)
            if len(raw)>14_000_000:
                raise ValueError('source response too large')
            details=validate(raw,day)
            result.update(status='RAW_DAILY_INTEGRITY_PASS',sha256=hashlib.sha256(raw).hexdigest(),
                          source_bytes=len(raw),**details)
            return result,raw
        except Exception as exc:
            result['error']=type(exc).__name__+': '+str(exc)[:200]
            if isinstance(exc,urllib.error.HTTPError) and exc.code==404:
                break
            if i<2:
                time.sleep(3*(i+1))
    return result,None


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--date',default=dt.datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y%m%d'))
    p.add_argument('--output-dir',default='v84_daily_probe_output')
    args=p.parse_args(argv)
    result,raw=probe(args.date)
    root=Path(args.output_dir);root.mkdir(parents=True,exist_ok=True)
    if raw is not None:
        (root/(args.date+'.csv')).write_bytes(raw)
    (root/'probe.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(result,ensure_ascii=False))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
