import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from baostock_shard import validate_one, listed_on_session
class Tests(unittest.TestCase):
 def test_suspend_never_flat(self):
  c,_=validate_one("sh.600000",[{"date":"2026-09-21","code":"sh.600000","tradestatus":"0"}],[])
  self.assertEqual(c["suspended"],1);self.assertEqual(c["flat"],0)
 def test_up_down_flat(self):
  def entry(d,close,prev):
   return {"date":d,"code":"sh.600000","tradestatus":"1","close":close,
          "preclose":prev,"amount":"12","volume":"100"}
  c,_=validate_one("sh.600000",[entry("2026-09-21","11","10"),
      entry("2026-09-22","10","11"),entry("2026-09-23","10","10")],[])
  self.assertEqual([c["up"],c["down"],c["flat"]],[1,1,1])
 def test_duplicate_blocks(self):
  with self.assertRaisesRegex(ValueError,"DUPLICATE_STOCK_DATE"):
   validate_one("sh.600000",[{"date":"2026-09-21","code":"sh.600000","tradestatus":"0"}]*2,[])
 def test_wrong_code_blocks(self):
  with self.assertRaisesRegex(ValueError,"WRONG_SECURITY_CODE"):
   validate_one("sh.600000",[{"date":"2026-09-21","code":"sz.000001","tradestatus":"0"}],[])
if __name__=="__main__":unittest.main()
