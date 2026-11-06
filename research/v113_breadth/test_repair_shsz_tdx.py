import sys,unittest,struct
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from repair_shsz_tdx import select_gap_fill,unpack_tdx,RECORD
def pack(entries):
    return b"".join(RECORD.pack(day,price,price+5,price-5,price,float(amount),vol,0)
        for day,price,amount,vol in entries)
class TestTdxScopedRepair(unittest.TestCase):
    def test_no_beijing_identity_used_and_only_missing_shsz_stock_day_filled(self):
        raw=pack([(20260918,1000,1200,100),(20260921,1020,2200,200),(20260922,1030,3400,300)])
        filled,left,trace=select_gap_fill("sh.600000",{"2026-09-21"},
            {"2026-09-18":10.0,"2026-09-22":10.3},raw)
        self.assertEqual(left,[])
        self.assertEqual([(r["date"],r["direction"]) for r in filled],[("2026-09-21","up")])
        self.assertEqual(trace["mismatches"],0)
    def test_mismatch_blocks_all(self):
        raw=pack([(20260918,1000,1200,100),(20260921,1020,2200,200),(20260922,1030,3400,300)])
        fill,left,trace=select_gap_fill("sz.000001",{"2026-09-21"},
            {"2026-09-18":10.0,"2026-09-22":90.0},raw)
        self.assertEqual(fill,[])
        self.assertEqual(left,["2026-09-21"])
        self.assertEqual(trace["reason"],"TDX_OVERLAP_DISAGREES_OR_INSUFFICIENT")
    def test_zero_volume_not_imputed(self):
        raw=pack([(20260918,1000,1200,100),(20260921,1020,0,0),(20260922,1030,3400,300)])
        fill,left,_=select_gap_fill("sh.600000",{"2026-09-21"},
            {"2026-09-18":10.0,"2026-09-22":10.3},raw)
        self.assertFalse(fill);self.assertEqual(left,["2026-09-21"])
    def test_corrupt_size_rejected(self):
        with self.assertRaisesRegex(ValueError,"TDX_BAD_LENGTH"):
            unpack_tdx(b"garbage")
if __name__=="__main__":unittest.main()
