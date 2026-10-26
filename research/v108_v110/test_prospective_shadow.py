import sys
from pathlib import Path
import json
import tempfile
import unittest
from datetime import datetime, timezone
sys.path.insert(0,str(Path(__file__).parent))
from prospective_shadow import write_once,build_record,signal_from_raw

class ProspectiveShadowTests(unittest.TestCase):
    def test_only_past_raw_rows_used(self):
        from datetime import date,timedelta
        days=[]
        d=date(2026,10,22)
        while len(days)<130:
            if d.weekday()<5: days.append(d)
            d-=timedelta(days=1)
        days.reverse()
        rows=[{"indexCode":"000985","tradeDate":x.strftime("%Y%m%d"),"close":str(4000+i)}
              for i,x in enumerate(days)]
        raw=json.dumps({"data":rows}).encode()
        state=signal_from_raw(raw,date(2026,10,23))
        self.assertEqual(state["state"],"UPTREND")
        rows.append({"indexCode":"000985","tradeDate":"20261023","close":"999999"})
        self.assertEqual(state,signal_from_raw(json.dumps({"data":rows}).encode(),date(2026,10,23)))
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
