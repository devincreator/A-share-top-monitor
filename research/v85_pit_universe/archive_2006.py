#!/usr/bin/env python3
"""Archive 2006 RAW source bytes from Actions artifacts; never certify PIT history."""
import argparse
import csv
import hashlib
import io
import json
import urllib.request
import zipfile
from pathlib import Path

CALENDAR='https://raw.githubusercontent.com/sky910140/financial-agent-takehome/e071088057946de60ba1622dec8a69acce1481cd/data/market/sse_composite.csv'
CAL_SHA='fc4bd4c4ee3b1659aec07e0622d8dc8ab7df95f8354b7b4f9230a3a05bfffd20'
SPECIAL_SHA='fe0bb95c2668667862425e8748e39a0200d6a1fc1748ed1914e579b42def44ee'


def validate(day, raw):
    data=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
    required={'symbol','trade_date','open','high','low','close','vol','pct_chg'}
    if len(data)<100 or not required.issubset(data[0]):
        raise ValueError(f'{day}: short file or missing columns')
    seen=set()
    for r in data:
        ticker=r['symbol']
        if ticker in seen or r['trade_date']!=day:
            raise ValueError(f'{day}: duplicate/date issue {ticker}')
        seen.add(ticker)
        if not ticker.endswith(('.SZ','.SH')):
            continue
        o,h,l,c=[float(r[k]) for k in ('open','high','low','close')]
        v=float(r['vol']);p=float(r['pct_chg'])
        exception=(day=='20060619' and ticker=='002051.SZ'
                   and abs(float(r.get('pre_close','0'))-7.4)<.001
                   and abs(o-17.11)<.001 and abs(h-50)<.001 and abs(l-15.5)<.001
                   and abs(c-31.97)<.001 and abs(p-332.03)<.01)
        if not 0<l<=min(o,c)<=max(o,c)<=h or v<0 or not (-100<p<300 or exception):
            raise ValueError(f'{day}: unexpected price/return {ticker} {p}')
    return len(data)


def read_calendar():
    with urllib.request.urlopen(CALENDAR,timeout=40) as res:raw=res.read()
    if hashlib.sha256(raw).hexdigest()!=CAL_SHA:
        raise ValueError('calendar SHA mismatch')
    dates={r['date'].replace('-','') for r in csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))}
    expected=sorted(d for d in dates if d.startswith('2006'))
    if len(expected)!=241:
        raise ValueError(f'calendar unexpectedly contains {len(expected)} trading days')
    return expected


def archive(input_dir, out, *, expected=None):
    root=Path(input_dir)
    paths=[p for p in root.rglob('*.csv')
           if (p.parent.name=='raw' and len(p.stem)==8 and p.stem.startswith('2006'))
           or p.name=='20060619_RAW_UNCERTIFIED.csv']
    if not paths:raise ValueError('no source artifacts found')
    merged={};provenance={}
    for p in sorted(paths):
        d='20060619' if p.name=='20060619_RAW_UNCERTIFIED.csv' else p.stem
        b=p.read_bytes();h=hashlib.sha256(b).hexdigest()
        if d=='20060619' and h!=SPECIAL_SHA:
            raise ValueError('IPO exception raw hash changed')
        n=validate(d,b)
        if d in merged and merged[d]!=b:
            raise ValueError(f'{d}: conflicting source bytes')
        merged[d]=b;provenance.setdefault(d,[]).append({'artifact_path':str(p.relative_to(root)), 'sha256':h,'rows':n})
    expected=expected if expected is not None else read_calendar()
    missing=sorted(set(expected)-set(merged));extra=sorted(set(merged)-set(expected))
    summary={'status':'RAW_2006_COMPLETE' if not missing and not extra else 'RAW_2006_INCOMPLETE',
             'expected_exchange_days':len(expected),'observed_unique_daily_files':len(merged),
             'missing_dates':missing,'extra_dates':extra,'raw_daily_rows':sum(items[0]['rows'] for items in provenance.values()),
             'PIT_CERTIFIED':False,'FORMAL_MODEL_ALLOWED':False,
             'warning':'Source internal hashes and calendar only; issuer listing episodes, suspension and adjustment are not PIT certified',
             'IPO_exception':{'date':'20060619','symbol':'002051.SZ','return_pct':332.03,
                              'source_sha256':SPECIAL_SHA,'scope':'RAW_ARCHIVE_ONLY'}}
    out=Path(out);out.parent.mkdir(parents=True,exist_ok=True)
    (out.parent/'v85_2006_archive_gate.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    if missing or extra:raise ValueError('Raw archive incomplete; '+json.dumps({'missing':missing,'extra':extra}))
    manifest={'file_sha256':{d:hashlib.sha256(b).hexdigest() for d,b in sorted(merged.items())},
              'source_provenance':provenance,'independent_calendar_sha256':CAL_SHA,
              'PIT_CERTIFIED':False,'FORMAL_MODEL_ALLOWED':False}
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for d,b in sorted(merged.items()):z.writestr(f'raw/{d}.csv',b)
        z.writestr('source_manifest_2006.json',json.dumps(manifest,ensure_ascii=False,indent=2))
        z.writestr('README_DATA_QUALITY.txt','2006 raw source internally validated. 241 trading days. PIT NOT CERTIFIED. IPO 002051 2006-06-19 special price verified via exchange and contemporaneous market report.\n')
    with zipfile.ZipFile(out) as z:
        assert z.testzip() is None
        assert len([n for n in z.namelist() if n.startswith('raw/')])==241
    return summary


def main():
    p=argparse.ArgumentParser();p.add_argument('--input-dir',required=True);p.add_argument('--output',required=True)
    x=p.parse_args();print(json.dumps(archive(x.input_dir,x.output),ensure_ascii=False))

if __name__=='__main__':main()
