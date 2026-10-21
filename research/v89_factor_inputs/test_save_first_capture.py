import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

P=Path(__file__).with_name("save_first_capture.py")
spec=importlib.util.spec_from_file_location("save_first_capture",P)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def report():
    return {"date":"2026-10-20","index":"000985.CSI","close":5306.57,
            "ret5_pct":-3.36,"ret63_pct":-12.65,
            "rv_ratio_percentile_prior756":30.82,
            "ret63_percentile_prior756":1.98,
            "candidate_input_sha256":"sha256demo",
            "cross_provider_status":"RESEARCH_PRICE_AMOUNT_CROSS_PROVIDER_PASS",
            "formal_signal_allowed":False}

class ResearchLedgerTests(unittest.TestCase):
    def test_first_capture_immutable(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d);r=report()
            a=m.archive_first_capture(r,path,timestamp="2026-10-21T01:00:00Z")
            self.assertEqual(a["status"],"FIRST_CAPTURE_PERSISTED")
            raw=(path/"2026-10-20.json").read_bytes()
            a=m.archive_first_capture(r,path,timestamp="2026-10-21T05:00:00Z")
            self.assertEqual(a["status"],"UNCHANGED")
            self.assertEqual((path/"2026-10-20.json").read_bytes(),raw)
            self.assertFalse(json.loads(raw)["formal_signal_allowed"])

    def test_revision_never_overwrites(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d);r=report()
            m.archive_first_capture(r,path)
            raw=(path/"2026-10-20.json").read_bytes()
            r["close"]=2
            a=m.archive_first_capture(r,path,audit_dir=path/"audit")
            self.assertEqual(a["status"],"SOURCE_REVISION_CONFLICT")
            self.assertEqual((path/"2026-10-20.json").read_bytes(),raw)
            self.assertTrue((path/"audit/revision_conflict.json").exists())

    def test_missing_validation_must_not_commit(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d);r=report()
            r["formal_signal_allowed"]=True
            self.assertEqual(m.archive_first_capture(r,path)["status"],"BLOCKED_NOT_RESEARCH_ONLY")
            self.assertFalse((path/'2026-10-20.json').exists())

if __name__=="__main__":
    unittest.main()
