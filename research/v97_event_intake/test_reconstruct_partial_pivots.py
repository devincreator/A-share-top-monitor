import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path

HERE=Path(__file__).parent
spec=importlib.util.spec_from_file_location("partial_v52",HERE/"reconstruct_partial_pivots.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def rows(closes):
    from datetime import date,timedelta
    d=date(2026,1,5)
    dates=[]
    while len(dates)<len(closes):
        if d.weekday()<5:
            dates.append(d.isoformat())
        d+=timedelta(days=1)
    return [{"date":days,"close":float(price)} for days,price in zip(dates,closes)]


class RealSourceLabelRuleTests(unittest.TestCase):
    def test_first_event_is_left_censored_and_next_is_alternating(self):
        values=rows([100,104,103,98,94,95,100,104])
        events=m.label_one(values,"5",.05)
        self.assertGreaterEqual(len(events),2)
        self.assertEqual(events[0]["direction"],"TOP")
        self.assertEqual(events[0]["date"],values[1]["date"])
        self.assertEqual(events[0]["confirmation_date"],values[3]["date"])
        self.assertEqual(events[0]["first_segment_left_censored"],"true")
        self.assertEqual(events[1]["direction"],"BOTTOM")
        self.assertEqual(events[1]["date"],values[4]["date"])
        self.assertEqual(events[1]["first_segment_left_censored"],"false")
        self.assertEqual(events[0]["earliest_possible_preopen_day_after_confirmation"],values[4]["date"])

    def test_equal_extreme_keeps_first_date(self):
        events=m.label_one(rows([100,104,104,98,94]),"5",.05)
        self.assertEqual(events[0]["date"],rows([100,110,110,104,100])[1]["date"])

    def test_future_prices_cannot_change_previously_confirmed_labels(self):
        p=rows([100,105,100,94,95,98,104,108,100])
        existing=m.label_one(p,"5",.05)
        # Append with new strictly later observation dates.
        from datetime import date,timedelta
        end=date.fromisoformat(p[-1]["date"])
        longer=p.copy()
        for c in [101,105,99,100]:
            end+=timedelta(days=1)
            while end.weekday()>=5:end+=timedelta(days=1)
            longer.append({"date":end.isoformat(),"close":float(c)})
        later=m.label_one(longer,"5",.05)
        for before,after in zip(existing,later):
            for key in ("id","date","scale","direction","confirmation_date"):
                self.assertEqual(before[key],after[key])
        # Next-session metadata for a confirmation on the last supplied day
        # can be filled only once a NEW later index session is observed.

    def test_price_calendar_violations_block(self):
        data={"indices":{"000985":[{"code":"000985","date":"2026-10-20",
             "close":100}] * 800}}
        with self.assertRaises(ValueError):
            m.index_prices(data,"2026-10-20")

    def test_append_only_evidence_cannot_be_revised(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"objective.csv"
            self.assertEqual(m.append_only(path,b"a,b\n1,2\n"),"FIRST_CAPTURE_SAVED")
            self.assertEqual(m.append_only(path,b"a,b\n1,2\n"),"UNCHANGED")
            with self.assertRaises(ValueError):
                m.append_only(path,b"a,b\n3,4\n")

    def test_csv_has_hashed_deterministic_output(self):
        raw=m.csv_bytes(["date","close"],rows([100,99,98,95]))
        self.assertIn(b"date,close\n",raw)
        self.assertEqual(raw,m.csv_bytes(["date","close"],rows([100,99,98,95])))

if __name__=="__main__":
    unittest.main()
