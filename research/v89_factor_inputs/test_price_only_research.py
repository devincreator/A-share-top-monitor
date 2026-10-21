import importlib.util
import json
import math
import tempfile
import unittest
from datetime import date,timedelta
from pathlib import Path

source=Path(__file__).with_name("price_only_research.py")
spec=importlib.util.spec_from_file_location("price_only_research",source)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def make():
    rows=[];d=date(2022,1,1);i=0
    while len(rows)<1010:
        if d.weekday()<5:
            rows.append({"date":d.isoformat(),"code":"000985",
                         "close":5000+0.4*i+100*math.sin(i/17),
                         "amount":1e12,"turnover":1.2})
            i+=1
        d+=timedelta(days=1)
    return rows

class PriceResearchTests(unittest.TestCase):
    def test_only_past_data_used(self):
        r=make();a=m.compute(r[:990],r[989]["date"])
        changed=[dict(x) for x in r]
        for x in changed[990:]:
            x["close"]=1e8
        b=m.compute(changed[:990],changed[989]["date"])
        self.assertEqual(a,b)
        self.assertFalse(a["formal_signal_allowed"])
        self.assertFalse(a["uses_information_after_asof"])

    def test_prior_percentile_excludes_today(self):
        history=list(range(756))+[800]
        self.assertAlmostEqual(m.percentile_before(history,756),100)
        history[-1]=-1
        self.assertEqual(m.percentile_before(history,756),0)

    def test_missing_observations_block(self):
        r=make()[:880]
        with self.assertRaises(ValueError):
            m.compute(r,r[-1]["date"])

    def test_source_disagreement_prevents_factor_output(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/"candidate_inputs.json").write_text(json.dumps({"indices":{"000985":make()}}))
            (root/"cross_provider_audit.json").write_text(json.dumps({
                "asof":make()[-1]["date"],
                "cross_index_source_status":"BLOCKED"}))
            with self.assertRaises(ValueError):
                m.research_report(root)

if __name__=="__main__":
    unittest.main()
