import sys
from pathlib import Path
import unittest
from decimal import Decimal

HERE=Path(__file__).parent
ROOT=HERE.parent/'v97_event_intake'/'observations'
sys.path.insert(0,str(HERE))
import fresh_preopen_baseline as m

class FrozenFreshBaseline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dates,cls.closes,cls.pivots,cls.provenance=m.load_sources(
            ROOT/'index_000985_prices_20220223_20261020.csv',
            ROOT/'partial_v52_derived_objective_pivots.csv')

    def test_real_source_sha_and_labels(self):
        self.assertEqual(self.provenance['price_sha256'],m.FROZEN_PRICE_SHA)
        self.assertEqual(self.provenance['pivots_sha256'],m.FROZEN_PIVOTS_SHA)
        self.assertEqual(len(self.pivots),58)
        self.assertEqual(len(self.dates),1128)

    def test_no_D_or_future_values_in_any_generated_signal(self):
        alerts,_=m.generate_alerts(self.dates,self.closes)
        idx={d.isoformat():i for i,d in enumerate(self.dates)}
        for row in alerts:
            decision_idx=idx[row['date']]
            self.assertEqual(row['last_price_observation_index'],decision_idx-1)
            self.assertEqual(row['last_price_observation_date'],
                             self.dates[decision_idx-1].isoformat())
            self.assertEqual(row['decision_at'],row['date']+'T09:20:00+08:00')
            self.assertLess(row['last_price_observation_index'],
                            row['decision_price_index'])
            self.assertNotIn('matched_pivot_id',row)

    def test_change_D_close_cannot_change_D_preopen_signal(self):
        i=500
        changed=list(self.closes)
        changed[i]=Decimal('99999999')
        first=[(x['date'],x['task']) for x in m.generate_alerts(self.dates,self.closes)[0]
               if x['date']==self.dates[i].isoformat()]
        second=[(x['date'],x['task']) for x in m.generate_alerts(self.dates,changed)[0]
                if x['date']==self.dates[i].isoformat()]
        self.assertEqual(first,second)

    def test_cannot_peek_beyond_asof_index(self):
        i=220
        first=m.feature_at(self.closes,i,m.RULES['5_TOP'])
        changed=list(self.closes)
        changed[i+1:]=[Decimal('99')]*len(changed[i+1:])
        self.assertEqual(first,m.feature_at(changed,i,m.RULES['5_TOP']))

    def test_one_formal_start_per_task_per_day(self):
        alerts,_=m.generate_alerts(self.dates,self.closes)
        pairs=[(x['date'],x['task']) for x in alerts]
        self.assertEqual(len(pairs),len(set(pairs)))

    def test_real_frozen_baseline_not_80_percent(self):
        alerts,rows,report=m.produce(
            ROOT/'index_000985_prices_20220223_20261020.csv',
            ROOT/'partial_v52_derived_objective_pivots.csv')
        self.assertEqual(len(alerts),59)
        self.assertEqual(len(rows),59)
        self.assertFalse(report['historical_PIT_certified'])
        self.assertFalse(report['formal_signal_allowed'])
        self.assertFalse(report['sample_out_of_sample'])
        self.assertFalse(report['all_four_tasks_precision_and_recall_ge_0_8'])
        expected={'5_TOP':(21,8,11,8,2,16),
                  '5_BOTTOM':(22,6,12,10,4,16),
                  '9_TOP':(10,2,7,5,1,7),
                  '9_BOTTOM':(6,2,2,5,2,7)}
        for task,(n,tp,fp,fn,pending,mature) in expected.items():
            row=report['task_metrics'][task]
            self.assertEqual((row['generated_formal_starts'],row['tp'],
                              row['fp'],row['fn'],row['pending'],row['mature_pivots']),
                             (n,tp,fp,fn,pending,mature))
            self.assertEqual(tp+fp+pending+row['excluded_alerts_left_boundary'],n)
            self.assertEqual(fn,mature-tp)

    def test_changed_raw_SHA_blocks(self):
        raw=(ROOT/'index_000985_prices_20220223_20261020.csv').read_bytes()
        with self.assertRaisesRegex(ValueError,'SHA256 mismatch'):
            m.read_source(raw+b'x',m.FROZEN_PRICE_SHA,['date','close'])

    def test_labels_not_required_to_generate_events(self):
        import inspect
        self.assertEqual(list(inspect.signature(m.generate_alerts).parameters),
                         ['dates','closes'])

if __name__=='__main__':
    unittest.main()
