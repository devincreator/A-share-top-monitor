from pathlib import Path
import json,hashlib,csv,math
P=Path(__file__).resolve().parent
m=json.loads((P/'upload_manifest.json').read_text(encoding='utf-8'))
for r in m['files']:
 f=P/r['path'];assert f.is_file(),r['path'];data=f.read_bytes();assert len(data)==r['bytes'],r['path'];assert hashlib.sha256(data).hexdigest()==r['sha256'],r['path']
rr=list(csv.DictReader((P/'turning-research-canonical/tables/research_inputs.csv').open(encoding='utf-8-sig')))
assert len(rr)==3659 and len({r['date'] for r in rr})==3659
assert rr[0]['date']=='2011-08-02' and rr[-1]['date']=='2026-08-25'
for r in rr:
 for k in ['all_a_close','hs300_close','zz1000_close','turnover','turnover_rate','financing_balance']:assert math.isfinite(float(r[k])) and float(r[k])>0,(r['date'],k)
ll=list(csv.DictReader((P/'turning-label-comparison/all_labels.csv').open(encoding='utf-8-sig')));assert len(ll)==443
v4=json.loads((P/'dual80-research/label_clock_v4/result.json').read_text(encoding='utf-8'));rank=json.loads((P/'dual80-research/label_clock_v4/rank_result.json').read_text(encoding='utf-8'));assert v4['passed_dual80']==0 and rank['dual80_cases']==0
print(json.dumps({'verified_original_files':len(m['files']),'original_bytes':sum(r['bytes'] for r in m['files']),'main_table_dates':len(rr),'all_share_labels':len(ll),'dual80_achieved':False,'note':'Integrity checks only; does not certify PIT or rerun models.'},ensure_ascii=False))
