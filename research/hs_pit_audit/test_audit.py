import unittest
from audit import audit
SHA="a"*64

def sample():
    return {"decision_at":"2026-10-27T09:20:00+08:00",
      "episodes":[{"security_listing_id":"issuer-old","symbol":"600018.SH",
        "listed_from":"2000-01-01","listed_through":"2005-12-31",
        "listing_evidence_uri":"https://example.org/proof"}],
      "bars":[{"security_listing_id":"issuer-old","symbol":"600018.SH",
        "date":"2005-01-04","source_raw_sha256":SHA}],
      "missing":[],
      "features":[{"name":"INDEX_CLOSE","observation_date":"2026-10-26",
        "published_at":"2026-10-26T16:00:00+08:00",
        "source_uri":"https://example.org/raw","source_raw_sha256":SHA,
        "publication_evidence_uri":"https://example.org/release",
        "publication_provenance":"INDEPENDENTLY_VERIFIED"}]}

class AuditTest(unittest.TestCase):
    def test_never_certifies_source(self):
        r=audit(sample())
        self.assertEqual(r["status"],"SCHEMA_CANDIDATE_NOT_PIT_CERTIFIED")
        self.assertFalse(r["formal_signal_allowed"])
    def test_d_day_block(self):
        x=sample();x["features"][0]["observation_date"]="2026-10-27"
        self.assertEqual(audit(x)["status"],"BLOCKED")
    def test_late_release_block(self):
        x=sample();x["features"][0]["published_at"]="2026-10-27T09:25:00+08:00"
        self.assertEqual(audit(x)["status"],"BLOCKED")
    def test_unresolved_missing_not_suspension(self):
        x=sample();x["missing"]=[{"security_listing_id":"issuer-old","date":"2005-01-05","classification":"UNRESOLVED"}]
        self.assertEqual(audit(x)["status"],"BLOCKED")
    def test_suspension_requires_evidence(self):
        x=sample();x["missing"]=[{"security_listing_id":"issuer-old","date":"2005-01-05","classification":"CONFIRMED_SUSPENDED"}]
        self.assertEqual(audit(x)["status"],"BLOCKED")
    def test_reused_ticker_overlap(self):
        x=sample();x["episodes"].append({"security_listing_id":"issuer-new","symbol":"600018.SH","listed_from":"2005-01-01","listing_evidence_uri":"https://example.org/proof2"})
        self.assertEqual(audit(x)["status"],"BLOCKED")
    def test_bar_invalid_listing_day(self):
        x=sample();x["bars"][0]["date"]="2006-01-04"
        self.assertEqual(audit(x)["status"],"BLOCKED")

if __name__=="__main__": unittest.main()
