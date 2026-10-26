import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from audit_shsz_pit_lag import decide
class TestHistoricalPIT(unittest.TestCase):
 def test_next_session_bars_only(self):
  r=decide(["2026-09-29","2026-09-30","2026-10-08"])
  self.assertEqual(r[1]["decision_date"],"2026-10-08")
  self.assertEqual(r[1]["latest_allowed_bar_date"],"2026-09-30")
  self.assertFalse(r[1]["historical_actual_publish_time_verified"])
 def test_calendar_duplicate_reject(self):
  with self.assertRaisesRegex(ValueError,"NON_MONOTONIC"):
   decide(["2026-10-08","2026-10-08"])
 def test_nontrading_gap_not_future(self):
  r=decide(["2026-09-30","2026-10-08"])
  self.assertTrue(r[0]["time_check_pass"])
if __name__=="__main__":unittest.main()
