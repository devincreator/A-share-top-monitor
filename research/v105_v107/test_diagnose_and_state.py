import importlib.util
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).parent
sys.path.insert(0,str(ROOT))
import diagnose_and_state as m

class DiagnosticsTests(unittest.TestCase):
    def test_no_future_dependency(self):
        xs=[100+i*.1 for i in range(100)]
        x=m.trailing_features(xs)
        self.assertEqual(x,m.trailing_features(xs+[99999][0:0]))
        self.assertEqual(x,m.trailing_features(xs[:]))
    def test_warmup(self):
        self.assertIsNone(m.trailing_features([100]*63))
        self.assertIsNotNone(m.trailing_features([100]*64))
    def test_hindsight_not_allowed_as_feature(self):
        events=[{"id":"a"}]
        fp=[{"alert_id":"a","task":"5_TOP","expost_diagnostic":"ANY","type":"BAD"}]
        with self.assertRaisesRegex(ValueError,"HINDSIGHT_BOUNDARY"):
            m.diagnose(fp,[],events)
    def test_unknown_fp_rejected(self):
        fp=[{"alert_id":"not_there","task":"5_TOP","expost_diagnostic":"ANY","type":"HINDSIGHT_DIAGNOSTIC_NOT_PREOPEN_FACTOR"}]
        with self.assertRaisesRegex(ValueError,"FP_NOT_IN_FROZEN"):
            m.diagnose(fp,[],[{"id":"a"}])
    def test_deterministic_states(self):
        a=[100+i*.2 for i in range(100)]
        self.assertEqual(m.trailing_features(a)["state"],"UPTREND")
        self.assertEqual(m.trailing_features(list(reversed(a)))["state"],"DOWNTREND")
    def test_event_state_crosswalk_uses_prior_observation(self):
        states=[{"asof_close_date":"2026-10-21","state":"UPTREND","ret5":.01,"ret20":.03,"ret63":.06,"position_63":.9}]
        ev=[{"id":"e1","task":"5_TOP","date":"2026-10-22","last_price_observation_date":"2026-10-21"}]
        out=m.event_state_crosswalk(ev,states)
        self.assertEqual(out[0]["state"],"UPTREND")
        self.assertFalse(out[0]["historical_source_time_certified"])
        ev[0]["last_price_observation_date"]="2026-10-22"
        with self.assertRaisesRegex(ValueError,"MISSING_ASOF_STATE"):
            m.event_state_crosswalk(ev,states)
    def test_fp_contingency_never_converts_pending_to_tp(self):
        rows=[{"alert_id":"a","task":"5_TOP","state":"UPTREND"},
              {"alert_id":"b","task":"5_TOP","state":"UPTREND"}]
        fp=[{"alert_id":"a"}]
        result=m.hindsight_error_by_state(rows,fp)[0]
        self.assertEqual(result["retrospective_fp"],1)
        self.assertEqual(result["not_identified_as_fp_in_this_file"],1)
        self.assertTrue(result["non_fp_may_include_pending"])
        with self.assertRaisesRegex(ValueError,"ORPHAN"):
            m.hindsight_error_by_state(rows,[{"alert_id":"unknown"}])
    def test_duplicate_dates(self):
        with self.assertRaisesRegex(ValueError,"DUPLICATE_PRICE"):
            m.parse_price_table([{"date":"2026-01-01","close":"10"},{"date":"2026-01-01","close":"11"}])
    def test_state_row_prefix_stability(self):
        p=[("2026-%02d-%02d"%(1+(i//28),1+(i%28)),100+i) for i in range(100)]
        a=m.states_asof(p)
        b=m.states_asof(p+[("2026-05-01",100000)])
        self.assertEqual(a,b[:len(a)])
if __name__=="__main__":unittest.main()
