import csv,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from reconstruct_breadth import calculate
class ReconstructTests(unittest.TestCase):
    def test_duplicate_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"x.csv"
            p.write_text("symbol,trade_date,close,pre_close,amount,vol\n"+"000001.SZ,20260814,10,9,100,100\n"*600)
            with self.assertRaisesRegex(ValueError,"DUPLICATE_SECURITY"):
                calculate(p,"2026-08-14")
    def test_wrong_day_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"x.csv"
            p.write_text("symbol,trade_date,close,pre_close,amount,vol\n000001.SZ,20260813,10,9,100,100\n")
            with self.assertRaisesRegex(ValueError,"WRONG_TRADE_DATE"):
                calculate(p,"2026-08-14")
if __name__=="__main__":unittest.main()
