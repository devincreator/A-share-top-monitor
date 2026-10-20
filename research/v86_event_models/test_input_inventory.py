import importlib.util
import tempfile
import unittest
from pathlib import Path

P = Path(__file__).with_name("input_inventory.py")
spec = importlib.util.spec_from_file_location("input_inventory", P)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class InputInventoryTest(unittest.TestCase):
    def test_missing_inputs_block(self):
        with tempfile.TemporaryDirectory() as d:
            r = module.inspect_inputs(Path(d)/"a.csv", Path(d)/"p.csv")
            self.assertEqual(r["status"], "BLOCKED")
            self.assertFalse(r["formal_backtest_allowed"])

    def test_valid_schema_is_not_certification(self):
        with tempfile.TemporaryDirectory() as d:
            a, p = Path(d)/"a.csv", Path(d)/"p.csv"
            a.write_text("date,direction,scale,event_id\n20200101,TOP,5,a1\n")
            p.write_text("turning_date,direction,scale,pivot_id,confirmation_date\n20200102,TOP,5,p1,20200112\n")
            r = module.inspect_inputs(a, p)
            self.assertEqual(r["status"], "INPUT_SCHEMA_READY_NOT_YET_AUDITED")
            self.assertFalse(r["formal_backtest_allowed"])

    def test_missing_column_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            a, p = Path(d)/"a.csv", Path(d)/"p.csv"
            a.write_text("date,direction,scale\n20200101,TOP,5\n")
            p.write_text("turning_date,direction,scale,pivot_id,confirmation_date\n20200102,TOP,5,p1,20200112\n")
            r = module.inspect_inputs(a, p)
            self.assertEqual(r["status"], "BLOCKED")
            self.assertIn("event_id", str(r["issues"]))


if __name__ == "__main__":
    unittest.main()
