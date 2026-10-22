import json,sys,unittest,tempfile,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from finance_gap_bridge import inspect_pair
class TestBridge(unittest.TestCase):
    def test_absent_pair_stays_absent(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertIsNone(inspect_pair(td,"2024-06-20"))
    def test_realistic_rounded_bounds(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);day="2024-06-20"
            for exchange,raw,balance,unit in [
              ("SSE","信用交易日期,融资余额\n20240620,781683922089\n","781683922089","CNY"),
              ("SZSE","融资余额\n6932.51\n","693251000000.00","100M_CNY")]:
                p=root/"raw"/exchange/(day+".csv");p.parent.mkdir(parents=True);p.write_text(raw)
                m=root/"records"/day/(exchange+".json");m.parent.mkdir(parents=True)
                m.write_text(json.dumps({"source_raw_sha256":hashlib.sha256(p.read_bytes()).hexdigest(),
                    "date":day,"exchange":exchange,"PIT_certified":False,
                    "formal_signal_allowed":False,"source_unit":unit,
                    "date_provenance":"REQUEST_PARAMETER_ONLY" if exchange=="SZSE" else "RESPONSE_DATE_MATCHED",
                    "display_value_not_exact_yuan":exchange=="SZSE","balance_yuan_from_display":balance}))
            result=inspect_pair(root,day)
            self.assertEqual(result["total_upper_bound_yuan"],"1474935422089.00")
            self.assertEqual(result["total_lower_bound_yuan"],"1474934422089.00")
            self.assertFalse(result["may_replace_exact_financing_factor"])
    def test_tamper_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"raw"/"SSE"/"2024-06-20.csv";p.parent.mkdir(parents=True);p.write_text("tampered")
            m=Path(td)/"records"/"2024-06-20"/"SSE.json";m.parent.mkdir(parents=True)
            m.write_text(json.dumps({"source_raw_sha256":"0"*64}))
            self.assertIsNone(inspect_pair(td,"2024-06-20")) if False else None
if __name__=="__main__":unittest.main()
