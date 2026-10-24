import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from accept_v113_full import build
class Tests(unittest.TestCase):
 def get(self):
  sh={"x":{"up":"1","down":"2","flat":"3","suspended":"1","unresolved":"0",
       "expected_listed_shsz":"7","security_days_with_status":"7"}}
  bj={"x":{"bj_up":"2","bj_down":"3","bj_flat":"4","bj_unknown_not_traded":"1",
       "bj_expected_listed":"10","bj_trading_bars":"9"}}
  return sh,bj
 def test_unknown_beijing_does_not_pass(self):
  a,b=self.get();daily,report=build(a,b,["x"])
  self.assertEqual(daily[0]["status"],"PARTIAL_UNKNOWN")
  self.assertEqual(report["status"],"PARTIAL")
  self.assertFalse(report["checks"]["beijing_suspension_vs_flat_certified"])
 def test_market_counts_add(self):
  a,b=self.get();daily,_=build(a,b,["x"])
  self.assertEqual([daily[0][x] for x in ("market_up","market_down","market_flat")],[3,5,7])
 def test_negative_gap_reject(self):
  a,b=self.get();b["x"]["bj_unknown_not_traded"]="-1"
  with self.assertRaisesRegex(ValueError,"NEGATIVE_GAP"):build(a,b,["x"])
 def test_missing_date_not_imputed(self):
  a,b=self.get();daily,_=build(a,b,["x","y"])
  self.assertEqual(daily[1]["status"],"SOURCE_MISSING")
 def test_other_dates_fail(self):
  a,b=self.get()
  with self.assertRaisesRegex(ValueError,"UNEXPECTED_DATE"):build(a,b,["y"])
if __name__=="__main__":unittest.main()
