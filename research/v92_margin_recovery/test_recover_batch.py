import datetime as dt
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HERE=Path(__file__).parent
spec=importlib.util.spec_from_file_location("v92_recovery",HERE/"recover_batch.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def history(n=850):
    start=dt.date(2022,1,3)
    dates=[]
    d=start
    while len(dates)<n:
        if d.weekday()<5:
            dates.append(d.isoformat())
        d+=dt.timedelta(days=1)
    return {"indices":{"000985":[{"date":day,"code":"000985"} for day in dates]},
            "financing":[{"date":day,"balance_sh_yuan":1e12,"balance_sz_yuan":1e12} for day in dates]}


class FakeFrame:
    def __init__(self,rows):
        self.rows=rows
        self.columns=list(rows[0])
    def __len__(self):
        return len(self.rows)
    def to_dict(self,orient):
        assert orient=="records"
        return self.rows
    def to_csv(self,path,index=False):
        assert index is False
        Path(path).write_text(json.dumps(self.rows,ensure_ascii=False))


class FakeExchange:
    def stock_margin_sse(self,start_date,end_date):
        return FakeFrame([{"信用交易日期":start_date,"融资余额":800000000000}])
    def stock_margin_szse(self,date):
        return FakeFrame([{"融资余额":7000.56}])


class GapRecoveryTests(unittest.TestCase):
    def test_only_pinned_long_window_gaps(self):
        data=history()
        dates=[x["date"] for x in data["indices"]["000985"]]
        data["financing"]=[row for row in data["financing"] if row["date"]!=dates[-30]]
        data["financing"][-2]["balance_sz_yuan"]=0
        gaps=mod.target_gaps(data)
        self.assertEqual(len(gaps),2)
        self.assertIn(dates[-30],gaps)
        self.assertIn(data["financing"][-2]["date"],gaps)

    def test_prevent_cherry_pick_after_recent_attempt(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            day="2024-06-20"
            attempted=root/"attempts"/day
            attempted.mkdir(parents=True)
            (attempted/"1.json").write_text(json.dumps({"attempt_utc":"2026-10-21T03:00:00Z"}))
            chosen=mod.select_dates([day,"2024-06-21"],root/"records",root/"attempts",
                                     today="2026-10-22",max_dates=8,retry_days=2)
            self.assertEqual(chosen,["2024-06-21"])
            chosen=mod.select_dates([day],root/"records",root/"attempts",
                                     today="2026-10-23",max_dates=8,retry_days=2)
            self.assertEqual(chosen,[day])

    def test_success_persists_raw_once_and_still_is_not_pit(self):
        from probe_official import run_pilot
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            date="2024-06-20"
            (root/"source.json").write_text(json.dumps({"indices":{"000985":[{"date":date}]},
                                                       "financing":[]}))
            pilot=run_pilot(root/"source.json",root/"pilot",dates=[date],
                            api=FakeExchange(),sleep=lambda _:None)
            evidence=mod.append_evidence(pilot,root/"ledger",root/"pilot",
                                        run_id="1",timestamp="2026-10-21T04:00:00Z")
            self.assertEqual([x["status"] for x in evidence[0]["sources"].values()],
                             ["FIRST_SOURCE_CAPTURED","FIRST_SOURCE_CAPTURED"])
            first=root/"ledger"/"records"/date/"SZSE.json"
            meta=json.loads(first.read_text())
            self.assertFalse(meta["PIT_certified"])
            self.assertTrue(meta["display_value_not_exact_yuan"])
            self.assertFalse(meta["source_response_date_verified"])
            sha=meta["source_raw_sha256"]
            self.assertEqual(sha,hashlib.sha256(
                (root/"ledger"/"raw"/"SZSE"/(date+".csv")).read_bytes()).hexdigest())
            result=mod.append_evidence(pilot,root/"ledger",root/"pilot",
                                       run_id="2",timestamp="2026-10-22T04:00:00Z")
            self.assertEqual(result[0]["sources"]["SZSE"]["status"],"FIRST_CAPTURE_UNCHANGED")
            self.assertEqual(first.read_text(),json.dumps(meta,ensure_ascii=False,indent=2)+"\n")

    def test_revised_source_does_not_overwrite_first_capture(self):
        from probe_official import run_pilot
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);date="2024-06-20"
            (root/"source.json").write_text(json.dumps({"indices":{"000985":[{"date":date}]},
                                                       "financing":[]}))
            first=run_pilot(root/"source.json",root/"first",dates=[date],api=FakeExchange(),sleep=lambda _:None)
            mod.append_evidence(first,root/"ledger",root/"first",run_id="1",timestamp="2026-10-21T04:00:00Z")
            class RevisedExchange(FakeExchange):
                def stock_margin_szse(self,date):
                    return FakeFrame([{"融资余额":7100.56}])
            other=run_pilot(root/"source.json",root/"second",dates=[date],api=RevisedExchange(),sleep=lambda _:None)
            result=mod.append_evidence(other,root/"ledger",root/"second",
                                       run_id="2",timestamp="2026-10-22T04:00:00Z")
            self.assertEqual(result[0]["sources"]["SZSE"]["status"],
                             "SOURCE_REVISION_CONFLICT_NO_OVERWRITE")
            old=json.loads((root/"ledger"/"records"/date/"SZSE.json").read_text())
            self.assertEqual(old["balance_yuan_from_display"],"700056000000.00")

    def test_unsafe_request_size_rejected(self):
        with self.assertRaisesRegex(ValueError,"unsafe"):
            mod.select_dates([],Path("."),Path("."),today="2026-10-21",max_dates=100)


if __name__=="__main__":
    unittest.main()
