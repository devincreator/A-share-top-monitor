import hashlib
import importlib.util
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('v103', Path(__file__).with_name('first_capture.py'))
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)


def official_bytes(n=160, *, wrong_index=False, add_today=False, weekend=False, stale=False):
    last = date(2026, 10, 20) if stale else date(2026, 10, 21)
    dates = []
    d = last
    while len(dates) < n:
        if d.weekday() < 5:
            dates.append(d)
        d -= timedelta(days=1)
    rows = [{'indexCode': '000300' if wrong_index else '000985',
             'tradeDate': d.strftime('%Y%m%d'), 'close': str(5000 + i)}
            for i, d in enumerate(reversed(dates))]
    if weekend:
        rows.append({'indexCode': '000985', 'tradeDate': '20261017', 'close': '5001'})
    if add_today:
        rows.append({'indexCode': '000985', 'tradeDate': '20261022', 'close': '5500'})
    return json.dumps({'data': rows}).encode()


def clock(h, m, s=0):
    return datetime(2026, 10, 22, h-8, m, s, tzinfo=timezone.utc)


def do_capture(raw, *, start=None, end=None, fetch=None):
    times = iter([start or clock(9, 10), end or clock(9, 11)])
    return v.capture(now=lambda: next(times),
                     fetch=fetch or (lambda _: (raw, {'http_status': 200})))


class ForwardEvidenceTests(unittest.TestCase):
    def test_valid_preopen_is_only_source_observation(self):
        raw = official_bytes()
        record, data = do_capture(raw)
        self.assertEqual(record['status'], 'PASS_PREOPEN_RAW_SOURCE_OBSERVED_RESEARCH_ONLY')
        self.assertEqual(record['observed_last_trade_date'], '2026-10-21')
        self.assertEqual(record['raw_sha256'], hashlib.sha256(raw).hexdigest())
        self.assertTrue(record['source_available_before_decision_cutoff_observed'])
        for field in ('formal_signal_allowed', 'forward_prediction_generated',
                      'actual_source_original_publication_time_known',
                      'independent_trading_calendar_certified', 'blind_performance_evaluated'):
            self.assertIs(record[field], False, field)
        self.assertEqual(data, raw)

    def test_late_response_does_not_claim_preopen(self):
        r, raw = do_capture(official_bytes(), end=clock(9, 20, 1))
        self.assertEqual(r['reason'], 'RESPONSE_AFTER_PREOPEN_CUTOFF')
        self.assertFalse(r['source_available_before_decision_cutoff_observed'])
        self.assertIsNotNone(raw)

    def test_early_or_late_start_never_fetches(self):
        for t in (clock(8, 59), clock(9, 20)):
            r, raw = v.capture(now=lambda: t,
                fetch=lambda _: self.fail('fetch must not run outside window'))
            self.assertEqual(r['reason'], 'OUTSIDE_09_00_TO_09_20_CAPTURE_WINDOW')
            self.assertIsNone(raw)

    def test_same_day_or_wrong_index_or_stale_or_insufficient_blocks(self):
        for raw in (official_bytes(add_today=True), official_bytes(wrong_index=True),
                    official_bytes(stale=True), official_bytes(n=126)):
            r, preserved = do_capture(raw)
            self.assertEqual(r['status'], 'BLOCKED')
            self.assertEqual(r['reason'], 'SOURCE_SCHEMA_OR_LOOKBACK_BLOCKED')
            self.assertEqual(preserved, raw)

    def test_weekend_anomaly_is_quarantined(self):
        r, _ = do_capture(official_bytes(weekend=True))
        self.assertEqual(r['status'], 'PASS_PREOPEN_RAW_SOURCE_OBSERVED_RESEARCH_ONLY')
        self.assertEqual(r['source_weekend_dates_quarantined'], ['2026-10-17'])

    def test_failed_network_is_blocked_and_timestamped(self):
        times = iter([clock(9, 10), clock(9, 11)])
        def bad(_):
            raise TimeoutError('no source')
        r, raw = v.capture(now=lambda: next(times), fetch=bad)
        self.assertEqual(r['reason'], 'SOURCE_FETCH_FAILED')
        self.assertIn('TimeoutError', r['error'])
        self.assertIsNone(raw)

    def test_raw_first_capture_immutable(self):
        record, raw = do_capture(official_bytes())
        with tempfile.TemporaryDirectory() as td:
            first = v.archive_once(record, raw, td)
            path = Path(td)/'2026-10-22'/'first_capture.json'
            rawpath = path.with_name('official_index_raw.json')
            old_manifest = path.read_bytes()
            old_raw = rawpath.read_bytes()
            altered = dict(record)
            altered['status'] = 'BLOCKED'
            second = v.archive_once(altered, b'different', td)
            self.assertEqual(first['archive_status'], 'FIRST_CAPTURE_PERSISTED')
            self.assertEqual(second['archive_status'], 'EXISTING_FIRST_CAPTURE_LEFT_UNCHANGED')
            self.assertEqual(path.read_bytes(), old_manifest)
            self.assertEqual(rawpath.read_bytes(), old_raw)

    def test_archive_refuses_hash_mismatch(self):
        record, _ = do_capture(official_bytes())
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                v.archive_once(record, b'corrupt', td)

    def test_monday_requires_friday_and_no_decision_day_data(self):
        self.assertEqual(v.prev_weekday(date(2026, 10, 26)), date(2026, 10, 23))
        self.assertEqual(v.prev_weekday(date(2026, 10, 22)), date(2026, 10, 21))


if __name__ == '__main__':
    unittest.main()
