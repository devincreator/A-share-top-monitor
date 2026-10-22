#!/usr/bin/env python3
"""Research-only forward source evidence, not a trading model.

A successful record means the collector received direct official-source bytes
before D 09:20 Asia/Shanghai. It does NOT certify the publisher's original
release time, a Chinese trading calendar, or an investable signal.
"""
import argparse
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

ZONE = ZoneInfo('Asia/Shanghai')
START = time(9, 0)
CUTOFF = time(9, 20)
CODE = '000985'
INDEX = '000985.CSI'
MIN_PRICE_SESSIONS = 127
BASE_URL = 'https://www.csindex.com.cn/csindex-home/perf/index-perf'
DEFAULT_LEDGER = Path('research/v103_forward_preopen/observations')


def utc_stamp(value):
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('naive timestamp forbidden')
    return value.astimezone(timezone.utc).isoformat(timespec='microseconds')


def prev_weekday(d):
    x = d - timedelta(days=1)
    while x.weekday() >= 5:
        x -= timedelta(days=1)
    return x


def source_url(decision):
    begin = decision - timedelta(days=310)
    end = decision - timedelta(days=1)
    return BASE_URL + '?' + urllib.parse.urlencode({
        'indexCode': CODE,
        'startDate': begin.strftime('%Y%m%d'),
        'endDate': end.strftime('%Y%m%d')})


def fetch_official(url):
    request = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (research-only first-observation)',
        'Referer': 'https://www.csindex.com.cn/',
        'Accept': 'application/json'})
    with urllib.request.urlopen(request, timeout=12) as response:
        if response.status != 200:
            raise ValueError('non-200 official HTTP response')
        raw = response.read(4_000_001)
        if len(raw) > 4_000_000:
            raise ValueError('bounded official raw response exceeded')
        # Redirects to an unrelated origin, even with JSON-shaped bytes,
        # are not direct evidence from the intended CSI provider.
        effective_url = response.geturl()
        parsed_origin = urllib.parse.urlsplit(effective_url)
        if parsed_origin.scheme != 'https' or parsed_origin.hostname != 'www.csindex.com.cn':
            raise ValueError('source redirected outside original HTTPS publisher')
        return raw, {
            'http_status': response.status,
            'http_date': response.headers.get('Date'),
            'http_last_modified': response.headers.get('Last-Modified'),
            'http_content_type': response.headers.get('Content-Type'),
            'effective_source_url': effective_url}


