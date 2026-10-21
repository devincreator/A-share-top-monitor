#!/usr/bin/env python3
"""V101 fresh START, frozen and untuned, PRICE ONLY.

Backtesting uses retrospective 000985 closes with a day-D preopen information
CUTOFF at the previous indexed observation. DOES NOT certify that the historical
D-1 close was actually published by D 09:20; source originally archived 2026.

This is a scientific counterfactual clock experiment, not production alerts or
new out-of-sample results. The objective pivots are ex-post labels only.
"""
import argparse
import csv
from datetime import date
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path

FROZEN_PRICE_SHA='f18bb93b38e6648fbd72bad53dc7fa06333cd63a01858063e1dfa50b14e7fc41'
FROZEN_PIVOTS_SHA='39648f066b515c6ddc5b5853f9d1f691e3439fa04393a81e36b4c19e649262b1'
SCHEMA_VERSION=1
MATURITY_BUFFER=140
CLOCK='09:20:00+08:00'
INDEX_ID='000985.CSI'
RULES={
    '5_TOP': {'window':63,'momentum':20,'limit':'0.90','minimum_momentum':'0.015','cooldown':10,'lead':10,'direction':'TOP','scale':'5'},
    '5_BOTTOM': {'window':63,'momentum':20,'limit':'0.10','minimum_momentum':'0.015','cooldown':10,'lead':10,'direction':'BOTTOM','scale':'5'},
    '9_TOP': {'window':126,'momentum':60,'limit':'0.95','minimum_momentum':'0.055','cooldown':20,'lead':20,'direction':'TOP','scale':'9'},
    '9_BOTTOM': {'window':126,'momentum':60,'limit':'0.05','minimum_momentum':'0.055','cooldown':20,'lead':20,'direction':'BOTTOM','scale':'9'},
}

def sha(data):return hashlib.sha256(data).hexdigest()

def read_source(raw,expected,columns):
    if sha(raw)!=expected:
        raise ValueError('frozen source SHA256 mismatch')
    import io
    reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
    if not set(columns).issubset(reader.fieldnames or []):
        raise ValueError('missing source columns')
    rows=list(reader)
    return rows

def load_sources(price_path,pivots_path):
    rawp=Path(price_path).read_bytes();rawv=Path(pivots_path).read_bytes()
    rows=read_source(rawp,FROZEN_PRICE_SHA,['date','close'])
    pivots=read_source(rawv,FROZEN_PIVOTS_SHA,['id','date','scale','direction','confirmation_date','first_segment_left_censored'])
    dates=[date.fromisoformat(r['date']) for r in rows]
    closes=[Decimal(r['close']) for r in rows]
    if len(rows)!=1128 or dates[0].isoformat()!='2022-02-23' or dates[-1].isoformat()!='2026-10-20':
        raise ValueError('frozen 000985 price window not available')
    if any(dates[i]<=dates[i-1] for i in range(1,len(dates))):
        raise ValueError('non-monotone dates')
    if any(not c.is_finite() or c<=0 for c in closes):
        raise ValueError('bad price values')
    if len(pivots)!=58 or any(p['scale'] not in ('5','9') for p in pivots):
        raise ValueError('frozen objective labels unexpected')
    n={d:i for i,d in enumerate(dates)}
    for p in pivots:
        a=date.fromisoformat(p['date']);b=date.fromisoformat(p['confirmation_date'])
        if a not in n or b not in n or n[b]<=n[a]:raise ValueError('pivot or confirmation outside price window')
    return dates,closes,pivots,{'price_sha256':sha(rawp),'pivots_sha256':sha(rawv)}

def feature_at(closes,asof,rule):
    """asof is index of LAST OBSERVED price, never the decision D index."""
    window=rule['window'];mom=rule['momentum']
    if asof<max(window-1,mom):return None
    current=closes[asof]
    look=closes[asof-window+1:asof+1]
    lo=min(look);hi=max(look)
    position=(current-lo)/(hi-lo) if hi>lo else Decimal('0.5')
    momentum=current/closes[asof-mom]-1
    eligible=(position>=Decimal(rule['limit']) and momentum>=Decimal(rule['minimum_momentum'])
              if rule['direction']=='TOP' else
              position<=Decimal(rule['limit']) and momentum<=-Decimal(rule['minimum_momentum']))
    return {'position':position,'momentum':momentum,'eligible':eligible,
            'min_close':lo,'max_close':hi,'last_close':current,
            'max_source_price_index':asof}

