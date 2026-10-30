"""Verify the archived data without provider credentials or third-party packages."""
from pathlib import Path
from decimal import Decimal
import csv,hashlib,json
ROOT=Path(__file__).resolve().parent

def main():
 manifest=json.loads((ROOT/'upload_manifest.json').read_text(encoding='utf-8'))
 for item in manifest['files']:
  f=ROOT/item['path']
  assert f.is_file(),f'Missing: {item["path"]}'
  assert f.stat().st_size==item['bytes'],f'Size mismatch: {item["path"]}'
  assert hashlib.sha256(f.read_bytes()).hexdigest()==item['sha256'],f'Hash mismatch: {item["path"]}'
 path=ROOT/'turning-research-canonical/tables/research_inputs.csv'
 rows=list(csv.DictReader(path.open(encoding='utf-8-sig')))
 assert len(rows)==3659 and len({r['date'] for r in rows})==3659
 assert rows[0]['date']=='2011-08-02' and rows[-1]['date']=='2026-08-25'
 for r in rows:
  for k,v in r.items():
   if k!='date':assert Decimal(v).is_finite() and Decimal(v)>0,(r['date'],k)
 components=list(csv.DictReader((ROOT/'turning-research-canonical/tables/turnover_rate_recomputed.csv').open(encoding='utf-8-sig')))
 assert len(components)==3659
 for r in components:
  assert Decimal(r['official_volume_shares'])/Decimal(r['float_a_shares'])*100==Decimal(r['turnover_rate_pct']),r['date']
 print(f'PASS: {len(manifest["files"])} file hashes; 3659 complete dates; 3659 turnover recomputations. Research only, not PIT certification.')
if __name__=='__main__':main()
