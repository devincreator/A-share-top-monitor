import importlib.util
import json
import tempfile
import unittest
from datetime import datetime,timezone
from pathlib import Path

SOURCE=Path(__file__).with_name("probe_recent.py")
spec=importlib.util.spec_from_file_location("v88_probe_recent",SOURCE)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def good(day, sha="demo-checksum"):
    return ({"status":"RAW_DAILY_INTEGRITY_PASS","source_url":"https://example.org/"+day,
             "sha256":sha,"source_rows":101,"unique_sh_sz_traded_bars":100,
             "positive_raw_pct_chg_count":55,"observed_traded_advance_share":.55},b"evidence")

class DateAwareTests(unittest.TestCase):
    def test_prior_date_stamped_not_falsely_current(self):
        calls=[]
        def fetch(d):
            calls.append(d)
            return good(d) if d=="20261020" else ({"status":"DATA_UNAVAILABLE","error":"HTTP 404"},None)
        with tempfile.TemporaryDirectory() as tmp:
            o=Path(tmp)
            r=m.run_recent("2026-10-21",fetch=fetch,output_dir=o/"run",ledger_dir=o/"ledger",
                           now_utc=datetime(2026,10,21,tzinfo=timezone.utc))
            self.assertEqual(calls,["20261021","20261020"])
            self.assertEqual(r["status"],"RAW_OBSERVED_RESEARCH_ONLY")
            self.assertEqual(r["latest_observed_date"],"2026-10-20")
            self.assertEqual(r["calendar_age_days"],1)
            self.assertFalse(r["formal_signal_allowed"])
            self.assertTrue((o/"ledger/2026-10-20.json").exists())

    def test_unavailable_does_not_create_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            o=Path(tmp)
            r=m.run_recent("2026-10-21",fetch=lambda d:({"status":"DATA_UNAVAILABLE"},None),
                           output_dir=o/"run",ledger_dir=o/"ledger")
            self.assertEqual(r["status"],"DATA_UNAVAILABLE")
            self.assertEqual(r["latest_observed_date"],None)
            self.assertFalse((o/"ledger").exists())

    def test_identical_revisit_does_not_mutate_initial_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            o=Path(tmp)
            params=dict(fetch=lambda d:good(d),output_dir=o/"run",ledger_dir=o/"ledger")
            first=m.run_recent("2026-10-20",now_utc=datetime(2026,10,21,tzinfo=timezone.utc),**params)
            before=(o/"ledger/2026-10-20.json").read_bytes()
            second=m.run_recent("2026-10-20",now_utc=datetime(2026,10,22,tzinfo=timezone.utc),**params)
            self.assertEqual(second["ledger_status"],"EXISTING_UNCHANGED")
            self.assertEqual(before,(o/"ledger/2026-10-20.json").read_bytes())

    def test_revision_is_flagged_without_overwriting(self):
        with tempfile.TemporaryDirectory() as tmp:
            o=Path(tmp)
            m.run_recent("2026-10-20",fetch=lambda d:good(d,"A"),output_dir=o/"run",ledger_dir=o/"ledger")
            r=m.run_recent("2026-10-20",fetch=lambda d:good(d,"B"),output_dir=o/"run",ledger_dir=o/"ledger")
            self.assertEqual(r["ledger_status"],"CONFLICT_WITH_FIRST_OBSERVATION")
            self.assertEqual(json.loads((o/"ledger/2026-10-20.json").read_text())["source_raw_sha256"],"A")

    def test_weekend_not_imputed_as_trading(self):
        days=m.recent_weekdays("2026-10-26",max_calendar_lookback=4)
        self.assertEqual(days,["20261026","20261023","20261022"])

if __name__=="__main__":
    unittest.main()
