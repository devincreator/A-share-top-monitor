#!/usr/bin/env python3
"""One-to-one retrospective event matching; no model training or live alerts.

Input CSVs: alerts(date,scale,direction,id), pivots(date,scale,direction,id),
           prices(date,close). Dates YYYY-MM-DD, scales 5/9, directions TOP/BOTTOM.
Historical objective pivot labels MAY use hindsight. Regime feature uses only
price observations STRICTLY BEFORE the alert date (pre-open clock).
"""
import argparse
import csv
import json
from collections import Counter
from datetime import date
from pathlib import Path


def load_csv(path, required):
    with open(path, newline='', encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    if any(not set(required).issubset(r) or any(not r.get(k) for k in required) for r in rows):
        raise ValueError(f'{path}: missing required CSV fields {required}')
    return rows


def normalize_events(rows, label):
    out = []
    seen_ids = set()
    for r in rows:
        if r['scale'] not in ('5', '9') or r['direction'] not in ('TOP', 'BOTTOM'):
            raise ValueError(f'{label}: unexpected scale/direction')
        stamp = date.fromisoformat(r['date'])
        uid = r['id']
        if uid in seen_ids:
            raise ValueError(f'{label}: duplicated event id: {uid}')
        seen_ids.add(uid)
        out.append({'date': stamp, 'scale': r['scale'], 'direction': r['direction'], 'id': uid})
    return sorted(out, key=lambda x: (x['date'], x['id']))


def classify_at_alert(event, dates, closes):
    """Past-only 60/120 trading-observation regime; descriptive, not optimized."""
    day = event['date']
    if day not in dates:
        return 'NO_PRICE_ON_ALERT_DATE'
    idx = dates.index(day)
    # The prediction is issued before today's regular trading session.
    # Therefore not even the prediction day's CLOSE can be a past feature.
    end = idx - 1
    if end < 120:
        return 'INSUFFICIENT_PAST'
    r60 = closes[end] / closes[end - 60] - 1
    r120 = closes[end] / closes[end - 120] - 1
    if r60 < -0.10 and r120 < 0:
        return 'DOWNTREND_RALLY_RISK'
    if r60 > 0.10 and r120 > 0:
        return 'UPTREND'
    return 'MIXED_OR_RANGE'


def audit(alerts, pivots, price_rows):
    """Maximum cardinality bipartite matches by time-window; deterministic."""
    alerts = normalize_events(alerts, 'alerts')
    pivots = normalize_events(pivots, 'pivots')
    price_days = [date.fromisoformat(r['date']) for r in price_rows]
    close = [float(r['close']) for r in price_rows]
    if price_days != sorted(set(price_days)) or any(x <= 0 for x in close):
        raise ValueError('prices must be ascending unique dates with positive closes')
    pos = {d: i for i, d in enumerate(price_days)}
    if any(e['date'] not in pos for e in alerts + pivots):
        raise ValueError('all event dates must exist in price observation calendar')
    by_task = {}
    for scale in ('5', '9'):
        for direction in ('TOP', 'BOTTOM'):
            key = f'{scale}_{direction}'
            aa = [a for a in alerts if a['scale'] == scale and a['direction'] == direction]
            pp = [p for p in pivots if p['scale'] == scale and p['direction'] == direction]
            limit = 10 if scale == '5' else 20
            candidates = []
            for a in aa:
                poss = [(pos[p['date']] - pos[a['date']], j)
                        for j,p in enumerate(pp)
                        if 1 <= pos[p['date']] - pos[a['date']] <= limit]
                candidates.append([j for lead,j in sorted(poss)])
            matched_pivot_to_alert = {}
            def augment(ai, seen):
                for pj in candidates[ai]:
                    if pj in seen:
                        continue
                    seen.add(pj)
                    if pj not in matched_pivot_to_alert or augment(matched_pivot_to_alert[pj], seen):
                        matched_pivot_to_alert[pj] = ai
                        return True
                return False
            for i in range(len(aa)):
                augment(i, set())
            a_to_p = {ai: pj for pj,ai in matched_pivot_to_alert.items()}
            results = []
            for i,a in enumerate(aa):
                pj = a_to_p.get(i)
                regime = classify_at_alert(a,price_days,close)
                results.append({'alert_id': a['id'], 'alert_date': a['date'].isoformat(),
                                'result': 'TP' if pj is not None else 'FP',
                                'market_regime_at_alert': regime,
                                'pivot_id': pp[pj]['id'] if pj is not None else None,
                                'lead_trading_days': pos[pp[pj]['date']] - pos[a['date']] if pj is not None else None})
            tp = len(a_to_p)
            fp = len(aa) - tp
            fn = len(pp) - tp
            leads = [x['lead_trading_days'] for x in results if x['lead_trading_days'] is not None]
            by_task[key] = {'tp': tp, 'fp': fp, 'fn': fn, 'formal_alerts':len(aa),
                            'mature_pivots': len(pp),
                            'precision': round(tp / len(aa), 6) if aa else None,
                            'recall': round(tp / len(pp), 6) if pp else None,
                            'mean_lead_trading_days': round(sum(leads)/len(leads), 4) if leads else None,
                            'false_positive_regimes': dict(Counter(x['market_regime_at_alert'] for x in results if x['result']=='FP')),
                            'events': results}
    return {'schema_version':1, 'evaluation': 'RESEARCH_ONLY',
            'matching':'one formal alert per objective mature pivot, 1-10/1-20 trading days',
            'warning':'Hindsight labels are for retrospective evaluation only; they are not live features.',
            'tasks':by_task}


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('--alerts',required=True)
    parser.add_argument('--pivots',required=True)
    parser.add_argument('--prices',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args(argv)
    result=audit(load_csv(args.alerts, ('date','scale','direction','id')),
                 load_csv(args.pivots, ('date','scale','direction','id')),
                 load_csv(args.prices, ('date','close')))
    dest=Path(args.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:{field:v[field] for field in ('tp','fp','fn','precision','recall')} for k,v in result['tasks'].items()}))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
