import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from openspec_acceptance import evaluate
class Acceptance(unittest.TestCase):
    def test_aggregate_only_never_passes(self):
        r=evaluate(["d1","d2"],[],["d1","d2"],universe_verified=True,suspensions_verified=True)
        self.assertEqual(r["state"],"PARTIAL")
    def test_bars_alone_dont_certify_suspensions(self):
        days=[str(i) for i in range(100)]
        r=evaluate(days,days,[],universe_verified=True)
        self.assertEqual(r["state"],"PARTIAL")
    def test_real_pass_requires_all_checks(self):
        days=[str(i) for i in range(100)]
        r=evaluate(days,days[:98],[],universe_verified=True,suspensions_verified=True)
        self.assertEqual(r["state"],"PASS")
    def test_false_success_does_not_inflate_coverage(self):
        r=evaluate(["d1","d2"],[],["d1"],universe_verified=False)
        self.assertEqual(r["coverage_security_dates"],0)
        self.assertEqual(r["state"],"PARTIAL")
    def test_outside_calendar_blocks(self):
        with self.assertRaisesRegex(ValueError,"OUT_OF_REFERENCE_DATE"):
            evaluate(["d1"],["d2"],[])
if __name__=="__main__":unittest.main()
