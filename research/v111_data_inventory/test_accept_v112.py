import csv,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from accept_v112 import audit
class V112Tests(unittest.TestCase):
    def fixture(self,root,count=100):
        root=Path(root);d=root/"daily.csv";b=root/"bridge.csv";m=root/"report.json"
        with d.open("w",newline="") as f:
            w=csv.DictWriter(f,fieldnames=["source_trade_date","financing_status","balance_total_yuan"]);w.writeheader()
            for i in range(count):
                w.writerow({"source_trade_date":f"2026-{i//28+1:02d}-{i%28+1:02d}","financing_status":"OK" if i<count-2 else "MISSING","balance_total_yuan":"100" if i<count-2 else ""})
        with b.open("w",newline="") as f:
            w=csv.DictWriter(f,fieldnames=["date","status","may_replace_exact_financing_factor","total_lower_bound_yuan","total_upper_bound_yuan","total_display_yuan_not_exact"]);w.writeheader()
            w.writerow({"date":f"2026-{(count-2)//28+1:02d}-{(count-2)%28+1:02d}","status":"DUAL_EXCHANGE_SOURCE_RESEARCH_ROUNDED_SZSE","may_replace_exact_financing_factor":"False","total_lower_bound_yuan":99,"total_upper_bound_yuan":101,"total_display_yuan_not_exact":100})
        m.write_text(json.dumps({"row_count":count}))
        return d,b,m
    def test_99_percent_exact_cutoff(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(audit(*self.fixture(t))["status"],"PASS")
    def test_98_percent_blocks(self):
        with tempfile.TemporaryDirectory() as t:
            d,b,m=self.fixture(t);b.write_text("date,status,may_replace_exact_financing_factor,total_lower_bound_yuan,total_upper_bound_yuan,total_display_yuan_not_exact\n")
            self.assertEqual(audit(d,b,m)["status"],"PARTIAL")
    def test_no_imputation(self):
        with tempfile.TemporaryDirectory() as t:
            d,b,m=self.fixture(t);s=d.read_text().replace("MISSING,","MISSING,999")
            d.write_text(s)
            with self.assertRaisesRegex(ValueError,"GAP_IMPUTATION"):audit(d,b,m)
if __name__=="__main__":unittest.main()
