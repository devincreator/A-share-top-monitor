import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from audit_shsz_a_issuers import audit,eligible
class TestIssuerBasis(unittest.TestCase):
 def test_out_date_boundary(self):
  self.assertTrue(eligible({"ipoDate":"2022-01-01","outDate":"2024-12-31"},"2024-12-31"))
  self.assertFalse(eligible({"ipoDate":"2022-01-01","outDate":"2024-12-31"},"2025-01-01"))
 def test_only_a_count(self):
  b=[{"code":"sh.123456","ipoDate":"2020-01-01","outDate":""}]
  r=audit(b,{"2024-12-31":(1,0)})
  self.assertTrue(all(x["matches"] for x in r))
 def test_mismatch_must_remain_visible(self):
  self.assertEqual(audit([],{"2024-12-31":(1,0)})[0]["delta"],-1)
if __name__=="__main__":unittest.main()
