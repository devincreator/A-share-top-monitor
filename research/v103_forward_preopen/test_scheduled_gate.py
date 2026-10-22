import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

root = Path(__file__).parent
spec = importlib.util.spec_from_file_location("v103_gate", root/"scheduled_gate.py")
import sys
sys.path.insert(0, str(root))
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)

class ScheduledGateTests(unittest.TestCase):
    def test_missing(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(g.check(td,"2026-10-23"),(False,"MISSING_MANIFEST"))
    def test_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"2026-10-23"
            p.mkdir()
            (p/"first_capture.json").write_text(json.dumps({"decision_date":"2026-10-23","status":"BLOCKED","reason":"SOURCE_FETCH_FAILED","source_available_before_decision_cutoff_observed":False}))
            self.assertEqual(g.check(td,"2026-10-23"),(False,"SOURCE_FETCH_FAILED"))
    def test_corrupt(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"2026-10-23"
            p.mkdir()
            (p/"first_capture.json").write_text("{broken")
            self.assertFalse(g.check(td,"2026-10-23")[0])
    def test_wrong_day(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"2026-10-23"
            p.mkdir()
            (p/"first_capture.json").write_text(json.dumps({"decision_date":"2026-10-22"}))
            self.assertEqual(g.check(td,"2026-10-23"),(False,"DATE_MISMATCH"))
    def test_realistic_pass_with_valid_immutable_archive(self):
        from datetime import date, datetime, timedelta, timezone
        from first_capture import archive_once, capture
        latest = date(2026, 10, 22)
        days = []
        d = latest
        while len(days) < 160:
            if d.weekday() < 5:
                days.append(d)
            d -= timedelta(days=1)
        rows = [{"indexCode": "000985", "tradeDate": x.strftime("%Y%m%d"), "close": "5000"}
                for x in reversed(days)]
        raw = json.dumps({"data": rows}).encode()
        stamps = iter([datetime(2026,10,23,1,10,tzinfo=timezone.utc),
                       datetime(2026,10,23,1,11,tzinfo=timezone.utc)])
        record, returned = capture(now=lambda: next(stamps),
                                   fetch=lambda url: (raw, {"http_status": 200}))
        self.assertEqual(record["status"], g.PASS)
        with tempfile.TemporaryDirectory() as td:
            archive_once(record, returned, td)
            self.assertEqual(g.check(td,"2026-10-23"),(True,"PASS_RESEARCH_ONLY"))
            original = Path(td)/"2026-10-23"/"official_index_raw.json"
            original.write_bytes(b"tampered")
            self.assertFalse(g.check(td,"2026-10-23")[0])

    def test_fake_pass_without_raw(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"2026-10-23"
            p.mkdir()
            (p/"first_capture.json").write_text(json.dumps({"decision_date":"2026-10-23","status":g.PASS,"source_available_before_decision_cutoff_observed":True}))
            self.assertFalse(g.check(td,"2026-10-23")[0])

if __name__ == "__main__":
    unittest.main()
