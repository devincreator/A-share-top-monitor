import importlib.util
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

SCRIPT=Path(__file__).with_name("probe_official.py")
spec=importlib.util.spec_from_file_location("v91_exchange_pilot",SCRIPT)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class FakeFrame:
    def __init__(self, rows):
        self.rows=rows
        self.columns=list(rows[0]) if rows else []
    def __len__(self):
        return len(self.rows)
    def to_dict(self,orient):
        assert orient=="records"
        return self.rows
    def to_csv(self,path,index=False):
        assert index is False
        Path(path).write_text(json.dumps(self.rows,ensure_ascii=False))


class FakeAPI:
    def stock_margin_sse(self,start_date,end_date):
        assert start_date==end_date
        return FakeFrame([{"信用交易日期":start_date,"融资余额":"987654321000"}])
    def stock_margin_szse(self,date):
        return FakeFrame([{"融资余额":"6649.54"}])


class OfficialExchangePilotTests(unittest.TestCase):
    def test_sse_balance_yuan_and_response_date(self):
        row=mod.parse_summary("SSE",FakeFrame([{
            "信用交易日期":"20240808","融资余额":987654321000}]),"2024-08-08")
        self.assertEqual(row["balance_yuan_from_source"],"987654321000")
        self.assertTrue(row["source_response_date_verified"])
        self.assertFalse(row["formal_signal_allowed"])

    def test_szse_balance_100m_yuan_not_exact(self):
        row=mod.parse_summary("SZSE",FakeFrame([{
            "融资余额":6649.54}]),"2024-08-08")
        self.assertEqual(Decimal(row["balance_yuan_from_source"]),Decimal("664954000000"))
        self.assertFalse(row["source_response_date_verified"])
        self.assertTrue(row["rounded_balance_not_exact_yuan"])

    def test_conflicting_date_rejected(self):
        with self.assertRaisesRegex(ValueError,"response date disagrees"):
            mod.parse_summary("SSE",FakeFrame([{"信用交易日期":"20240807",
                "融资余额":"987654321000"}]),"2024-08-08")

    def test_no_zero_silent_imputation(self):
        with self.assertRaises(ValueError):
            mod.parse_summary("SZSE",FakeFrame([{"融资余额":0}]),"2024-08-08")

    def test_aggregated_stock_rows_not_misread_as_market_total(self):
        with self.assertRaisesRegex(ValueError,"exactly one"):
            mod.parse_summary("SZSE",FakeFrame([{"融资余额":1000},{"融资余额":800}]),"2024-08-08")

    def test_jin10_rounding_and_invalid_zero(self):
        source=mod.parse_summary("SZSE",FakeFrame([{"融资余额":"6649.54"}]),"2024-08-08")
        matched=mod.compare_jin10(source,{"balance_sz_yuan":664954100000})
        self.assertEqual(matched["status"],"CONSISTENT_WITH_SOURCE_ROUNDING")
        wrong=mod.compare_jin10(source,{"balance_sz_yuan":0})
        self.assertEqual(wrong["status"],"JIN10_INVALID_SOURCE_VALUE")

    def test_real_source_attempts_stay_research_only(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            inputs={"indices":{"000985":[{"date":"2024-08-08"}]},"financing":[{
                "date":"2024-08-08","balance_sh_yuan":987654321000,
                "balance_sz_yuan":0}]}
            (root/"inputs.json").write_text(json.dumps(inputs))
            audit=mod.run_pilot(root/"inputs.json",root/"raw",
                                dates=["2024-08-08"],api=FakeAPI(),sleep=lambda _:None)
            self.assertEqual(audit["exchange_source_success_count"],2)
            self.assertFalse(audit["formal_signal_allowed"])
            self.assertFalse(audit["PIT_certified"])
            self.assertTrue((root/"raw/szse_2024-08-08_raw.csv").exists())

    def test_non_index_date_does_not_provoke_request(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/"inputs.json").write_text(json.dumps({"indices":{"000985":[]},"financing":[]}))
            audit=mod.run_pilot(root/"inputs.json",root/"raw",
                                dates=["2024-08-08"],api=FakeAPI(),sleep=lambda _:None)
            self.assertEqual(audit["days"][0]["status"],"REJECTED_NOT_INDEX_DAY")
            self.assertEqual(audit["exchange_source_success_count"],0)


if __name__=="__main__":
    unittest.main()
