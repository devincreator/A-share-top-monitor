import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from rolling_v113_breadth import per_stock_features
class Tests(unittest.TestCase):
 def make(self,n):
  return [{"date":"2026-%02d-%02d"%(1+(i//25),1+i%25),
           "status":"TRADING","close":str(i+1),"high":str(i+1),"low":str(i+1)} for i in range(n)]
 def test_asof_mean_requires_20_observations(self):
  values=list(per_stock_features(self.make(20)))
  self.assertNotIn("ma_20_eligible",values[18][1])
  self.assertEqual(values[19][1]["above_ma_20"],1)
 def test_suspend_does_not_backfill(self):
  rows=self.make(19)+[{"date":"2026-01-20","status":"SUSPENDED"}]+[{"date":"2026-01-21","status":"TRADING","close":"20","high":"20","low":"20"}]
  out=list(per_stock_features(rows))
  self.assertEqual(out[-2][1],{"suspended":1})
  self.assertEqual(out[-1][1]["ma_20_eligible"],1)
 def test_high252_cannot_use_future(self):
  vals=list(per_stock_features(self.make(252)))
  self.assertNotIn("new_high_252",vals[250][1])
  self.assertEqual(vals[251][1]["new_high_252"],1)
if __name__=="__main__":unittest.main()
