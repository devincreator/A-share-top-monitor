import unittest
from annual_evidence import build
class YearInventoryTest(unittest.TestCase):
 def test_21_years(self):self.assertEqual(len(build()["years"]),21)
 def test_2006_raw_only(self):
  r=build()["years"][0];self.assertIn("RAW_SHA_VERIFIED_NOT_PIT",r["raw_daily_bar_coverage"]);self.assertFalse(r["formally_usable_for_market_breadth"])
 def test_gap_does_not_mean_no_data(self):
  for r in build()["years"]:
   self.assertNotEqual(r["raw_daily_bar_coverage"],"MISSING_ALL_DATA")
 def test_no_fake_pit_pass(self):
  for r in build()["years"]:
   self.assertEqual(r["historical_listing_pit"],"BLOCKED");self.assertEqual(r["source_publication_pit"],"BLOCKED")
if __name__=="__main__":unittest.main()
