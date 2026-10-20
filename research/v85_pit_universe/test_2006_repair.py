import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from pilot_2006_repair import validate

class PilotTests(unittest.TestCase):
    def source(self, date='20060313', duplicate=False):
        hdr='symbol,trade_date,open,high,low,close,pct_chg,vol\n'
        rows=''.join(f'{600000+i}.SH,{date},10,11,9,10,0,123\n' for i in range(101))
        if duplicate:rows+=f'600000.SH,{date},10,11,9,10,0,123\n'
        return (hdr+rows).encode()
    def test_valid_raw_day(self):self.assertEqual(validate('20060313',self.source()),101)
    def test_wrong_day_rejected(self):
        with self.assertRaises(ValueError):validate('20060313',self.source(date='20060314'))
    def test_duplicate_rejected(self):
        with self.assertRaises(ValueError):validate('20060313',self.source(duplicate=True))

if __name__=='__main__':unittest.main()
