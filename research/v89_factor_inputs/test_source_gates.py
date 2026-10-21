import importlib.util
import json
import tempfile
import unittest
from datetime import date,timedelta
from pathlib import Path

HERE=Path(__file__).parent
def module(path,name):
    spec=importlib.util.spec_from_file_location(name,HERE/path)
    obj=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj

gate=module("strict_gate.py","v89_strict_gate")

def fixtures():
    asof="2026-10-20"
    days=[];d=date(2022,1,1)
    while d<=date(2026,10,20):
        if d.weekday()<5:
            days.append(d.isoformat())
        d+=timedelta(days=1)
    inputs={"indices":{},"financing":[]}
    for code in gate.CODES:
        inputs["indices"][code]=[{
            "date":day,"code":code,
            "close":gate.ANCHORS.get(day,5800.0) if code=="000985" else 4000,
            "amount":1e12,"turnover":1.8} for day in days]
    inputs["financing"]=[{
        "date":day,"balance_sh_yuan":1.25e12,"balance_sz_yuan":1.3e12} for day in days]
    return asof,inputs

class SourceGateTests(unittest.TestCase):
    def test_all_inputs_do_not_generate_signal(self):
        asof,inputs=fixtures()
        result=gate.assess(inputs,asof=asof)
        self.assertEqual(result["status"],"PRIMITIVE_INPUTS_SCHEMA_VALID_RESEARCH_ONLY")
        self.assertFalse(result["formal_signal_allowed"])

    def test_wrong_all_share_anchor_rejected(self):
        asof,inputs=fixtures()
        for r in inputs["indices"]["000985"]:
            if r["date"]=="2026-10-08":
                r["close"]=9999
        result=gate.assess(inputs,asof=asof)
        self.assertIn("price index anchor failed",str(result["errors"]))

    def test_missing_price_date_rejected(self):
        asof,inputs=fixtures()
        inputs["indices"]["000300"]=[r for r in inputs["indices"]["000300"] if r["date"]!=asof]
        self.assertEqual(gate.assess(inputs,asof=asof)["status"],"BLOCKED")

    def test_financing_wrong_units_rejected(self):
        asof,inputs=fixtures()
        for r in inputs["financing"]:
            r["balance_sh_yuan"]/=1e8
            r["balance_sz_yuan"]/=1e8
        self.assertIn("unit mismatch",str(gate.assess(inputs,asof=asof)["errors"]))

    def test_duplicate_financing_date_rejected(self):
        asof,inputs=fixtures()
        inputs["financing"].append(dict(inputs["financing"][-1]))
        self.assertEqual(gate.assess(inputs,asof=asof)["status"],"BLOCKED")

    def test_source_identity_required(self):
        asof,inputs=fixtures()
        del inputs["indices"]["000985"][0]["code"]
        self.assertIn("unverified index identity",str(gate.assess(inputs,asof=asof)["errors"]))

    def test_asof_uses_real_verified_raw_day(self):
        import sys
        sys.path.insert(0,str(HERE))
        candidates=module("collect_candidates.py","v89_collect")
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/"2026-10-20.json").write_text(json.dumps({
                "observation_date":"2026-10-20","source_format_verified":True,
                "source_raw_sha256":"abc"}))
            (root/"2026-10-21.json").write_text(json.dumps({
                "observation_date":"2026-10-21","source_format_verified":False,
                "source_raw_sha256":"def"}))
            self.assertEqual(candidates.latest_research_source_day(root),"2026-10-20")

if __name__=="__main__":
    unittest.main()
