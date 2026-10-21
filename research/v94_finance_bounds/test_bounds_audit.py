import csv
import datetime as dt
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HERE=Path(__file__).parent
spec=importlib.util.spec_from_file_location("v94_finance_bounds",HERE/"bounds_audit.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def sample(n=830):
    days=[]
    day=dt.date(2022,1,3)
    while len(days)<n:
        if day.weekday()<5:
            days.append(day.isoformat())
        day+=dt.timedelta(days=1)
    gap=days[-120]
    return {"indices":{"000985":[{"date":d,"code":"000985"} for d in days]},
            "financing":[{"date":d,"balance_sh_yuan":"740311931631",
                          "balance_sz_yuan":"664954000000"}
                         for d in days if d!=gap]},gap


def write_exchange(root,date,exchange,*,tamper=False):
    base=Path(root)
    path=base/"raw"/exchange/(date+".csv")
    meta=base/"records"/date/(exchange+".json")
    path.parent.mkdir(parents=True,exist_ok=True)
    meta.parent.mkdir(parents=True,exist_ok=True)
    if exchange=="SSE":
        raw=("信用交易日期,融资余额\n"+date.replace("-","")+",740311931631\n").encode()
        unit="CNY";proof="RESPONSE_DATE_MATCHED";source_verified=True;rounded=False
        money="740311931631"
    else:
        raw=b"\xe8\x9e\x8d\xe8\xb5\x84\xe4\xbd\x99\xe9\xa2\x9d\n6649.54\n"
        unit="100M_CNY";proof="REQUEST_PARAMETER_ONLY";source_verified=False;rounded=True
        money="664954000000.00"
    path.write_bytes(raw)
    meta.write_text(json.dumps({
        "date":date,"exchange":exchange,
        "source_raw_path":str(path),"source_raw_sha256":hashlib.sha256(raw).hexdigest(),
        "source_unit":unit,"source_response_date_verified":source_verified,
        "date_provenance":proof,"display_value_not_exact_yuan":rounded,
        "balance_yuan_from_display":money,
        "PIT_certified":False,"formal_signal_allowed":False
    }))
    if tamper:path.write_bytes(raw+b"x")


class V94Tests(unittest.TestCase):
    def test_rounded_interval_is_only_conditional(self):
        b=m.precision_bounds("6649.54")
        self.assertEqual(b["conditional_low_yuan_inclusive"],"664953500000.00")
        self.assertEqual(b["conditional_high_yuan_exclusive"],"664955000000.00")
        self.assertFalse(b["exact_yuan_certified"])

    def test_source_day_never_promoted(self):
        data,date=sample()
        with tempfile.TemporaryDirectory() as root:
            write_exchange(root,date,"SSE")
            write_exchange(root,date,"SZSE")
            x=m.audit_all(data,root)
            self.assertEqual(x["target_missing_or_invalid_days"],1)
            self.assertEqual(x["exchange_raw_SHA_and_schema_both_pass_days"],1)
            self.assertEqual(x["days"][0]["status"],"ROUNDED_INTERVAL_ONLY_NOT_PIT")
            self.assertEqual(x["days"][0]["sh_sz_conditional_low_yuan"],"1405265431631.00")
            self.assertFalse(x["formal_signal_allowed"])

    def test_tampered_source_hash_blocks(self):
        data,date=sample()
        with tempfile.TemporaryDirectory() as root:
            write_exchange(root,date,"SSE")
            write_exchange(root,date,"SZSE",tamper=True)
            x=m.audit_all(data,root)
            self.assertEqual(x["days"][0]["status"],"BLOCKED_SOURCE_INTEGRITY")
            self.assertEqual(x["exchange_raw_SHA_and_schema_both_pass_days"],0)

    def test_cross_source_disagreement_remains_blocked(self):
        data,date=sample()
        data["financing"].append({"date":date,"balance_sh_yuan":"740311931631",
                                  "balance_sz_yuan":"720000000000"})
        with tempfile.TemporaryDirectory() as root:
            write_exchange(root,date,"SSE")
            write_exchange(root,date,"SZSE")
            result=m.audit_day(root,date,data["financing"][-1])
            self.assertEqual(result["status"],"BLOCKED_CROSS_SOURCE_DISAGREEMENT")
            self.assertFalse(result["formal_signal_allowed"])

    def test_publication_time_missing_and_naive_rejected(self):
        self.assertFalse(m.published_before(None,"2026-10-20T15:00:00+08:00"))
        self.assertFalse(m.published_before("2026-10-20T14:30:00",
                                            "2026-10-20T15:00:00+08:00"))
        self.assertFalse(m.published_before("2026-10-21T07:00:00+08:00",
                                            "2026-10-20T15:00:00+08:00"))
        self.assertTrue(m.published_before("2026-10-20T14:30:00+08:00",
                                           "2026-10-20T15:00:00+08:00"))

    def test_landing_page_not_equivalent_to_exchange_value(self):
        self.assertFalse(m.published_before("unverified","2026-10-20T15:00:00+08:00"))


if __name__=="__main__":
    unittest.main()