def generate_alerts(dates,closes):
    """Fresh event on eligible FALSE -> TRUE; shared time-symmetric rules frozen."""
    if len(dates)!=len(closes):raise ValueError('date/price size mismatch')
    all_rows=[]
    by_task={k:[] for k in RULES}
    for task,rule in RULES.items():
        last_signal=-100000
        previously_eligible=False
        for di in range(1,len(dates)):
            asof=di-1
            feat=feature_at(closes,asof,rule)
            eligible=feat is not None and feat['eligible']
            edge=eligible and not previously_eligible
            if edge and (di-last_signal)>rule['cooldown']:
                d=dates[di].isoformat();observed=dates[asof].isoformat()
                event={
                    'id':f'V101_{task}_{d}', 'event_type':'FORMAL_START',
                    'task':task,'scale':rule['scale'],'direction':rule['direction'],
                    'date':d, 'decision_at':f'{d}T{CLOCK}',
                    'last_price_observation_date':observed,
                    'last_price_observation_index':asof,
                    'decision_price_index':di,
                    'candidate_historical_release_assumption':'D_MINUS_1_PRICE_AVAILABLE_BY_D_0920_NOT_VERIFIED',
                    'position_rolling_close':str(feat['position']),
                    'momentum_prior_close':str(feat['momentum']),
                    'latest_source_close':str(feat['last_close']),
                    'window_sessions':rule['window'],
                    'momentum_sessions':rule['momentum'],
                    'min_momentum_threshold':rule['minimum_momentum'],
                    'position_threshold':rule['limit'],
                    'rule_status':'FROZEN_UNTUNED_PRICE_ONLY_BASELINE',
                }
                by_task[task].append(event);all_rows.append(event)
                last_signal=di
            previously_eligible=bool(eligible)
    all_rows.sort(key=lambda e:(e['date'],e['task'],e['id']))
    return all_rows,by_task

def match_chronological(alerts,pivots,positions,lead):
    """Greedy earliest eligible for equal-length lead windows; max cardinality."""
    found={};j=0
    for a in sorted(alerts,key=lambda x:(x['date'],x['id'])):
        da=positions[date.fromisoformat(a['date'])]
        while j<len(pivots) and positions[date.fromisoformat(pivots[j]['date'])]<=da:j+=1
        if j<len(pivots):
            gap=positions[date.fromisoformat(pivots[j]['date'])]-da
            if 1<=gap<=lead:
                found[a['id']]=pivots[j];j+=1
    return found

def event_replay(alerts,pivots,dates):
    positions={d:i for i,d in enumerate(dates)};n=len(dates)
    details=[];summaries={}
    for task,rule in RULES.items():
        these=sorted([a for a in alerts if a['task']==task],key=lambda x:(x['date'],x['id']))
        pp=sorted([p for p in pivots if p['scale']==rule['scale'] and p['direction']==rule['direction']],key=lambda x:(x['date'],x['id']))
        left=[p for p in pp if p['first_segment_left_censored'].lower()=='true']
        candidates=[p for p in pp if p not in left]
        mature=[p for p in candidates if positions[date.fromisoformat(p['confirmation_date'])]+MATURITY_BUFFER<n]
        immature=[p for p in candidates if p not in mature]
        mapped=match_chronological(these,mature,positions,rule['lead'])
        cases={'TP':0,'FP':0,'PENDING':0,'EXCLUDED_LEFT_CENSORED':0}
        for a in these:
            i=positions[date.fromisoformat(a['date'])];p=mapped.get(a['id'])
            if p:status='TP'
            elif any(1<=positions[date.fromisoformat(x['date'])]-i<=rule['lead'] for x in left):status='EXCLUDED_LEFT_CENSORED'
            elif any(1<=positions[date.fromisoformat(x['date'])]-i<=rule['lead'] for x in immature):status='PENDING'
            elif i+rule['lead']+MATURITY_BUFFER<n:status='FP'
            else:status='PENDING'
            cases[status]+=1
            details.append({**a,'event_result':status,
                            'matched_pivot_id':p['id'] if p else '',
                            'matched_pivot_date':p['date'] if p else '',
                            'lead_trading_sessions':positions[date.fromisoformat(p['date'])]-i if p else '',
                            'label_only_used_after_forecast':True})
        tp=cases['TP'];fp=cases['FP'];fn=len(mature)-tp
        summaries[task]={
            'generated_formal_starts':len(these),'tp':tp,'fp':fp,'fn':fn,
            'pending':cases['PENDING'],'excluded_alerts_left_boundary':cases['EXCLUDED_LEFT_CENSORED'],
            'mature_pivots':len(mature),'excluded_pivots_left_boundary':len(left),
            'immature_pivots':len(immature),
            'precision':tp/(tp+fp) if tp+fp else None,
            'recall':tp/len(mature) if mature else None,
            'goal_precision_ge_0_8':(tp/(tp+fp)>=0.8 if tp+fp else None),
            'goal_recall_ge_0_8':(tp/len(mature)>=0.8 if mature else None),
        }
    details.sort(key=lambda e:(e['date'],e['task'],e['id']))
    if len(details)!=len(alerts):raise AssertionError('replay altered event count')
    return details,summaries

