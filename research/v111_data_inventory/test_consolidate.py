import json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from consolidate import build
def base():
    return {"indices":{c:[{"code":c,"date":"2026-10-20","close":5000,"amount":100,"turnover":1},
                          {"code":c,"date":"2026-10-21","close":5001,"amount":101,"turnover":1}] for c in ("000985","000300","000852")},
            "financing":[{"date":"2026-10-20","balance_sh_yuan":100,"balance_sz_yuan":0}]}
class TestConsolidation(unittest.TestCase):
    def test_zero_financing_not_backfilled(self):
        rows,report=build(base())
        self.assertEqual(rows[0]["financing_status"],"INVALID")
        self.assertEqual(rows[0]["balance_total_yuan"],"")
        self.assertEqual(report["financing_invalid_anchor"],1)
    def test_lag_shift_not_calendar_subtract(self):
        rows,_=build(base())
        self.assertEqual(rows[0]["decision_date_for_price_assuming_D_minus_1"],"2026-10-21")
        self.assertEqual(rows[0]["decision_date_for_financing_assuming_D_minus_2"],"")
    def test_code_mismatch_blocks(self):
        obj=base()
        obj["indices"]["000985"][0]["code"]="000300"
        with self.assertRaisesRegex(ValueError,"CODE_MISMATCH"):
            build(obj)
    def test_duplicate_blocks(self):
        obj=base();obj["indices"]["000985"].append(obj["indices"]["000985"][0])
        with self.assertRaisesRegex(ValueError,"DUPLICATE"):
            build(obj)
    def test_no_unknown_calendar_claim(self):
        _,report=build(base())
        self.assertFalse(report["formal_signal_allowed"])
        self.assertIn("not certified",report["anchor"])
if __name__=="__main__":unittest.main()
