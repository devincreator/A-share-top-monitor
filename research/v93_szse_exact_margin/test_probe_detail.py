import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HERE=Path(__file__).parent
spec=importlib.util.spec_from_file_location("v93_detail",HERE/"probe_detail.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class Frame:
    def __init__(self,rows):
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


def detail_rows(amount=7000000000):
    return Frame([{"证券代码":f"{i:06d}","融资余额":amount} for i in range(1,101)])


class FakeAPI:
    def stock_margin_detail_szse(self,date):
        return detail_rows()
    def stock_margin_szse(self,date):
        return Frame([{"融资余额":7000.00}])


class DetailTests(unittest.TestCase):
    def test_decimal_sum_exact_yuan(self):
        a=mod.sum_detail_yuan(detail_rows())
        self.assertEqual(a["detail_balance_sum_yuan"],"700000000000")
        self.assertEqual(a["distinct_security_codes"],100)

    def test_duplicate_security_code_fails(self):
        f=detail_rows()
        f.rows[-1]["证券代码"]=f.rows[0]["证券代码"]
        with self.assertRaisesRegex(ValueError,"duplicate"):
            mod.sum_detail_yuan(f)

    def test_source_not_full_market_must_fail_match(self):
        d=mod.sum_detail_yuan(detail_rows(amount=6000000000))
        summary={"balance_yuan_from_source":"700000000000.00"}
        result=mod.compare_sources(d,summary,{"balance_sz_yuan":700000000000})
        self.assertEqual(result["status"],"DETAIL_NOT_WHOLE_MARKET_SUMMARY")
        self.assertFalse(result["detail_equals_Jin10_exactly"])
        self.assertFalse(result["PIT_certified"])

    def test_matching_detail_remains_non_pit(self):
        d=mod.sum_detail_yuan(detail_rows())
        x=mod.compare_sources(d,{"balance_yuan_from_source":"700000000000.00"},
                              {"balance_sz_yuan":700000000000})
        self.assertEqual(x["status"],"DETAIL_CONSISTENT_WITH_SUMMARY_DISPLAY_PRECISION")
        self.assertTrue(x["detail_equals_Jin10_exactly"])
        self.assertFalse(x["formal_signal_allowed"])

    def test_full_pilot_writes_raw_and_never_trading_signal(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);date="2026-10-20"
            (root/"source.json").write_text(json.dumps({
                "indices":{"000985":[{"code":"000985","date":date}]},
                "financing":[{"date":date,"balance_sh_yuan":1e12,"balance_sz_yuan":7e11}]}))
            res=mod.pilot(root/"source.json",root/"result",
                          dates=[date],api=FakeAPI())
            self.assertEqual(res["dates"][0]["status"],"DETAIL_AGGREGATE_COMPUTED_RESEARCH_ONLY")
            self.assertFalse(res["dates"][0]["PIT_certified"])
            self.assertTrue((root/"result"/f"szse_detail_{date}_raw.csv").exists())

    def test_no_market_date_no_request(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/"source.json").write_text(json.dumps({
                "indices":{"000985":[]},"financing":[]}))
            res=mod.pilot(root/"source.json",root/"result",dates=["2024-08-08"],api=FakeAPI())
            self.assertEqual(res["dates"][0]["status"],"BLOCKED")


if __name__=="__main__":
    unittest.main()
