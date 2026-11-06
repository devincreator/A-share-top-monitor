import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from reconcile_shsz_dated_membership import reclassify_day
class Tests(unittest.TestCase):
 def base(self):
  return {"date":"2026-10-19","expected_listed_shsz":"5226","security_days_with_status":"5224",
    "unresolved":"2","up":"3000","down":"2200","flat":"16","suspended":"8"}
 def test_two_exited_stocks_reduce_population_no_false_bars(self):
  b=self.base()
  r=reclassify_day(b,[{"status":"NOT_IN_HISTORICAL_LIST"},{"status":"NOT_IN_HISTORICAL_LIST"}])
  self.assertEqual(r["fully_reconciled"],1)
  self.assertEqual(r["expected_shsz_in_dated_membership"],5224)
  self.assertEqual(r["up"],3000)
 def test_verified_suspensions_not_flat(self):
  b=self.base()
  r=reclassify_day(b,[{"status":"0"},{"status":"NOT_IN_HISTORICAL_LIST"}])
  self.assertEqual(r["suspended"],9)
  self.assertEqual(r["flat"],16)
  self.assertEqual(r["fully_reconciled"],1)
 def test_missing_traded_bar_cannot_qualify(self):
  b=self.base()
  r=reclassify_day(b,[{"status":"1"},{"status":"NOT_IN_HISTORICAL_LIST"}])
  self.assertEqual(r["fully_reconciled"],0)
  self.assertEqual(r["unresolved"],1)
if __name__=="__main__":unittest.main()
