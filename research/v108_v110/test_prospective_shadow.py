import sys
from pathlib import Path
import json
import tempfile
import unittest
from datetime import datetime, timezone
sys.path.insert(0,str(Path(__file__).parent))
from prospective_shadow import write_once,build_record

class ProspectiveShadowTests(unittest.TestCase):
    def test_never_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"2026-10-23"/"shadow.json"
            write_once({"status":"UNSCORED_PENDING_FUTURE_OUTCOME"},p)
            with self.assertRaises(FileExistsError):
                write_once({"status":"UNSCORED_PENDING_FUTURE_OUTCOME"},p)
    def test_missing_source_cannot_forge(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"2026-10-23"
            with self.assertRaises(ValueError):
                build_record(p/"first_capture.json",p/"official_index_raw.json",
                  now=datetime(2026,10,23,1,12,tzinfo=timezone.utc))
    def test_record_cannot_be_generated_from_blocked_source(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"2026-10-23"
            p.mkdir()
            (p/"first_capture.json").write_text(json.dumps({
                "decision_date":"2026-10-23","status":"BLOCKED",
                "source_available_before_decision_cutoff_observed":False}))
            with self.assertRaisesRegex(ValueError,"SOURCE_GATE_BLOCKED"):
                build_record(p/"first_capture.json",p/"official_index_raw.json",
                  now=datetime(2026,10,23,1,12,tzinfo=timezone.utc))
if __name__=="__main__":unittest.main()