def parse_official(raw, decision):
    try:
        doc = json.loads(raw.decode('utf-8-sig'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError('invalid official JSON') from exc
    if not isinstance(doc, dict) or not isinstance(doc.get('data'), list):
        raise ValueError('official data array missing')
    seen = set()
    prices = []
    weekend = []
    for row in doc['data']:
        if not isinstance(row, dict) or str(row.get('indexCode')) != CODE:
            raise ValueError('official index identity missing or inconsistent')
        ds = str(row.get('tradeDate', ''))
        if len(ds) != 8 or not ds.isdigit():
            raise ValueError('official tradeDate format invalid')
        d = date(int(ds[:4]), int(ds[4:6]), int(ds[6:]))
        if d in seen:
            raise ValueError('duplicate official date')
        seen.add(d)
        if d >= decision:
            raise ValueError('future or decision-day price in preopen response')
        try:
            close = Decimal(str(row['close']))
        except (KeyError, InvalidOperation, TypeError) as exc:
            raise ValueError('invalid official close') from exc
        if not close.is_finite() or close <= 0:
            raise ValueError('nonpositive or nonfinite official close')
        if d.weekday() >= 5:
            weekend.append(d.isoformat())
        else:
            prices.append((d, close))
    prices.sort()
    if len(prices) < MIN_PRICE_SESSIONS:
        raise ValueError('insufficient direct-source lookback: ' + str(len(prices)))
    if prices[-1][0] != prev_weekday(decision):
        raise ValueError('latest source day not immediately previous weekday: ' + prices[-1][0].isoformat())
    return {
        'observed_last_trade_date': prices[-1][0].isoformat(),
        'observed_last_close': str(prices[-1][1]),
        'source_weekday_rows': len(prices),
        'source_weekend_dates_quarantined': weekend,
        'min_lookback_127_available': True,
        'last_127_closes_sha256': hashlib.sha256(
            ''.join(f'{d.isoformat()},{c}\n' for d, c in prices[-MIN_PRICE_SESSIONS:]).encode()
        ).hexdigest()}


def capture(*, now=lambda: datetime.now(timezone.utc), fetch=fetch_official):
    started = now()
    if started.tzinfo is None or started.utcoffset() is None:
        raise ValueError('unaware system clock')
    local = started.astimezone(ZONE)
    d = local.date()
    record = {
        'schema': 'V103_FIRST_OBSERVED_DIRECT_SOURCE_V1',
        'decision_date': d.isoformat(),
        'decision_cutoff_local': f'{d.isoformat()}T09:20:00+08:00',
        'request_started_at_utc': utc_stamp(started),
        'source_url': source_url(d),
        'source_name': 'CSI official index-perf direct HTTPS',
        'index': INDEX,
        'status': 'BLOCKED',
        'reason': None,
        'research_only': True,
        'formal_signal_allowed': False,
        'production_updated': False,
        'forward_prediction_generated': False,
        'historical_publisher_release_timestamp_certified': False,
        'actual_source_original_publication_time_known': False,
        'independent_trading_calendar_certified': False,
        'source_available_before_decision_cutoff_observed': False,
        'blind_performance_evaluated': False}
    if local.weekday() >= 5:
        record['reason'] = 'NON_WEEKDAY'
        return record, None
    if not (START <= local.time().replace(tzinfo=None) < CUTOFF):
        record['reason'] = 'OUTSIDE_09_00_TO_09_20_CAPTURE_WINDOW'
        return record, None
    try:
        raw, headers = fetch(record['source_url'])
        completed = now()
        record['response_completed_at_utc'] = utc_stamp(completed)
        record['http_response_headers'] = headers
        record['raw_sha256'] = hashlib.sha256(raw).hexdigest()
        record['raw_bytes'] = len(raw)
    except Exception as exc:
        record['reason'] = 'SOURCE_FETCH_FAILED'
        record['error'] = f'{type(exc).__name__}: {str(exc)[:200]}'
        record['response_completed_at_utc'] = utc_stamp(now())
        return record, None
    ended_local = completed.astimezone(ZONE)
    # Reject clocks that move backwards or a forged second timestamp. Such
    # evidence cannot prove an entire source request finished after it began.
    if completed.astimezone(timezone.utc) < started.astimezone(timezone.utc):
        record['reason'] = 'INVALID_NON_MONOTONIC_CAPTURE_CLOCK'
        return record, raw
    record['request_duration_seconds'] = (
        completed.astimezone(timezone.utc) - started.astimezone(timezone.utc)
    ).total_seconds()
    if ended_local.date() != d or not (START <= ended_local.time().replace(tzinfo=None) < CUTOFF):
        record['reason'] = 'RESPONSE_AFTER_PREOPEN_CUTOFF'
        return record, raw
    try:
        record.update(parse_official(raw, d))
    except Exception as exc:
        record['reason'] = 'SOURCE_SCHEMA_OR_LOOKBACK_BLOCKED'
        record['error'] = f'{type(exc).__name__}: {str(exc)[:200]}'
        return record, raw
    record['status'] = 'PASS_PREOPEN_RAW_SOURCE_OBSERVED_RESEARCH_ONLY'
    record['reason'] = 'SOURCE_BYTES_OBSERVED_BY_CUTOFF_BUT_ORIGINAL_PUBLISH_TIME_AND_CALENDAR_NOT_CERTIFIED'
    record['source_available_before_decision_cutoff_observed'] = True
    record['first_observed_at_utc'] = utc_stamp(completed)
    return record, raw


def verify_first_capture(manifest, source):
    """Verify previously persisted evidence before reporting it as existing.

    A corrupt/missing raw or an orphaned source is a hard failure, never a
    silent 'already exists' success. Does not attempt retroactive repairs.
    """
    manifest = Path(manifest)
    source = Path(source)
    if not manifest.is_file():
        if source.exists():
            raise ValueError('ORPHANED_FIRST_CAPTURE_SOURCE_MISSING_MANIFEST')
        raise ValueError('first capture manifest missing')
    try:
        first = json.loads(manifest.read_bytes().decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError('INVALID_PREEXISTING_CAPTURE_MANIFEST') from exc
    if not isinstance(first, dict):
        raise ValueError('INVALID_PREEXISTING_CAPTURE_MANIFEST')
    d = first.get('decision_date')
    try:
        if date.fromisoformat(d).isoformat() != d or manifest.parent.name != d:
            raise ValueError('first capture decision path mismatch')
    except (TypeError, ValueError) as exc:
        raise ValueError('first capture decision path mismatch') from exc
    declared = first.get('raw_sha256')
    if declared is not None:
        if not isinstance(declared, str) or len(declared) != 64:
            raise ValueError('invalid preexisting raw SHA256')
        if not source.is_file():
            raise ValueError('RAW_EVIDENCE_MISSING_FOR_FIRST_CAPTURE')
        if hashlib.sha256(source.read_bytes()).hexdigest() != declared:
            raise ValueError('RAW_EVIDENCE_TAMPERED_OR_TRUNCATED')
    elif source.exists():
        raise ValueError('UNDECLARED_RAW_EVIDENCE_IN_FIRST_CAPTURE')
    if first.get('status') == 'PASS_PREOPEN_RAW_SOURCE_OBSERVED_RESEARCH_ONLY':
        if not declared or not first.get('source_available_before_decision_cutoff_observed'):
            raise ValueError('first capture falsely claims eligible source')
        # Independently revalidate the recorded first-observed clock, rather
        # than merely trusting a PASS label in the JSON. Never retroactively
        # promote an old BLOCKED record to PASS.
        try:
            began = datetime.fromisoformat(first['request_started_at_utc'])
            ended = datetime.fromisoformat(first['response_completed_at_utc'])
            if began.utcoffset() is None or ended.utcoffset() is None:
                raise ValueError('naive first-observation time')
            local_start = began.astimezone(ZONE)
            local_end = ended.astimezone(ZONE)
            if (local_start.date().isoformat() != d
                    or local_end.date().isoformat() != d
                    or not (START <= local_start.time().replace(tzinfo=None) < CUTOFF)
                    or not (START <= local_end.time().replace(tzinfo=None) < CUTOFF)
                    or ended.astimezone(timezone.utc) < began.astimezone(timezone.utc)
                    or first.get('first_observed_at_utc') != utc_stamp(ended)):
                raise ValueError('first-observation clock does not prove preopen source')
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError('INVALID_STORED_FIRST_OBSERVATION_CLOCK') from exc
        # SHA-preserved data must also reproduce all fields that were claimed
        # in its original manifest. This is useful for second-run self audits.
        try:
            parsed = parse_official(source.read_bytes(), date.fromisoformat(d))
            for key in ('observed_last_trade_date', 'observed_last_close',
                        'source_weekday_rows', 'source_weekend_dates_quarantined',
                        'min_lookback_127_available', 'last_127_closes_sha256'):
                if first.get(key) != parsed[key]:
                    raise ValueError('stored source claim differs from original raw bytes: '+key)
        except (ValueError, TypeError, KeyError) as exc:
            raise ValueError('INVALID_STORED_SOURCE_CLAIMS') from exc
    elif first.get('source_available_before_decision_cutoff_observed') is not False:
        raise ValueError('nonpass record cannot claim preopen source verified')
    return {'decision_date': d,
            'status': first.get('status'),
            'manifest_sha256': hashlib.sha256(manifest.read_bytes()).hexdigest(),
            'raw_sha256': declared}


def archive_once(record, raw, ledger):
    try:
        decision_date = record['decision_date']
        if date.fromisoformat(decision_date).isoformat() != decision_date:
            raise ValueError('invalid decision date')
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError('invalid decision date for first capture') from exc
    target = Path(ledger) / decision_date
    manifest = target / 'first_capture.json'
    source = target / 'official_index_raw.json'
    if manifest.exists() or source.exists():
        existing = verify_first_capture(manifest, source)
        if existing['decision_date'] != decision_date:
            raise ValueError('first capture target date changed')
        return {'archive_status': 'EXISTING_FIRST_CAPTURE_VERIFIED_UNCHANGED',
                'new_capture_discarded': True, **existing}

    if record.get('status') == 'PASS_PREOPEN_RAW_SOURCE_OBSERVED_RESEARCH_ONLY' and raw is None:
        raise ValueError('PASS declared without original source bytes')
    if raw is not None:
        if hashlib.sha256(raw).hexdigest() != record.get('raw_sha256'):
            raise ValueError('source raw sha mismatch before first capture')
    elif record.get('raw_sha256') is not None:
        raise ValueError('source raw sha declared without raw bytes')
    target.mkdir(parents=True, exist_ok=True)
    if raw is not None:
        with source.open('xb') as f:
            f.write(raw)
    payload = (json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()
    # Manifest is the final durable commit marker, written ONLY after the
    # complete byte-for-byte raw payload has been placed on disk.
    with manifest.open('xb') as f:
        f.write(payload)
    return {'archive_status': 'FIRST_CAPTURE_PERSISTED',
            'decision_date': decision_date,
            'status': record['status'], 'reason': record['reason'],
            'manifest_sha256': hashlib.sha256(payload).hexdigest(),
            'raw_sha256': record.get('raw_sha256'), 'formal_signal_allowed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ledger', default=str(DEFAULT_LEDGER))
    args = parser.parse_args()
    result, raw = capture()
    saved = archive_once(result, raw, args.ledger)
    print(json.dumps(saved, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
