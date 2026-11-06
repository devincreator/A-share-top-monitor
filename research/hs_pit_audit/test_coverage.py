import unittest
from coverage import evaluate,feature_gate
SHA="a"*64
class CoverageTests(unittest.TestCase):
 def test_empty_calendar_blocks(self):
  self.assertEqual(evaluate([],"2026-10-27",["2005-01-04"])["status"],"BLOCKED")
 def test_missing_source_is_not_suspend(self):
  r=[dict(date="2005-01-04",security_listing_id="old",status="SOURCE_GAP",independent_evidence_uri="x")]
  self.assertEqual(evaluate(r,"2026-10-27")["status"],"BLOCKED")
 def test_valid_suspended_schema_only(self):
  r=[dict(date="2005-01-04",security_listing_id="old",status="CONFIRMED_SUSPENDED",independent_evidence_uri="x")]
  self.assertFalse(evaluate(r,"2026-10-27")["PIT_certified"])
 def test_same_security_twice(self):
  r=[dict(date="2005-01-04",security_listing_id="old",status="TRADED",source_raw_sha256=SHA)]*2
  self.assertEqual(evaluate(r,"2026-10-27")["status"],"BLOCKED")
 def test_same_day_block(self):
  r=[{"factor":"INDEX_CLOSE","observation_date":"2026-10-27","published_at":"2026-10-27T15:31:00+08:00","source_raw_sha256":SHA,"publication_evidence_uri":"x","publication_provenance":"INDEPENDENTLY_VERIFIED"}]
  self.assertIn("SAME_OR_FUTURE_DAY",feature_gate(r,"2026-10-27T09:20:00+08:00")["factors"][0]["reasons"])
 def test_dminus_one_late_release(self):
  r=[{"factor":"INDEX_CLOSE","observation_date":"2026-10-26","published_at":"2026-10-27T09:25:00+08:00","source_raw_sha256":SHA,"publication_evidence_uri":"x","publication_provenance":"INDEPENDENTLY_VERIFIED"}]
  self.assertIn("LATE_PUBLICATION",feature_gate(r,"2026-10-27T09:20:00+08:00")["factors"][0]["reasons"])
if __name__=="__main__":unittest.main()
