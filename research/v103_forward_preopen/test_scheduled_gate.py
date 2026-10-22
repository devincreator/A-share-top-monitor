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
    def test_fake_pass_without_raw(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"2026-10-23"
            p.mkdir()
            (p/"first_capture.json").write_text(json.dumps({"decision_date":"2026-10-23","status":g.PASS,"source_available_before_decision_cutoff_observed":True}))
            self.assertFalse(g.check(td,"2026-10-23")[0])

if __name__ == "__main__":
    unittest.main()
