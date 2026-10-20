#!/usr/bin/env python3
"""One chunk of five VERIFIED-MISSING 2006 days. Store raw, not PIT model inputs."""
import argparse
import json
import time
from pathlib import Path
from pilot_2006_repair import fetch, DAYS as PILOT_DAYS

ROOT=Path(__file__).resolve().parent
LIST=ROOT/'missing_2006_remaining.json'


def select_batch(group):
    dates=json.loads(LIST.read_text(encoding='utf8'))
    if len(dates)!=85 or dates != sorted(set(dates)) or set(dates).intersection(PILOT_DAYS):
        raise ValueError('missing-day input manifest is not exactly 85 new dates')
    if group not in range(1,18):
        raise ValueError('group outside 1..17')
    return dates[(group-1)*5:group*5]


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--group',type=int,required=True)
    args=p.parse_args(argv)
    days=select_batch(args.group)
    root=Path('v85_2006_bulk')/f'batch_{args.group:02d}'
    raw=root/'raw';raw.mkdir(parents=True,exist_ok=True)
    results=[]
    for day in days:
        b,item=fetch(day)
        if b is not None:
            (raw/(day+'.csv')).write_bytes(b)
        results.append(item)
        print(json.dumps(item),flush=True)
        time.sleep(3)
    report={'group':args.group,'expected_days':days,
            'received':sum(x['status']=='RAW_DAILY_INTEGRITY_PASS' for x in results),
            'records':results,'PIT_CERTIFIED':False,'FORMAL_MODEL_ALLOWED':False}
    (root/'gate.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    if report['received']!=5:
        raise SystemExit('Batch incomplete; resume only missing dates, do not mark complete')

if __name__=='__main__':main()
