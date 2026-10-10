#!/usr/bin/env python3
"""BSE daily financing balance archive with complete date-level audit. No strategy code."""
import json,os,time,random
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import pandas as pd
import akshare as ak

O=Path('out');O.mkdir(exist_ok=True)
START="2023-01-01";END="2026-10-08"
MIN_DATE="2023-01-01"
MAX_JOBS=2
def date_calendar():
    f=ak.stock_zh_index_daily_tx(symbol='sh000300',start_date=START.replace('-',''),end_date=END.replace('-',''))
    f['date']=pd.to_datetime(f.date).dt.strftime('%Y%m%d')
    days=sorted(set(f.date))
    if not 850<=len(days)<=1000:raise RuntimeError("unexpected trading day count "+str(len(days)))
    return days
def fetch(date):
    err=None
    for retry in range(3):
        try:
            f=ak.stock_margin_bse(date=date)
            if f is None or len(f)!=1: raise ValueError("not exactly one BSE summary row")
            c=f.iloc[0]
            raw=float(c['融资余额'])
            if not 0<raw<2e6:raise ValueError(f"invalid BSE balance in 10k yuan: {raw}")
            return {'date':f'{date[:4]}-{date[4:6]}-{date[6:]}','balance_bse_yuan':round(raw*10000,2),'source':'BSE','retry':retry}
        except Exception as e:
            err=f'{type(e).__name__}: {str(e)[:180]}'
            time.sleep(0.8*(retry+1))
    return {'date':f'{date[:4]}-{date[4:6]}-{date[6:]}','error':err}
def dump(rows):
    df=pd.DataFrame([r for r in rows if 'balance_bse_yuan' in r]).drop_duplicates('date').sort_values('date')
    df.to_csv(O/'bse_financing_history.csv',index=False)
    return len(df)
audit={'start':START,'end':END,'unit':'CNY yuan','status':'INCOMPLETE','error_count':None,'total_dates':None,'examples':[]}
rows=[]
try:
    days=date_calendar()
    audit['total_dates']=len(days)
    # For exchange capacity limits, submit only two concurrent requests; preserve 100% date accountability.
    with ThreadPoolExecutor(max_workers=MAX_JOBS) as pool:
        futures=[pool.submit(fetch,d) for d in days]
        for i,future in enumerate(as_completed(futures),1):
            rows.append(future.result())
            if i%50==0:
                good=dump(rows)
                print(json.dumps({'progress':i,'total':len(days),'successful':good,'failed':i-good}),flush=True)
    good=dump(rows)
    missing=[x for x in rows if 'error' in x]
    audit['success_dates']=good
    audit['error_count']=len(missing)
    audit['examples']=missing[:25]
    audit['status']='COMPLETE' if not missing and good==len(days) else 'INCOMPLETE'
except Exception as e:
    audit['fatal']=f'{type(e).__name__}: {str(e)[:260]}'
    dump(rows)
finally:
    (O/'bse_financing_full_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(audit,ensure_ascii=False),flush=True)
