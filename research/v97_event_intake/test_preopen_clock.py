import importlib.util
import unittest
from pathlib import Path

SPEC=importlib.util.spec_from_file_location("preopen_clock",Path(__file__).with_name("preopen_clock.py"))
m=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)
SHA="a"*64


def pred(day="2026-10-20",when="2026-10-20T08:50:00+08:00"):
    return {"id":"alert-001","prediction_date":day,"decision_at":when}


def rec(factor="INDEX_CLOSE",day="2026-10-19",pub="2026-10-19T17:00:00+08:00"):
    return {"factor":factor,"observation_date":day,"published_at":pub,
            "source_raw_sha256":SHA,"source_uri":"https://example.org/raw",
            "publication_provenance":"INDEPENDENTLY_VERIFIED",
            "publication_evidence_uri":"https://example.org/exchange-notice"}


class PreopenClockTests(unittest.TestCase):
    def test_strict_previous_trading_date_only(self):
        x=m.inspect_prediction(pred(),[rec()],["INDEX_CLOSE"])
        self.assertEqual(x["status"],"PREOPEN_SCHEMA_VALID_REQUIRES_SOURCE_AUTHENTICATION")
        self.assertFalse(x["formal_signal_allowed"])

    def test_same_day_daily_price_forbidden_even_before_open(self):
        x=m.inspect_prediction(pred(),[rec(day="2026-10-20",pub="2026-10-20T08:00:00+08:00")],
                               ["INDEX_CLOSE"])
        self.assertEqual(x["status"],"BLOCKED")
        self.assertIn("same-day",str(x["errors"]))

    def test_same_day_financing_forbidden(self):
        x=m.inspect_prediction(pred(),[rec("FINANCING_BALANCE","2026-10-20","2026-10-20T08:10:00+08:00")],
                               ["FINANCING_BALANCE"])
        self.assertEqual(x["status"],"BLOCKED")

    def test_claimed_final_indicator_published_before_own_market_close_is_fabricated(self):
        x=m.inspect_prediction(
            pred(),[rec(day="2026-10-19",pub="2026-10-19T10:00:00+08:00")],
            ["INDEX_CLOSE"])
        self.assertEqual(x["status"],"BLOCKED")
        self.assertIn("before its observation-day market close",str(x["errors"]))

    def test_previous_day_financing_not_released_until_after_prediction(self):
        x=m.inspect_prediction(pred(),[rec("FINANCING_BALANCE","2026-10-19","2026-10-20T09:10:00+08:00")],
                               ["FINANCING_BALANCE"])
        self.assertIn("published after",str(x["errors"]))

    def test_two_factors_one_stale_unavailable(self):
        x=m.inspect_prediction(pred(),[rec(),rec("FINANCING_BALANCE","2026-10-19","2026-10-20T09:10:00+08:00")],
                               ["INDEX_CLOSE","FINANCING_BALANCE"])
        self.assertEqual(x["factor_evidence"][0]["status"],"TIME_CONTRACT_SCHEMA_CANDIDATE")
        self.assertEqual(x["status"],"BLOCKED")

    def test_unknown_release_provenance_rejected(self):
        row=rec();row["publication_provenance"]="ASSUMED_END_OF_DAY"
        x=m.inspect_prediction(pred(),[row],["INDEX_CLOSE"])
        self.assertIn("not independently evidenced",str(x["errors"]))

    def test_naive_decision_timestamp_rejected(self):
        x=m.inspect_prediction(pred(when="2026-10-20T08:50:00"),[rec()],["INDEX_CLOSE"])
        self.assertIn("naive timestamp",str(x["errors"]))

    def test_after_open_cannot_be_preopen(self):
        x=m.inspect_prediction(pred(when="2026-10-20T09:31:00+08:00"),[rec()],["INDEX_CLOSE"])
        self.assertIn("not a before-open",str(x["errors"]))

    def test_prediction_decision_day_must_match(self):
        x=m.inspect_prediction(pred(when="2026-10-19T08:50:00+08:00"),[rec()],["INDEX_CLOSE"])
        self.assertIn("does not fall",str(x["errors"]))

    def test_missing_required_feature_does_not_pass(self):
        x=m.inspect_prediction(pred(),[rec()],["INDEX_CLOSE","C50"])
        self.assertIn("missing factor evidence",str(x["errors"]))

    def test_duplicate_source_factor_rejected(self):
        x=m.inspect_prediction(pred(),[rec(),rec()],["INDEX_CLOSE"])
        self.assertIn("duplicate factor",str(x["errors"]))

    def test_tampered_raw_hash_missing(self):
        row=rec();row["source_raw_sha256"]="invalid"
        x=m.inspect_prediction(pred(),[row],["INDEX_CLOSE"])
        self.assertIn("SHA256",str(x["errors"]))

    def test_source_from_future_rejected(self):
        x=m.inspect_prediction(pred(),[rec(day="2026-10-21",pub="2026-10-21T08:00:00+08:00")],
                               ["INDEX_CLOSE"])
        self.assertEqual(x["status"],"BLOCKED")


if __name__=="__main__":
    unittest.main()
