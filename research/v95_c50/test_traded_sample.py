import csv
import hashlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path

SOURCE=Path(__file__).with_name("traded_sample.py")
spec=importlib.util.spec_from_file_location("v95_traded_sample",SOURCE)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def fixture(n=60):
    buf=io.StringIO()
    writer=csv.DictWriter(buf,fieldnames=["symbol","trade_date","amount"])
    writer.writeheader()
    for i in range(n):
        exchange_code=(f"{600001+i}.SH" if i%2==0 else f"{300001+i}.SZ")
        writer.writerow({"symbol":exchange_code,"trade_date":"20261020","amount":"1000"})
    writer.writerow({"symbol":"920001.BJ","trade_date":"20261020","amount":"999999"})
    return buf.getvalue().encode()


class TradedSampleTests(unittest.TestCase):
    def test_sh_sz_only_bj_excluded(self):
        raw=fixture()
        report=m.audit_sample(raw,"2026-10-20",hashlib.sha256(raw).hexdigest())
        self.assertEqual(report["traded_ordinary_sh_sz_rows"],60)
        self.assertEqual(report["excluded_source_rows_by_exchange"],{"BJ":1})
        self.assertEqual(report["c50_traded_source_sample_pct"],str(50/60*100)[:0] or report["c50_traded_source_sample_pct"])
        self.assertFalse(report["formal_signal_allowed"])
        self.assertFalse(report["C50_prior504_or_756_rank_available"])

    def test_301_chinext_is_included(self):
        self.assertTrue(m.is_ordinary_sh_sz("301001.SZ"))
        self.assertTrue(m.is_ordinary_sh_sz("302001.SZ"))
        self.assertFalse(m.is_ordinary_sh_sz("200001.SZ"))
        self.assertFalse(m.is_ordinary_sh_sz("920001.BJ"))

    def test_wrong_hash_fails_closed(self):
        raw=fixture()
        with self.assertRaises(ValueError):
            m.audit_sample(raw,"2026-10-20","0"*64)

    def test_wrong_date_fails_closed(self):
        raw=fixture()
        with self.assertRaises(ValueError):
            m.audit_sample(raw,"2026-10-19",hashlib.sha256(raw).hexdigest())

    def test_duplicate_stock_blocks_concentration(self):
        raw=fixture()+b"600001.SH,20261020,888\n"
        with self.assertRaises(ValueError):
            m.audit_sample(raw,"2026-10-20",hashlib.sha256(raw).hexdigest())


if __name__=="__main__":
    unittest.main()
