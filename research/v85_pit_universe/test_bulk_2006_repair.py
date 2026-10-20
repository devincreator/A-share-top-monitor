import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from bulk_2006_repair import select_batch

class BatchTests(unittest.TestCase):
    def test_all_unique_missing_days(self):
        all_days=sum((select_batch(i) for i in range(1,18)),[])
        self.assertEqual(len(all_days),85)
        self.assertEqual(len(set(all_days)),85)
        self.assertEqual(all_days,sorted(all_days))
    def test_limit_batch_size(self):
        self.assertTrue(all(len(select_batch(i))==5 for i in range(1,18)))
    def test_out_of_range(self):
        with self.assertRaises(ValueError):select_batch(18)

if __name__=='__main__':unittest.main()
