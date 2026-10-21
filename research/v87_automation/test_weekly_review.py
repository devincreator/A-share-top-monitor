import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SOURCE = Path(__file__).with_name("weekly_review.py")
spec = importlib.util.spec_from_file_location("weekly_review", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class MonthlyCheckTests(unittest.TestCase):
    def fixture(self, root):
        r = Path(root)
        for f in ("research/status", "research/v84_live_readiness", "data"):
            (r/f).mkdir(parents=True, exist_ok=True)
        (r/"research/status/quality_gates.json").write_text(json.dumps({
            "spec":{"new_forward_unseen_validation":False},
            "versions":{"V85_2006":{"status":"RAW_241_241_VERIFIED_NOT_PIT"}},
            "data_quality":{"2005_asof_listing_universe_independently_verified":False,
                            "2005_suspension_vs_source_gap_resolved":False}}))
        (r/"data/latest_state.json").write_text(json.dumps({
            "asof":"2026-09-21","data_status":"price_core_verified_partial",
            "latest_formal_signals":{}}))
        (r/"data/latest_verified_market.json").write_text(json.dumps({
            "market_date":"2026-10-08","model_date":"2026-08-04",
            "complete_model_recalculated":False}))
        src = Path(__file__).parents[1]/"v84_live_readiness/readiness.py"
        (r/"research/v84_live_readiness/readiness.py").write_bytes(src.read_bytes())
        return r

    def test_stale_inputs_do_not_pretend_to_be_current(self):
        with tempfile.TemporaryDirectory() as d:
            x = module.report_on(self.fixture(d),"2026-10-20",
                    inventory_fn=lambda *args:{"status":"BLOCKED","issues":["missing event records"]})
            self.assertFalse(x["formal_signals_generated"])
            self.assertFalse(x["gates"]["current_full_model"]["passed"])
            self.assertFalse(x["gates"]["2005_listing_suspension_PIT"]["passed"])
            self.assertFalse(x["gates"]["formal_double80"]["passed"])
            self.assertTrue(x["gates"]["2006_raw_integrity"]["passed"])
            self.assertEqual(x["window"]["status"],"RESEARCH_RUNNING")

    def test_end_does_not_imply_model_success(self):
        with tempfile.TemporaryDirectory() as d:
            x = module.report_on(self.fixture(d),"2027-04-21",
                    inventory_fn=lambda *args:{"status":"BLOCKED","issues":[]})
            self.assertEqual(x["window"]["status"],"ENDED")
            self.assertFalse(x["gates"]["prospective_frozen_sample"]["passed"])

    def test_separate_raw_observation_never_promotes_formal_model(self):
        with tempfile.TemporaryDirectory() as d:
            root=self.fixture(d)
            ledger=root/"research/v88_daily_observations/ledger"
            ledger.mkdir(parents=True)
            (ledger/"2026-10-20.json").write_text(json.dumps({
                "observation_date":"2026-10-20",
                "source_format_verified":True,
                "source_raw_sha256":"source-verified-only",
                "traded_sh_sz_records":5217,
                "raw_traded_advance_share":0.65804102}))
            x=module.report_on(root,"2026-10-21",
                    inventory_fn=lambda *args:{"status":"BLOCKED","issues":[]})
            self.assertEqual(x["research_observed_raw_market"]["asof"],"2026-10-20")
            self.assertFalse(x["research_observed_raw_market"]["is_formal_model_input"])
            self.assertFalse(x["gates"]["current_full_model"]["passed"])

if __name__ == "__main__":
    unittest.main()
