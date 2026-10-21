import importlib.util
import unittest
from datetime import date,timedelta
from pathlib import Path

S=Path(__file__).with_name("cross_provider.py")
spec=importlib.util.spec_from_file_location("cross_provider",S)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def fx():
    a=date(2026,9,1)
    days=[]
    for i in range(42):
        d=a+timedelta(days=i)
        if d.weekday()<5:
            days.append(d)
    arr=[{"indexCode":"000985","tradeDate":d.strftime("%Y%m%d"),
          "close":5000+i,"tradingValue":10000.23} for i,d in enumerate(days)]
    alternate=[{"code":"000985","date":d.isoformat(),"close":5000+i,
                "amount":1000023000000.0} for i,d in enumerate(days)]
    return {"data":arr},alternate,days[-1].isoformat()

class CrossProviderTests(unittest.TestCase):
    def test_consistent_both_fields_accept_research_only(self):
        official,alt,asof=fx()
        x=m.compare_one("000985",official,alt,asof)
        self.assertEqual(x["matched"],len(alt))
        self.assertEqual(x["status"],"RESEARCH_CROSS_PROVIDER_PASS")
        self.assertFalse(x["provider_independence_certified"])

    def test_weekend_quarantined(self):
        official,alt,asof=fx()
        official["data"].append({"indexCode":"000985","tradeDate":"20260905",
                                 "close":5001,"tradingValue":10000.23})
        x=m.compare_one("000985",official,alt,asof)
        self.assertEqual(x["quarantined_non_trading_dates"],["2026-09-05"])
        self.assertEqual(x["status"],"RESEARCH_CROSS_PROVIDER_PASS_WITH_QUARANTINE")

    def test_unit_mismatch_not_silently_accepted(self):
        official,alt,asof=fx()
        official["data"][-1]["tradingValue"]*=10000
        x=m.compare_one("000985",official,alt,asof)
        self.assertEqual(x["status"],"BLOCKED")
        self.assertIn("amount disagreement",str(x["mismatches"]))

    def test_wrong_instrument_rejected(self):
        official,alt,asof=fx()
        official["data"][-1]["indexCode"]="H00985"
        x=m.compare_one("000985",official,alt,asof)
        self.assertEqual(x["status"],"BLOCKED")

    def test_nonmatching_close_blocks(self):
        official,alt,asof=fx()
        alt[-1]["close"]=123.45
        self.assertEqual(m.compare_one("000985",official,alt,asof)["status"],"BLOCKED")

    def test_future_row_blocks(self):
        official,alt,asof=fx()
        prev=days=alt[-2]["date"]
        self.assertEqual(m.compare_one("000985",official,alt,prev)["status"],"BLOCKED")

if __name__=="__main__":
    unittest.main()
