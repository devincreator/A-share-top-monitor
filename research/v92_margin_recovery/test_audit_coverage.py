import datetime as dt
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HERE=Path(__file__).parent
spec=importlib.util.spec_from_file_location("v92_coverage",HERE/"audit_coverage.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def example_inputs():
    dates=[]
    day=dt.date(2022,1,3)
    while len(dates)<830:
        if day.weekday()<5:
            dates.append(day.isoformat())
        day+=dt.timedelta(days=1)
    hole=dates[-5]
    return {"indices":{"000985":[{"date":day,"code":"000985"} for day in dates]},
            "financing":[{"date":day,"balance_sh_yuan":1e12,"balance_sz_yuan":1e12}
                         for day in dates if day!=hole]},hole


def write_source(root,day,exchange):
    if exchange=="SSE":
        csvtext="信用交易日期,融资余额\n"+day.replace("-","")+",801234000000\n"
        yuan="801234000000";unit="CNY";provenance="RESPONSE_DATE_MATCHED"
        has_response_date=True;rounded=False
    else:
        csvtext="融资余额,融资买入额\n7192.86,200.00\n"
        yuan="719286000000.00";unit="100M_CNY";provenance="REQUEST_PARAMETER_ONLY"
        has_response_date=False;rounded=True
    file=Path(root)/"raw"/exchange/(day+".csv")
    meta=Path(root)/"records"/day/(exchange+".json")
    file.parent.mkdir(parents=True,exist_ok=True)
    meta.parent.mkdir(parents=True,exist_ok=True)
    raw=csvtext.encode()
    file.write_bytes(raw)
    doc={"date":day,"exchange":exchange,"source_raw_path":str(file),
         "source_raw_sha256":hashlib.sha256(raw).hexdigest(),
         "source_unit":unit,"balance_yuan_from_display":yuan,
         "date_provenance":provenance,"source_response_date_verified":has_response_date,
         "display_value_not_exact_yuan":rounded,
         "formal_signal_allowed":False,"PIT_certified":False}
    meta.write_text(json.dumps(doc))


class CoverageTests(unittest.TestCase):
    def test_both_original_sources_verified_and_not_pit(self):
        data,hole=example_inputs()
        with tempfile.TemporaryDirectory() as d:
            for ex in ("SSE","SZSE"):
                write_source(d,hole,ex)
            result=mod.audit_all(data,d)
            self.assertEqual(result["original_source_gap_or_invalid_days"],1)
            self.assertEqual(result["raw_source_both_exchanges_sha_valid_days"],1)
            self.assertFalse(result["finance_growth63_prior756_rank_certified"])
            self.assertFalse(result["formal_signal_allowed"])

    def test_raw_source_tamper_is_reported_not_certified(self):
        data,hole=example_inputs()
        with tempfile.TemporaryDirectory() as d:
            for ex in ("SSE","SZSE"):
                write_source(d,hole,ex)
            src=Path(d)/"raw"/"SZSE"/(hole+".csv")
            src.write_text(src.read_text().replace("7192.86","8192.86"))
            result=mod.audit_all(data,d)
            self.assertEqual(result["status"],"SOURCE_INTEGRITY_FAILED")
            self.assertEqual(result["raw_source_both_exchanges_sha_valid_days"],0)
            self.assertEqual(len(result["source_integrity_failures"]),1)

    def test_sse_response_date_mismatch_blocks(self):
        data,hole=example_inputs()
        with tempfile.TemporaryDirectory() as d:
            write_source(d,hole,"SSE")
            src=Path(d)/"raw"/"SSE"/(hole+".csv")
            meta=Path(d)/"records"/hole/"SSE.json"
            raw=src.read_bytes().replace(hole.replace("-","").encode(),b"20200101")
            src.write_bytes(raw)
            doc=json.loads(meta.read_text())
            doc["source_raw_sha256"]=hashlib.sha256(raw).hexdigest()
            meta.write_text(json.dumps(doc))
            result=mod.audit_all(data,d)
            self.assertEqual(result["status"],"SOURCE_INTEGRITY_FAILED")

    def test_no_sources_stays_unobserved(self):
        data,hole=example_inputs()
        with tempfile.TemporaryDirectory() as d:
            r=mod.audit_all(data,d)
            self.assertEqual(r["raw_source_not_both_observed_days"],1)
            self.assertEqual(r["raw_source_both_exchanges_sha_valid_days"],0)


if __name__=="__main__":
    unittest.main()
