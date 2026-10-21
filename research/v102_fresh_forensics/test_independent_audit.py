import importlib.util
from itertools import combinations
from pathlib import Path
from decimal import Decimal
import unittest

SOURCE=Path(__file__).with_name("independent_audit.py")
spec=importlib.util.spec_from_file_location("v102_independent_audit",SOURCE)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class V102Tests(unittest.TestCase):
    def test_actual_59_new_signals_and_32_fp_28_fn(self):
        report,fp,fn,warmup=m.build()
        self.assertEqual(report["independent_new_formal_starts_reproduced"],59)
        self.assertEqual(report["independent_event_outcomes_reproduced"],59)
        self.assertEqual((len(fp),len(fn),len(warmup)),(32,28,5))
        self.assertFalse(report["formal_signal_allowed"])
        self.assertFalse(report["source_asof_PIT_verified"])
        self.assertFalse(report["blind_sample"])

    def test_actual_five_historically_unforecastable_mature_objectives(self):
        result,_,_,warmup=m.build()
        count={k:v["full_forecast_opportunity_sensitivity"]
               for k,v in result["full_lead_window_eligible_metrics"].items()}
        expected={"5_TOP":(1,8,11,7,15),"5_BOTTOM":(2,6,12,8,14),
                  "9_TOP":(1,2,7,4,6),"9_BOTTOM":(1,2,2,4,6)}
        for k,(excluded,tp,fp,fn,den) in expected.items():
            x=count[k]
            self.assertEqual(tuple(x[y] for y in
                ("excluded_insufficient_history","tp","fp","fn","eligible_mature_pivots")),
                (excluded,tp,fp,fn,den))
            self.assertAlmostEqual(x["recall"],tp/den)
        self.assertEqual(len({a["pivot_id"] for a in warmup}),5)

    def test_event_count_and_rule_mechanics(self):
        prices=m.rows_from_file("prices")
        dates=[x["date"] for x in prices]
        closes=[Decimal(x["close"]) for x in prices]
        events,state=m.independent_alerts(dates,closes)
        self.assertEqual(len(events),59)
        self.assertEqual(len({e["id"] for e in events}),59)
        for a in events:
            self.assertEqual(a["asof"],dates[a["source_index"]])
            self.assertEqual(a["date"],dates[a["source_index"]+1])
            self.assertLess(a["source_index"],len(dates)-1)
        self.assertTrue(state)

    def test_D_day_close_is_not_a_predictor(self):
        xs=[Decimal("100")+Decimal(i)/10 for i in range(300)]
        for task,r in m.RULES.items():
            first=m.candidate(xs,200,r)
            different=list(xs)
            different[200]=Decimal("9999999")
            different[201:]=[Decimal("0.001")]*len(different[201:])
            self.assertEqual(first,m.candidate(different,200,r),task)

    def test_separate_dynamic_program_matches_bruteforce_cardinality(self):
        dates=[f"2026-10-{i:02d}" for i in range(1,9)]
        pos={x:i for i,x in enumerate(dates)}
        def optimal(aa,pp,max_lead):
            def dfs(i,seen):
                if i==len(aa):return 0
                base=dfs(i+1,seen)
                for j,p in enumerate(pp):
                    if j not in seen and 1<=pos[p["date"]]-pos[aa[i]["date"]]<=max_lead:
                        base=max(base,1+dfs(i+1,seen|{j}))
                return base
            return dfs(0,set())
        subset=[()]+[c for n in (1,2,3) for c in combinations(range(7),n)]
        n=0
        for ac in subset:
            aa=[{"id":f"a{i}","date":dates[i]} for i in ac]
            for pc in subset:
                pp=[{"id":f"p{i}","date":dates[i]} for i in pc]
                for lead in (1,2,3):
                    ours=m.independent_max_match(aa,pp,pos,lead)
                    self.assertEqual(len(ours),optimal(aa,pp,lead))
                    n+=1
        self.assertGreater(n,7000)

    def test_no_original_source_or_research_success_claimed(self):
        report,fp,fn,_=m.build()
        self.assertTrue(report["not_forecastability_improvement_only_denominator_correction"])
        self.assertEqual(sum(x["expost_diagnostic"].startswith("EXTREME_") for x in fp),11)
        self.assertEqual(sum(x["expost_rule_diagnostic"]=="NO_SUFFICIENT_PRIOR_PRICE_HISTORY" for x in fn),5)

if __name__=="__main__":unittest.main()
