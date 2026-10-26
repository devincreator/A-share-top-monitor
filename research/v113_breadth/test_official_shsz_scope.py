import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from audit_official_shsz_scope import audit
class ScopeTests(unittest.TestCase):
 def test_issuer_stock_are_not_equated(self):
  rows=[{"code":"sh.600000","type":"1","ipoDate":"1999-11-10","outDate":""}]
  r=audit(rows)
  self.assertFalse(r["independent_stock_identity_reconciliation_certified"])
  self.assertTrue(all(x["metric_same_definition"] is False for x in r["official_comparisons"]))
 def test_duplicate_basics_blocks(self):
  row={"code":"sh.600000","type":"1","ipoDate":"1999-11-10","outDate":""}
  with self.assertRaisesRegex(ValueError,"DUPLICATE_CODE"):audit([row,row])
if __name__=="__main__":unittest.main()
