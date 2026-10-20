import importlib.util
import tempfile
import unittest
from pathlib import Path

SOURCE = Path(__file__).with_name("input_inventory.py")
spec = importlib.util.spec_from_file_location("input_inventory", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

P = "date,close\n2020-01-01,100\n2020-01-02,101\n2020-01-03,99\n"
A = "id,date,scale,direction,event_type\na1,2020-01-01,5,TOP,FORMAL_START\n"
B = "id,date,scale,direction\np1,2020-01-03,5,TOP\n"

class InputInventoryTests(unittest.TestCase):
    def inputs(self, root, a=A, b=B, p=P):
        files = [Path(root)/n for n in ("alerts.csv", "pivots.csv", "prices.csv")]
        for file, text in zip(files, (a,b,p)):
            file.write_text(text)
        return files

    def test_missing_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            r=module.inspect_inputs(Path(d)/"a",Path(d)/"b",Path(d)/"c")
            self.assertEqual(r["status"],"BLOCKED")
            self.assertFalse(r["formal_backtest_allowed"])

    def test_canonical_schema_matches_event_audit(self):
        with tempfile.TemporaryDirectory() as d:
            r=module.inspect_inputs(*self.inputs(d))
            self.assertEqual(r["status"],"INPUT_SCHEMA_READY_NOT_YET_AUDITED")
            self.assertFalse(r["formal_backtest_allowed"])

    def test_legacy_aliases_are_research_only(self):
        with tempfile.TemporaryDirectory() as d:
            a="event_id,date,scale,direction\na1,20200101,5,TOP\n"
            b="pivot_id,turning_date,confirmation_date,scale,direction\np1,20200103,20200104,5,TOP\n"
            r=module.inspect_inputs(*self.inputs(d,a,b))
            self.assertEqual(r["status"],"INPUT_SCHEMA_READY_NOT_YET_AUDITED")
            self.assertEqual(r["files"]["pivots"]["schema"],"LEGACY")

    def test_nonformal_not_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            r=module.inspect_inputs(*self.inputs(d,A.replace("FORMAL_START","ACTIVE")))
            self.assertEqual(r["status"],"BLOCKED")

    def test_missing_calendar_date_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            r=module.inspect_inputs(*self.inputs(d,b=B.replace("2020-01-03","2020-01-06")))
            self.assertEqual(r["status"],"BLOCKED")

    def test_duplicate_event_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            r=module.inspect_inputs(*self.inputs(d,a=A+"a1,2020-01-02,5,TOP,FORMAL_START\n"))
            self.assertEqual(r["status"],"BLOCKED")

    def test_confirmation_before_pivot_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            b="pivot_id,turning_date,confirmation_date,scale,direction\np1,20200103,20200101,5,TOP\n"
            r=module.inspect_inputs(*self.inputs(d,b=b))
            self.assertEqual(r["status"],"BLOCKED")

if __name__ == "__main__":
    unittest.main()
