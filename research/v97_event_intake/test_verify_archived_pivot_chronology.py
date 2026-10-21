import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SPEC=importlib.util.spec_from_file_location("v97_label_check",
    Path(__file__).with_name("verify_archived_pivot_chronology.py"))
checker=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


def price_rows():
    return [{"date":day,"close":str(v)} for day,v in [
        ("2026-01-05",100),("2026-01-06",110),
        ("2026-01-07",104),("2026-01-08",99),
        ("2026-01-09",101),("2026-01-12",109),
        ("2026-01-13",102)]]


def label(id,day,confirmed,direction,extreme,next_day,left):
    return {"id":id,"date":day,"scale":"5","direction":direction,
        "extreme_close":str(extreme),"confirmation_date":confirmed,
        "earliest_possible_preopen_day_after_confirmation":next_day,
        "first_segment_left_censored":"true" if left else "false"}


def events():
    return [
        label("5_TOP_2026-01-06","2026-01-06","2026-01-07","TOP",110,"2026-01-08",True),
        label("5_BOTTOM_2026-01-08","2026-01-08","2026-01-12","BOTTOM",99,"2026-01-13",False)
    ]


class ChronologyTests(unittest.TestCase):
    def test_independent_known_5pct_ex_post_timestamps(self):
        z=checker.verify(price_rows(),events())
        self.assertTrue(z["chronology_invariants_passed"],z["errors"])
        self.assertEqual(z["scale_summary"]["5"]["reported_labels"],2)
        self.assertFalse(z["formal_start_alerts_restored"])
        self.assertFalse(z["historical_feature_PIT_certified"])

    def test_first_crossing_not_delayed(self):
        bad=events()
        bad[0]["confirmation_date"]="2026-01-08"
        z=checker.verify(price_rows(),bad)
        self.assertFalse(z["chronology_invariants_passed"])
        self.assertTrue(any("earlier reversal" in x["error"] or "higher high" in x["error"]
                            for x in z["errors"]))

    def test_do_not_backdate_confirmed_label_to_extreme(self):
        bad=events()
        bad[0]["confirmation_date"]="2026-01-06"
        z=checker.verify(price_rows(),bad)
        self.assertFalse(z["chronology_invariants_passed"])
        self.assertTrue(any("confirmation not later" in x["error"] for x in z["errors"]))

    def test_cannot_claim_confirmation_day_preopen(self):
        bad=events()
        bad[0]["earliest_possible_preopen_day_after_confirmation"]="2026-01-07"
        self.assertFalse(checker.verify(price_rows(),bad)["chronology_invariants_passed"])

    def test_no_future_label_extreme_from_later_day(self):
        bad=events()
        bad[0]["extreme_close"]="111"
        self.assertFalse(checker.verify(price_rows(),bad)["chronology_invariants_passed"])

    def test_no_same_direction_duplicates(self):
        bad=events()
        bad[1]["direction"]="TOP"
        bad[1]["id"]="5_TOP_2026-01-08"
        self.assertFalse(checker.verify(price_rows(),bad)["chronology_invariants_passed"])

    def test_frozen_actual_1128_price_and_58_labels_sha(self):
        root=Path(__file__).with_name("observations")
        actual=checker.audit_file_bundle(root)
        self.assertEqual(actual["status"],"ARCHIVED_OBJECTIVE_LABEL_CHRONOLOGY_VERIFIED_NOT_PIT")
        self.assertEqual(actual["observed_price_sessions"],1128)
        self.assertEqual(actual["scale_summary"]["5"]["reported_labels"],39)
        self.assertEqual(actual["scale_summary"]["9"]["reported_labels"],19)
        self.assertFalse(actual["formal_signal_allowed"])
        self.assertFalse(actual["double80_achieved"])

    def test_tampered_archived_csv_sha_is_refused(self):
        original=Path(__file__).with_name("observations")
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)
            for name in ("index_000985_prices_20220223_20261020.csv",
                         "partial_v52_derived_objective_pivots.csv",
                         "partial_v52_pivot_manifest.json"):
                (out/name).write_bytes((original/name).read_bytes())
            with (out/"partial_v52_derived_objective_pivots.csv").open("a") as fh:
                fh.write("tampered\n")
            with self.assertRaisesRegex(ValueError,"SHA"):
                checker.audit_file_bundle(out)


if __name__=="__main__":
    unittest.main()
