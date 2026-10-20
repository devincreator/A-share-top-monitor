import unittest
import sys
from pathlib import Path
from datetime import date,timedelta
sys.path.insert(0,str(Path(__file__).parent))
from event_audit import audit

DATES=[date(2020,1,1)+timedelta(days=i) for i in range(220)]
PRICES=[{'date':d.isoformat(),'close':str(100-i*.1)} for i,d in enumerate(DATES)]

def evt(i,scale='5',direction='TOP',id='X'):
    return {'date':DATES[i].isoformat(),'scale':scale,'direction':direction,'id':id}

class EventTests(unittest.TestCase):
    def test_one_pivot_cannot_fill_two_alarms(self):
        x=audit([evt(140,id='a'),evt(145,id='b')],[evt(146,id='p')],PRICES)['tasks']['5_TOP']
        self.assertEqual((x['tp'],x['fp'],x['fn']),(1,1,0))
    def test_windows_5_and_9(self):
        a=[evt(130,'5',id='a'),evt(130,'9',id='b')]
        p=[evt(141,'5',id='p'),evt(141,'9',id='q')]
        x=audit(a,p,PRICES)['tasks']
        self.assertEqual((x['5_TOP']['tp'],x['9_TOP']['tp']),(0,1))
    def test_same_day_not_early_warning(self):
        x=audit([evt(150,id='a')],[evt(150,id='p')],PRICES)['tasks']['5_TOP']
        self.assertEqual((x['tp'],x['fn']),(0,1))
    def test_missing_calendar_event_rejected(self):
        with self.assertRaises(ValueError):
            audit([{'id':'a','scale':'5','direction':'TOP','date':'2019-01-01'}],[],PRICES)
    def test_symmetric_bottom(self):
        x=audit([evt(160,direction='BOTTOM',id='a')],[evt(161,direction='BOTTOM',id='p')],PRICES)['tasks']['5_BOTTOM']
        self.assertEqual((x['tp'],x['fp'],x['fn']),(1,0,0))
    def test_no_future_in_regime(self):
        x=audit([evt(150,id='a')],[],PRICES)['tasks']['5_TOP']['events'][0]['market_regime_at_alert']
        future_mod=PRICES[:151]+[dict(v,close='100000') for v in PRICES[151:]]
        y=audit([evt(150,id='a')],[],future_mod)['tasks']['5_TOP']['events'][0]['market_regime_at_alert']
        self.assertEqual(x,y)

if __name__=='__main__':unittest.main()
