import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from audit_breadth import validate
class V113Tests(unittest.TestCase):
    def test_missing_not_silently_filled(self):
        x=validate(["2026-01-01","2026-01-02"],[{"date":"2026-01-01","up":"10","down":"12"}])
        self.assertEqual(x["observed_reference_days"],1)
        self.assertFalse(x["full_v113_pass"])
    def test_duplication_blocks(self):
        with self.assertRaisesRegex(ValueError,"DUPLICATE"):
            validate(["2026-01-01"],[{"date":"2026-01-01","up":"10","down":"12"}]*2)
    def test_candidate_coverage_not_full_certification(self):
        x=validate(["2026-01-01"],[{"date":"2026-01-01","up":"10","down":"12"}])
        self.assertTrue(x["research_candidate_98pct_coverage_reached"])
        self.assertFalse(x["survivorship_bias_excluded"])
        self.assertFalse(x["full_v113_pass"])
if __name__=="__main__":unittest.main()
