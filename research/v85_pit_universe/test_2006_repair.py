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


class ExceptionalIPOTests(unittest.TestCase):
    @staticmethod
    def fake(symbol='002051.SZ', close='31.97'):
        hdr='symbol,trade_date,open,high,low,close,pre_close,pct_chg,vol\n'
        rows=''.join(f'{600000+i}.SH,20060619,10,11,9,10,9.5,0,123\n' for i in range(101))
        rows+=f'{symbol},20060619,17.11,50.0,15.5,{close},7.4,332.03,451453.87\n'
        return (hdr+rows).encode()
    def test_documented_ipo_only(self):
        self.assertEqual(validate('20060619',self.fake()),102)
    def test_other_symbol_still_rejected(self):
        with self.assertRaises(ValueError):validate('20060619',self.fake(symbol='002052.SZ'))
    def test_mutated_ipo_bar_rejected(self):
        with self.assertRaises(ValueError):validate('20060619',self.fake(close='40'))

if __name__=='__main__':unittest.main()
