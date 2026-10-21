import importlib.util
import unittest
from datetime import date, timedelta
from pathlib import Path

SOURCE = Path(__file__).with_name("isolate_window.py")
spec = importlib.util.spec_from_file_location("v90_isolate", SOURCE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def sample(n=850):
    start = date(2022, 1, 3)
    dates = []
    d = start
    while len(dates) < n:
        if d.weekday() < 5:
            dates.append(d.isoformat())
        d += timedelta(days=1)
    index = [{"date": d, "code": "000985"} for d in dates]
    finance = [{"date": d, "balance_sh_yuan": 1.2e12,
                "balance_sz_yuan": 1.3e12} for d in dates]
    return dates, index, finance


class TestPinnedTradingCalendar(unittest.TestCase):
    def test_complete_windows_never_prove_pit(self):
        dates, index, finance = sample()
        got = mod.audit_financing(finance, index, dates[-1])
        self.assertEqual(got["status"], "ALL_WINDOWS_SCHEMA_VALID_NOT_PIT")
        self.assertTrue(got["windows"]["finance_growth63_prior756_rank"]["window_complete"])
        self.assertFalse(got["formal_signal_allowed"])
        self.assertFalse(got["finance_publication_timestamp_verified"])

    def test_old_zero_blocks_820_but_not_recent_253(self):
        dates, index, finance = sample()
        finance[-500]["balance_sz_yuan"] = 0.0
        got = mod.audit_financing(finance, index, dates[-1])
        self.assertEqual(got["status"], "RECENT_WINDOW_CANDIDATE_LONG_FACTOR_BLOCKED")
        self.assertTrue(got["windows"]["finance_recent252"]["window_complete"])
        self.assertFalse(got["windows"]["finance_growth63_prior756_rank"]["window_complete"])
        self.assertEqual(got["windows"]["finance_growth63_prior756_rank"]["invalid_balance_count"], 1)

    def test_missing_day_cannot_be_ignored(self):
        dates, index, finance = sample()
        del finance[-9]
        got = mod.audit_financing(finance, index, dates[-1])
        recent = got["windows"]["finance_growth63"]
        self.assertFalse(recent["window_complete"])
        self.assertEqual(recent["missing_session_count"], 1)
        self.assertEqual(got["status"], "BLOCKED_FINANCING_RECENT_WINDOW")

    def test_asof_financing_zero_blocks_recent(self):
        dates, index, finance = sample()
        finance[-1]["balance_sh_yuan"] = 0
        got = mod.audit_financing(finance, index, dates[-1])
        self.assertEqual(got["status"], "BLOCKED_FINANCING_RECENT_WINDOW")
        self.assertEqual(got["windows"]["finance_growth63"]["invalid_dates"], [dates[-1]])

    def test_duplicate_financing_rejected(self):
        dates, index, finance = sample()
        finance.append(dict(finance[-2]))
        with self.assertRaisesRegex(ValueError, "duplicate financing date"):
            mod.audit_financing(finance, index, dates[-1])

    def test_off_calendar_index_bad(self):
        dates, index, finance = sample()
        index.append({"code": "000985", "date": "2025-01-04"})
        with self.assertRaisesRegex(ValueError, "weekend index"):
            mod.audit_financing(finance, index, dates[-1])

    def test_short_index_history_blocks_long_window(self):
        dates, index, finance = sample(200)
        got = mod.audit_financing(finance, index, dates[-1])
        self.assertEqual(got["windows"]["finance_growth63_prior756_rank"]["status"],
                         "BLOCKED_INSUFFICIENT_INDEX_HISTORY")

    def test_invalid_number_kept_not_interpolated(self):
        dates, index, finance = sample()
        finance[-2]["balance_sh_yuan"] = "NaN"
        got = mod.audit_financing(finance, index, dates[-1])
        self.assertEqual(got["windows"]["finance_growth63"]["invalid_balance_count"], 1)
        self.assertEqual(got["windows"]["finance_growth63"]["status"], "BLOCKED_SOURCE_GAPS_OR_ANOMALIES")


if __name__ == "__main__":
    unittest.main()