def produce(price_path,pivot_path):
    dates,closes,pivots,source=load_sources(price_path,pivot_path)
    alerts,_=generate_alerts(dates,closes)
    details,summaries=event_replay(alerts,pivots,dates)
    metrics={
       'experiment':'V101_FRESH_UNTUNED_PREOPEN_PRICE_ONLY_BENCHMARK',
       'index':INDEX_ID,'schema_version':SCHEMA_VERSION,
       'frozen_original_source':source,
       'source_dates':{'first':dates[0].isoformat(),'last':dates[-1].isoformat(),'trading_sessions':len(dates)},
       'last_decision_day':dates[-1].isoformat(),
       'prediction_time':'09:20 Asia/Shanghai',
       'max_feature_observation_index_offset':-1,
       'candidate_publication_clock':'Previous official-trading-day close assumed available before next day 09:20; actual historical release times NOT independently certified',
       'historical_PIT_certified':False,
       'source_originally_captured_at_forecast_date':False,
       'label_truth':'2026-10-20 ex-post frozen 5/9% alternating close-reversal labels used for scoring only',
       'pre_registered_without_optimizing_against_labels':True,
       'older_V63_V68_FORMAL_START_required':False,
       'old_V63_V68_summary_used_for_selection':False,
       'sample_out_of_sample':False,
       'research_only':True,
       'formal_signal_allowed':False,
       'production_updated':False,
       'maturity_buffer_after_pivot_confirmation_sessions':MATURITY_BUFFER,
       'rules':RULES,
       'task_metrics':summaries,
       'all_four_tasks_precision_and_recall_ge_0_8':all(
         s['goal_precision_ge_0_8'] is True and s['goal_recall_ge_0_8'] is True
         for s in summaries.values()),
       'warning':'Retrospective, repeatedly studied data; no authentic historical publication-time proof or true prospective event predictions. No trading or production recommendations.'
    }
    return alerts,details,metrics

def csv_content(rows,fields):
    import io
    buf=io.StringIO(newline='');writer=csv.DictWriter(buf,fieldnames=fields,lineterminator='\n')
    writer.writeheader();writer.writerows(rows)
    return buf.getvalue().encode('utf-8')

def write_once(path,payload):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        if path.read_bytes()!=payload:raise ValueError(f'refusing to overwrite first capture {path}')
        return
    path.write_bytes(payload)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--prices',default='research/v97_event_intake/observations/index_000985_prices_20220223_20261020.csv')
    parser.add_argument('--pivots',default='research/v97_event_intake/observations/partial_v52_derived_objective_pivots.csv')
    parser.add_argument('--out-dir',default='research/v101_fresh_start/observations')
    args=parser.parse_args()
    signals,events,report=produce(args.prices,args.pivots)
    report['signals_count']=len(signals)
    report['event_rows_sha256']=sha(csv_content(events,list(events[0]) if events else []))
    root=Path(args.out_dir)
    write_once(root/'fresh_formal_start_events.csv',csv_content(signals,list(signals[0]) if signals else []))
    write_once(root/'matched_or_pending_event_audit.csv',csv_content(events,list(events[0]) if events else []))
    write_once(root/'frozen_baseline_report.json',(json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode())
    print(json.dumps({'source_sessions':1128,'generated_signals':len(signals),'task_metrics':report['task_metrics'],'formal_signal_allowed':False},ensure_ascii=False))

if __name__=='__main__':main()
