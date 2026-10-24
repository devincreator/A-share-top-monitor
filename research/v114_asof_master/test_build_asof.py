import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from build_asof import build
class Tests(unittest.TestCase):
    def base(self):
        return [{"source_trade_date":d,"financing_status":"OK","balance_total_yuan":str(100+i),
                 "000985_close":str(500+i)} for i,d in enumerate(["2026-09-29","2026-09-30","2026-10-09","2026-10-12"])]
    def test_two_sessions_margin(self):
        rows,_=build(self.base())
        self.assertEqual(rows[1]["decision_date"],"2026-10-09")
        self.assertEqual(rows[1]["finance_asof"],"2026-09-29")
        self.assertEqual(rows[1]["price_asof"],"2026-09-30")
    def test_month_closed(self):
        rows,_=build(self.base())
        self.assertEqual(rows[1]["month_last_closed_day"],"2026-09-30")
    def test_no_same_day_breadth(self):
        rows,_=build(self.base(),[{"date":"2026-10-09","up":"2000","down":"3000"},
                                  {"date":"2026-10-12","up":"2001","down":"2999"}])
        self.assertFalse(rows[1]["breadth_valid"])
        self.assertTrue(rows[2]["breadth_valid"])
        self.assertEqual(rows[2]["breadth_up"],"2000")
    def test_calendar_duplicates_fail(self):
        with self.assertRaisesRegex(ValueError,"NON_UNIQUE"):build(self.base()*2)
if __name__=="__main__":unittest.main()
