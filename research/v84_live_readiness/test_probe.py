import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from daily_probe import validate

class ProbeTests(unittest.TestCase):
    def sample(self, duplicate=False):
        h='symbol,trade_date,open,high,low,close,pct_chg,vol\n'
        s=''.join(f'{600001+i}.SH,20261020,10,11,9,10.5,5,100\n' for i in range(100))
        if duplicate:s+='600001.SH,20261020,10,11,9,10,0,100\n'
        return (h+s).encode()
    def test_valid(self):
        d=validate(self.sample(),'20261020')
        self.assertEqual(d['unique_sh_sz_traded_bars'],100)
        self.assertFalse(d['observed_traded_breadth_is_PIT_certified'])
    def test_duplicates_fail_closed(self):
        with self.assertRaises(ValueError):
            validate(self.sample(duplicate=True),'20261020')
    def test_wrong_date_fails_closed(self):
        with self.assertRaises(ValueError):
            validate(self.sample(),'20261019')

if __name__=='__main__':unittest.main()
