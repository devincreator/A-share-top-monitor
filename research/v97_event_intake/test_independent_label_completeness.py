import importlib.util
from copy import deepcopy
import unittest
from pathlib import Path

SPEC=importlib.util.spec_from_file_location(
    "v97_independent_label_completeness",
    Path(__file__).with_name("independent_label_completeness.py"))
audit=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def prices():
    values=[100,110,108,104,99,106,112]
    return [{"date":f"2026-10-{i:02d}","close":str(x)}
            for i,x in enumerate(values,1)]


def complete_rows():
    return (audit.calculate_all_reversals(prices(),"5")[0]+
            audit.calculate_all_reversals(prices(),"9")[0])


class IndependentCompletenessTests(unittest.TestCase):
    def test_two_thresholds_reproduce_distinct_first_crossings(self):
        small,small_trailing=audit.calculate_all_reversals(prices(),"5")
        large,large_trailing=audit.calculate_all_reversals(prices(),"9")
        self.assertEqual([(x["direction"],x["date"],x["confirmation_date"])
                          for x in small],
                         [("BOTTOM","2026-10-01","2026-10-02"),
                          ("TOP","2026-10-02","2026-10-04"),
                          ("BOTTOM","2026-10-05","2026-10-06")])
        self.assertEqual([(x["direction"],x["date"],x["confirmation_date"])
                          for x in large],
                         [("BOTTOM","2026-10-01","2026-10-02"),
                          ("TOP","2026-10-02","2026-10-05"),
                          ("BOTTOM","2026-10-05","2026-10-07")])
        self.assertEqual(small_trailing["status"],"UNCONFIRMED_TRAILING_EXTREME")
        self.assertTrue(all(not x.get("formal_signal_allowed",False)
                            for x in [small_trailing,large_trailing]))

    def test_complete_archived_labels_must_have_one_to_one_generation(self):
        result=audit.compare_complete(prices(),complete_rows())
        self.assertEqual(result["status"],
                         "BOUNDED_LABEL_ENUMERATION_MATCHED_NOT_ORIGINAL_ALERTS_OR_PIT")
        self.assertEqual(result["scale_checks"]["5"]["missing_labels"],0)
        self.assertFalse(result["formal_signal_allowed"])
        self.assertFalse(result["original_formal_start_restored"])

    def test_omitted_pivot_is_discovered_not_silently_accepted(self):
        labels=complete_rows()
        labels=[x for x in labels if x["id"]!="5_TOP_2026-10-02"]
        result=audit.compare_complete(prices(),labels)
        self.assertEqual(result["status"],"BLOCKED")
        self.assertEqual(result["scale_checks"]["5"]["missing_labels"],1)
        self.assertTrue(any(x["reason"]=="MISSING_CONFIRMED_REVERSAL"
                            for x in result["discrepancies"]))

    def test_extra_hindsight_label_is_rejected(self):
        rows=complete_rows()
        forged=deepcopy(rows[0])
        forged["id"]="5_BOTTOM_2026-10-03"
        forged["date"]="2026-10-03"
        rows.append(forged)
        result=audit.compare_complete(prices(),rows)
        self.assertEqual(result["scale_checks"]["5"]["extra_labels"],1)
        self.assertFalse(result["independent_reversal_enumeration_complete_within_bounded_price_series"])

    def test_wrong_first_confirmation_detected(self):
        rows=complete_rows()
        for x in rows:
            if x["id"]=="5_TOP_2026-10-02":
                x["confirmation_date"]="2026-10-05"
        result=audit.compare_complete(prices(),rows)
        self.assertGreater(result["scale_checks"]["5"]["mismatched_fields"],0)
        self.assertIn("FIELD_MISMATCH",[x["reason"] for x in result["discrepancies"]])

    def test_duplicate_reported_pivot_detected(self):
        rows=complete_rows()
        rows.append(deepcopy(rows[0]))
        result=audit.compare_complete(prices(),rows)
        self.assertEqual(result["status"],"BLOCKED")
        self.assertIn("DUPLICATE_ARCHIVED_ID",
                      [x["reason"] for x in result["discrepancies"]])

    def test_invalid_or_unsorted_close_rejected(self):
        broken=prices()
        broken[4]["close"]="NaN"
        with self.assertRaises(ValueError):
            audit.calculate_all_reversals(broken,"5")
        swapped=prices()
        swapped[4],swapped[5]=swapped[5],swapped[4]
        with self.assertRaises(ValueError):
            audit.calculate_all_reversals(swapped,"9")


if __name__=="__main__":
    unittest.main()
