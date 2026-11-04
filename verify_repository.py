from pathlib import Path
import json,hashlib,csv,math,ast
P=Path(__file__).resolve().parent
m=json.loads((P/'repository_manifest.json').read_text(encoding='utf-8'))
for x in m['files']:
 f=P/x['path'];assert f.is_file(),x['path'];assert hashlib.sha256(f.read_bytes()).hexdigest()==x['sha256'],x['path']
rows=list(csv.DictReader((P/'turning-research-canonical/tables/research_inputs.csv').open(encoding='utf-8-sig')))
assert len(rows)==3659 and len({r['date'] for r in rows})==3659
assert (rows[0]['date'],rows[-1]['date'])==('2011-08-02','2026-08-25')
for r in rows:
 for k,v in r.items():
  if k!='date':assert math.isfinite(float(v)) and float(v)>0,(r['date'],k)
labels=list(csv.DictReader((P/'turning-label-comparison/all_labels.csv').open(encoding='utf-8-sig')));assert len(labels)==443
contract=json.loads((P/'ACTIVE_RESEARCH_CONTRACT.json').read_text(encoding='utf-8'))
assert contract['user_confirmed_window']['minimum_lead_sessions']==0 and contract['user_confirmed_window']['maximum_lead_sessions']==6
assert not (P/'research').exists()
workflows=list((P/'.github/workflows').glob('*.yml'));assert len(workflows)==1 and workflows[0].name=='verify-research.yml'
assert 'schedule:' not in workflows[0].read_text(encoding='utf-8')
for f in P.rglob('*.py'):
 if '.git' not in f.parts:ast.parse(f.read_text(encoding='utf-8-sig'),filename=str(f))
for name,key in [('result.json','passed_dual80'),('rank_result.json','dual80_cases')]:assert json.loads((P/'dual80-research/label_clock_v4'/name).read_text(encoding='utf-8'))[key]==0
print(json.dumps({'verified_files':len(m['files']),'retained_original_files':m['retained_original_files'],'main_table_rows':len(rows),'all_share_labels':len(labels),'workflows':1,'scheduled_workflows':0,'dual80_achieved':False},ensure_ascii=False))
