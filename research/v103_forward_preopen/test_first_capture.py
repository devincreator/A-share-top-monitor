import hashlib
import importlib.util
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest
from unittest import mock

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
            self.assertEqual(second['archive_status'], 'EXISTING_FIRST_CAPTURE_VERIFIED_UNCHANGED')
            self.assertEqual(path.read_bytes(), old_manifest)
            self.assertEqual(rawpath.read_bytes(), old_raw)

    def test_archive_refuses_hash_mismatch(self):
        record, _ = do_capture(official_bytes())
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                v.archive_once(record, b'corrupt', td)

    def test_backward_wall_clock_cannot_claim_preopen_pass(self):
        record, raw = do_capture(official_bytes(), start=clock(9, 12), end=clock(9, 11))
        self.assertEqual(record['status'], 'BLOCKED')
        self.assertEqual(record['reason'], 'INVALID_NON_MONOTONIC_CAPTURE_CLOCK')
        self.assertFalse(record['source_available_before_decision_cutoff_observed'])
        self.assertEqual(raw, official_bytes())

    def test_positive_capture_duration_is_recorded(self):
        record, _ = do_capture(official_bytes(), start=clock(9, 10), end=clock(9, 11, 4))
        self.assertEqual(record['request_duration_seconds'], 64.0)

    def test_existing_archive_is_sha_checked_before_declaring_unchanged(self):
        record, raw = do_capture(official_bytes())
        with tempfile.TemporaryDirectory() as td:
            v.archive_once(record, raw, td)
            p = Path(td)/record['decision_date']/'official_index_raw.json'
            p.write_bytes(b'corrupt')
            with self.assertRaisesRegex(ValueError, 'RAW_EVIDENCE_TAMPERED'):
                v.archive_once(record, raw, td)

    def test_missing_source_cannot_be_silent_existing_capture(self):
        record, raw = do_capture(official_bytes())
        with tempfile.TemporaryDirectory() as td:
            v.archive_once(record, raw, td)
            p = Path(td)/record['decision_date']/'official_index_raw.json'
            p.unlink()
            with self.assertRaisesRegex(ValueError, 'RAW_EVIDENCE_MISSING'):
                v.archive_once(record, raw, td)

    def test_orphan_source_after_interrupted_write_stays_blocked(self):
        record, raw = do_capture(official_bytes())
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)/record['decision_date']
            folder.mkdir()
            (folder/'official_index_raw.json').write_bytes(raw)
            with self.assertRaisesRegex(ValueError, 'ORPHANED_FIRST_CAPTURE'):
                v.archive_once(record, raw, td)
            self.assertFalse((folder/'first_capture.json').exists())

    def test_corrupt_existing_manifest_blocks_reuse(self):
        record, raw = do_capture(official_bytes())
        with tempfile.TemporaryDirectory() as td:
            v.archive_once(record, raw, td)
            p = Path(td)/record['decision_date']/'first_capture.json'
            p.write_text('NOT JSON')
            with self.assertRaisesRegex(ValueError, 'INVALID_PREEXISTING_CAPTURE_MANIFEST'):
                v.archive_once(record, raw, td)

    def test_pass_without_raw_source_or_declared_sha_refused(self):
        record, raw = do_capture(official_bytes())
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError, 'PASS declared without original'):
                v.archive_once(record, None, td)
            tampered = dict(record)
            tampered.pop('raw_sha256')
            with self.assertRaisesRegex(ValueError, 'source raw sha mismatch'):
                v.archive_once(tampered, raw, td)

    def test_invalid_archive_date_path_is_not_accepted(self):
        record, raw = do_capture(official_bytes())
        for invalid in ('../../other', '2026-10-22/../../../other', '2026-10-22x'):
            bogus = dict(record, decision_date=invalid)
            with tempfile.TemporaryDirectory() as td:
                with self.assertRaisesRegex(ValueError, 'invalid decision date'):
                    v.archive_once(bogus, raw, td)

    def test_source_cannot_redirect_to_unrelated_origin(self):
        class FakeResponse:
            status = 200
            headers = {'Date': 'Thu, 22 Oct 2026 01:11:00 GMT'}
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def geturl(self): return 'https://third-party.invalid/faked-csi'
            def read(self, n): return official_bytes()
        with mock.patch.object(v.urllib.request, 'urlopen', return_value=FakeResponse()):
            with self.assertRaisesRegex(ValueError, 'redirected outside'):
                v.fetch_official(v.source_url(date(2026,10,22)))

    def test_invalid_duplicate_and_nonfinite_official_rows_rejected(self):
        import json as _json
        valid = _json.loads(official_bytes())
        duplicates = dict(valid, data=valid['data']+[dict(valid['data'][0])])
        nonfinite = _json.loads(official_bytes())
        nonfinite['data'][-1]['close'] = 'NaN'
        for bad in (duplicates, nonfinite):
            record, raw = do_capture(_json.dumps(bad).encode())
            self.assertEqual(record['status'], 'BLOCKED')
            self.assertEqual(record['reason'], 'SOURCE_SCHEMA_OR_LOOKBACK_BLOCKED')

    def test_reused_manifest_with_forged_early_clock_cannot_pass(self):
        record, raw = do_capture(official_bytes())
        with tempfile.TemporaryDirectory() as td:
            v.archive_once(record, raw, td)
            p = Path(td)/record['decision_date']/'first_capture.json'
            wrong = json.loads(p.read_text())
            wrong['request_started_at_utc'] = '2026-10-22T01:24:00.000000+00:00'
            p.write_text(json.dumps(wrong))
            with self.assertRaisesRegex(ValueError, 'INVALID_STORED_FIRST_OBSERVATION_CLOCK'):
                v.verify_first_capture(p, p.with_name('official_index_raw.json'))

    def test_reused_manifest_with_forged_recorded_close_cannot_pass(self):
        record, raw = do_capture(official_bytes())
        with tempfile.TemporaryDirectory() as td:
            v.archive_once(record, raw, td)
            p = Path(td)/record['decision_date']/'first_capture.json'
            wrong = json.loads(p.read_text())
            wrong['observed_last_close'] = '12345678'
            p.write_text(json.dumps(wrong))
            with self.assertRaisesRegex(ValueError, 'INVALID_STORED_SOURCE_CLAIMS'):
                v.archive_once(record, raw, td)

    def test_reused_manifest_source_clock_sha_and_parse_are_all_consistent(self):
        record, raw = do_capture(official_bytes())
        with tempfile.TemporaryDirectory() as td:
            v.archive_once(record, raw, td)
            p = Path(td)/record['decision_date']/'first_capture.json'
            verified = v.verify_first_capture(p, p.with_name('official_index_raw.json'))
            self.assertEqual(verified['decision_date'], record['decision_date'])
            self.assertEqual(verified['raw_sha256'], record['raw_sha256'])
            self.assertEqual(verified['status'], 'PASS_PREOPEN_RAW_SOURCE_OBSERVED_RESEARCH_ONLY')

    def test_monday_requires_friday_and_no_decision_day_data(self):
        self.assertEqual(v.prev_weekday(date(2026, 10, 26)), date(2026, 10, 23))
        self.assertEqual(v.prev_weekday(date(2026, 10, 22)), date(2026, 10, 21))


if __name__ == '__main__':
    unittest.main()
