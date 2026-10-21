import json
import unittest
from pathlib import Path


class LegacySummaryContract(unittest.TestCase):
    def test_not_a_reconstructed_event_log(self):
        doc=json.loads(Path(__file__).with_name("legacy_2015_2021_baseline.json").read_text(encoding="utf8"))
        self.assertEqual(doc["research_track"],"LONG_CSI300")
        self.assertEqual(doc["replay_status"],"BLOCKED_ORIGINAL_DATED_EVENTS")
        self.assertFalse(doc["source_alert_clock_verified_preopen"])
        self.assertFalse(doc["formal_signal_allowed"])

    def test_old_report_aggregates_self_consistent(self):
        doc=json.loads(Path(__file__).with_name("legacy_2015_2021_baseline.json").read_text())
        t=doc["tasks"]
        self.assertEqual((t["5_TOP"]["alerts"],t["5_TOP"]["tp"],t["5_TOP"]["fp"]),(70,21,49))
        self.assertEqual((t["5_BOTTOM"]["alerts"],t["5_BOTTOM"]["tp"],t["5_BOTTOM"]["fp"]),(61,22,39))
        self.assertEqual((t["9_TOP"]["alerts"],t["9_TOP"]["tp"],t["9_TOP"]["fp"]),(27,4,23))
        self.assertEqual((t["9_BOTTOM"]["alerts"],t["9_BOTTOM"]["tp"],t["9_BOTTOM"]["fp"]),(21,6,15))
        for task in t.values():
            self.assertEqual(task["alerts"],task["tp"]+task["fp"])
            self.assertEqual(task["mature_pivots"],task["tp"]+task["fn"])

    def test_no_aggregated_result_inferred_as_preopen_success(self):
        doc=json.loads(Path(__file__).with_name("legacy_2015_2021_baseline.json").read_text())
        self.assertFalse(doc["same_day_features_excluded_certified"])
        self.assertEqual(doc["preopen_equivalence_status"],
                         "BLOCKED_LEGACY_SAME_DAY_FEATURE_CLOCK_UNKNOWN")


if __name__=="__main__":
    unittest.main()
