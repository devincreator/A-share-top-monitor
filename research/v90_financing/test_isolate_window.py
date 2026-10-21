import importlib.util
import unittest
from datetime import date,timedelta
from pathlib import Path
p=Path(__file__).with_name("isolate_window.py")
spec=importlib.util.spec_from_file_location("isolate_window",p)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def rows(n=110):
    start=date(2026,1,1)
    return [{"date":(start+timedelta(days=i)).isoformat(),
             "balance_sh_yuan":1.2e12,"balance_sz_yuan":1.3e12} for i in range(n)]
class WindowTests(unittest.TestCase):
    def test_older_anomaly_not_poison_recent_window(self):
        a=rows();a[0]["balance_sz_yuan"]=0
        z=m.isolate_financing(a,a[-1]["date"],lookback=60)
        self.assertEqual(z["status"],"CANDIDATE_WINDOW_ONLY_NOT_PIT")
        self.assertEqual(len(z["rejected"]),1)
        self.assertFalse(z["formal_signal_allowed"])
    def test_recent_anomaly_blocks(self):
        a=rows();a[-5]["balance_sz_yuan"]=0
        self.assertEqual(m.isolate_financing(a,a[-1]["date"],60)["status"],"BLOCKED_ANOMALY_IN_WINDOW")
    def test_asof_missing_blocks(self):
        a=rows();a[-1]["balance_sz_yuan"]=0
        self.assertEqual(m.isolate_financing(a,a[-1]["date"],60)["status"],"BLOCKED_ASOF_NOT_VERIFIED")
    def test_duplicate_date_blocks(self):
        a=rows();a.append(dict(a[0]))
        with self.assertRaises(ValueError):
            m.isolate_financing(a,a[-2]["date"])
if __name__=="__main__":
    unittest.main()
