import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from state_stability import analyze
class StabilityTests(unittest.TestCase):
    def test_no_labels_or_pit_claim(self):
        result=analyze([{"asof_close_date":"2025-12-31","state":"UPTREND"},
                        {"asof_close_date":"2026-01-02","state":"DOWNTREND"}])
        self.assertEqual(result["sample_rows"],2)
        self.assertFalse(result["prospective_predictions_scored"])
        self.assertFalse(result["source_pit_certified"])
        self.assertEqual(len(result["annual_frequency"]),2)
    def test_duplicate_dates_block(self):
        with self.assertRaisesRegex(ValueError,"NON_INCREASING"):
            analyze([{"asof_close_date":"2026-01-02","state":"MIXED"},
                     {"asof_close_date":"2026-01-02","state":"MIXED"}])
    def test_unregistered_state_block(self):
        with self.assertRaisesRegex(ValueError,"UNKNOWN_STATE"):
            analyze([{"asof_close_date":"2026-01-02","state":"FUTURE_TOP"}])
    def test_no_data_blocks(self):
        with self.assertRaisesRegex(ValueError,"EMPTY_STATE_HISTORY"):
            analyze([])
if __name__=="__main__":unittest.main()
