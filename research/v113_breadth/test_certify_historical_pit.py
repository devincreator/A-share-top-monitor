import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from certify_historical_pit import audit
class CertTests(unittest.TestCase):
 def test_missing_publication_proof_blocked(self):
  dates=[{"source_trade_date":"2026-%02d-01"%((i%12)+1)} for i in range(12)]
  with self.assertRaisesRegex(ValueError,"BAD_FROZEN_CALENDAR"):audit(dates,[])
 def test_claimed_delays_not_certification(self):
  days=[{"source_trade_date":"2022-%02d-%02d"%(m,day)} for m in range(2,12) for day in range(1,30)]
  days=days[:1129]
  with self.assertRaisesRegex(ValueError,"BAD_FROZEN_CALENDAR"):audit(days,[])
if __name__=="__main__":unittest.main()
