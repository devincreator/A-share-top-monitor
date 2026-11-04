import unittest,random,json,importlib.util
from pathlib import Path
from decimal import Decimal
P=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('seven',P/'evaluate_baseline.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

class ScoringTests(unittest.TestCase):
 def test_day_zero_and_eighth_rejected_first_and_seventh_accepted(self):
  dates=[str(i) for i in range(15)];pos={d:i for i,d in enumerate(dates)};aa=[{'id':'a','date':'2'}]
  for delta,expected in [(0,0),(1,1),(7,1),(8,0)]:
   pp=[{'id':'p','date':str(2+delta)}]
   self.assertEqual(len(m.independent.independent_max_match(aa,pp,pos,7)),expected)
 def test_duplicate_alerts_do_not_reuse_pivot(self):
  pos={str(i):i for i in range(12)};aa=[{'id':'a1','date':'1'},{'id':'a2','date':'2'}];pp=[{'id':'p','date':'4'}]
  mapped=m.independent.independent_max_match(aa,pp,pos,7);self.assertEqual(len(mapped),1);self.assertEqual(len({p['id'] for p in mapped.values()}),1)
 def test_maximum_count_against_exhaustive_search(self):
  rng=random.Random(7);pos={f'{i:02d}':i for i in range(16)}
  def brute(aa,pp,i=0,seen=frozenset()):
   if i==len(aa):return 0
   best=brute(aa,pp,i+1,seen)
   for j,p in enumerate(pp):
    if j not in seen and 1<=pos[p['date']]-pos[aa[i]['date']]<=7:best=max(best,1+brute(aa,pp,i+1,seen|{j}))
   return best
  for _ in range(250):
   aa=[{'id':f'a{i:02d}','date':f'{i:02d}'} for i in sorted(rng.sample(range(16),rng.randrange(6)))];pp=[{'id':f'p{i:02d}','date':f'{i:02d}'} for i in sorted(rng.sample(range(16),rng.randrange(6)))]
   self.assertEqual(len(m.independent.independent_max_match(aa,pp,pos,7)),brute(aa,pp))
 def test_prediction_unchanged_when_decision_day_and_future_prices_change(self):
  xs=[Decimal(100)+Decimal(i)/10 for i in range(300)];changed=xs[:];changed[200:]=[Decimal('0.001')]*100
  for r in m.base.RULES.values():self.assertEqual(m.base.feature_at(xs,199,r),m.base.feature_at(changed,199,r))
 def test_real_event_accounting_and_no_false_success(self):
  r=m.evaluate();self.assertFalse(r['double80_achieved']);self.assertFalse(r['source_asof_publication_verified']);self.assertFalse(r['sample_is_unseen'])
  for task,v in r['task_metrics'].items():
   self.assertEqual(v['TP']+v['FN'],v['mature_pivots']);self.assertEqual(v['TP']+v['FP']+v['PENDING']+v['EXCLUDED_LEFT_CENSORED'],v['all_formal_start_alerts'])
if __name__=='__main__':unittest.main()
