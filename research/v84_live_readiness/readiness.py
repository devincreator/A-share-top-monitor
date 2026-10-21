#!/usr/bin/env python3
"""Read-only daily readiness audit. This script NEVER emits a trading alert."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

ISO = '%Y-%m-%d'


def parse_date(value):
    return dt.datetime.strptime(value, ISO).date()


def read(path):
    raw = Path(path).read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def build_report(state, market, *, today, state_sha='', market_sha=''):
    today = parse_date(today) if isinstance(today, str) else today
    model_day = parse_date(market['model_date'])
    market_day = parse_date(market['market_date'])
    price_day = parse_date(state['asof'])
    future = [kind for kind, day in [('model', model_day), ('market', market_day), ('price', price_day)] if day > today]
    if future:
        raise ValueError('source date is in the future: ' + ','.join(future))
    if model_day > market_day:
        raise ValueError('model_date > market_date')
    if state.get('data_status') != 'price_core_verified_partial':
        raise ValueError('unexpected price core status; manual source review required')
    complete = market.get('complete_model_recalculated') is True
    same_day_full = complete and model_day == today
    channels = {
        'price_core': {'asof': price_day.isoformat(), 'calendar_age_days': (today-price_day).days,
                       'status': 'HISTORICAL_VERIFIED_ONLY'},
        'market_snapshot': {'asof': market_day.isoformat(), 'calendar_age_days': (today-market_day).days,
                            'status': 'HISTORICAL_SNAPSHOT_ONLY'},
        'full_four_module_model': {'asof': model_day.isoformat(), 'calendar_age_days': (today-model_day).days,
                                   'status': 'READY' if same_day_full else 'STALE_OR_UNVERIFIED'},
    }
    return {
        'schema_version': 1,
        'audit_date': today.isoformat(),
        'status': 'FORMAL_INPUTS_READY_FOR_SEPARATE_SIGNAL_ENGINE' if same_day_full else 'DATA_PENDING',
        'is_new_formal_signal': False,
        'explanation': 'Data availability only. No new 5%/9% formal alert is computed here.',
        'channels': channels,
        'input_sha256': {'latest_state.json': state_sha, 'latest_verified_market.json': market_sha},
        'last_archived_top5': state.get('latest_formal_signals', {}).get('top5'),
        'last_archived_top9': state.get('latest_formal_signals', {}).get('top9'),
        'warnings': [
            'Archived signals are not current trading instructions.',
            'Calendar age is not trading-day age.',
            'Full model requires independently verified price, volume, turnover, financing and frozen rules.',
        ],
    }


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--state', default='data/latest_state.json')
    p.add_argument('--market', default='data/latest_verified_market.json')
    p.add_argument('--today', default=dt.datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat())
    p.add_argument('--output', default='research/status/v84_daily_readiness.json')
    args = p.parse_args(argv)
    state, state_sha = read(args.state)
    market, market_sha = read(args.market)
    report = build_report(state, market, today=args.today, state_sha=state_sha, market_sha=market_sha)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf8')
    print(json.dumps({'status': report['status'], 'audit_date': report['audit_date'],
                      'channels': report['channels'], 'output': str(output)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
