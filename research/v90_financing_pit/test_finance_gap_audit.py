import importlib.util
import unittest
from datetime import date,timedelta
from pathlib import Path

spec=importlib.util.spec_from_file_location("finance_gap_audit",Path(__file__).with_name("finance_gap_audit.py"))
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def example(n=1000):
    dates=[]
    d=date(2020,1,1)
    while len(dates)<n:
        if d.weekday()<5: dates.append(d.isoformat())
        d+=timedelta(days=1)
    data={"indices":{"000985":[{"date":x} for x in dates]},
          "financing":[{"date":x,"balance_sh_yuan":1.2e12+i*1e7,
                        "balance_sz_yuan":1.1e12+i*1e7} for i,x in enumerate(dates)]}
    return data,dates

class CoverageTests(unittest.TestCase):
    def test_uninterrupted_can_calculate_research_factors(self):
        data,_=example()
        o=m.audit(data)
        self.assertEqual(o["market_sessions_missing_financing"],0)
        self.assertEqual(o["prior756_rank_status"],"RESEARCH_ARITHMETIC_ONLY")
        self.assertFalse(o["formal_signal_allowed"])

    def test_zero_blocks_756_but_not_clean_latest_63(self):
        data,dates=example()
        data["financing"][350]["balance_sz_yuan"]=0
        o=m.audit(data)
        self.assertEqual(o["invalid_nonpositive_dates"],[dates[350]])
        self.assertEqual(o["prior756_unusable_growth_sessions"],2)
        self.assertEqual(o["prior756_rank_status"],"BLOCKED")
        self.assertEqual(o["growth63_status"],"RESEARCH_ARITHMETIC_ONLY")
        self.assertEqual(o["imputed_rows"],0)

    def test_contiguous_missing_source_days_not_dropped_from_calendar(self):
        data,dates=example()
        gap=set(dates[400:560])
        data["financing"]=[row for row in data["financing"] if row["date"] not in gap]
        o=m.audit(data)
        self.assertEqual(o["market_sessions_missing_financing"],160)
        self.assertEqual(o["missing_session_ranges"][0]["trading_sessions"],160)
        self.assertEqual(o["prior756_rank_status"],"BLOCKED")

    def test_rounded_secondary_quote_is_not_exact_pit(self):
        q={"exchange":"SZ","trade_date":"2024-08-08","value_yi_yuan":6649.54,
           "precision_yi_yuan":.01,"first_supported_publication_date":"2024-08-09",
           "urls":["https://www.jiemian.com/article/11535150.html"]}
        o=m.corroborate_quote(q)
        self.assertEqual(o["upper_yuan_exclusive"]-o["lower_yuan_inclusive"],1000000)
        self.assertFalse(o["official_exact_data"])
        self.assertFalse(o["usable_as_of_trade_close"])

    def test_same_day_quote_rejected(self):
        q={"exchange":"SZ","trade_date":"2024-08-08","value_yi_yuan":6649.54,
           "precision_yi_yuan":.01,"first_supported_publication_date":"2024-08-08",
           "urls":[]}
        with self.assertRaises(ValueError):m.corroborate_quote(q)

if __name__=="__main__":
    unittest.main()
