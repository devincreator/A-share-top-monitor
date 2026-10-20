import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from readiness import build_report

STATE={'asof':'2026-09-21','data_status':'price_core_verified_partial','latest_formal_signals':{'top5':{'date':'2026-08-05','route':'B'}}}
MARKET={'market_date':'2026-10-08','model_date':'2026-08-04','complete_model_recalculated':False}

class ReadinessTests(unittest.TestCase):
    def test_does_not_promote_old_model(self):
        x=build_report(STATE,MARKET,today='2026-10-20')
        self.assertEqual(x['status'],'DATA_PENDING')
        self.assertFalse(x['is_new_formal_signal'])
        self.assertEqual(x['channels']['market_snapshot']['asof'],'2026-10-08')
    def test_bad_future_timestamp_fails_closed(self):
        with self.assertRaises(ValueError):
            build_report(STATE,MARKET,today='2026-09-01')
    def test_mismatched_model_date_fails(self):
        with self.assertRaises(ValueError):
            build_report(STATE,dict(MARKET,model_date='2026-10-09'),today='2026-10-20')
    def test_same_day_complete_is_readiness_not_alert(self):
        x=build_report(STATE,dict(MARKET,model_date='2026-10-08',complete_model_recalculated=True),today='2026-10-08')
        self.assertEqual(x['status'],'FORMAL_INPUTS_READY_FOR_SEPARATE_SIGNAL_ENGINE')
        self.assertFalse(x['is_new_formal_signal'])

if __name__=='__main__':unittest.main()
