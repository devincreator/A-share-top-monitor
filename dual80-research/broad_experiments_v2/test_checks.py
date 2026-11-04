from pathlib import Path
import subprocess,csv,json,hashlib,collections
P=Path(__file__).resolve().parent
before=hashlib.sha256((P/'result.json').read_bytes()).hexdigest()
subprocess.run(['python','-B',str(P/'run.py')],check=True,stdout=subprocess.DEVNULL)
assert before==hashlib.sha256((P/'result.json').read_bytes()).hexdigest(),'Control prefix fix unexpectedly changed full-data metrics'
subprocess.run(['python','-B',str(P/'run.py'),'--limit','2500','--out',str(P/'prefix_2500')],check=True,stdout=subprocess.DEVNULL)
read=lambda p:list(csv.DictReader(p.open(encoding='utf-8-sig')))
full={(r['task'],r['group'],r['date']):r for r in read(P/'scores.csv')};partial=read(P/'prefix_2500/scores.csv')
maximum_score_delta=0.0
for x in partial:
 original=full[x['task'],x['group'],x['date']]
 assert all(x[k]==original[k] for k in x if k!='score')
 delta=abs(float(x['score'])-float(original['score']));maximum_score_delta=max(maximum_score_delta,delta)
 assert delta<=1e-12,'Material prefix score change'

r=json.loads((P/'result.json').read_text(encoding='utf-8'));pr=json.loads((P/'prefix_2500/result.json').read_text(encoding='utf-8'));ff={(x['task'],x['year'],x['group'],x['policy']):x for x in r['annual_selection']}
assert all(ff[x['task'],x['year'],x['group'],x['policy']]==x for x in pr['annual_selection'])
end=max(x['date'] for x in partial);fe=read(P/'events.csv');pe=read(P/'prefix_2500/events.csv')
a={(x['task'],x['configuration'],x['date']) for x in fe if x['date']<=end};b={(x['task'],x['configuration'],x['date']) for x in pe};assert a==b
assert len({(x['task'],x['configuration'],x['date']) for x in fe})==len(fe)
for task,configs in r['results'].items():
 for config,v in configs.items():
  ev=[x for x in fe if x['task']==task and x['configuration']==config];ct=collections.Counter(x['status'] for x in ev)
  assert ct['TP']==v['tp'] and ct['FP']==v['fp'] and ct['PENDING']==v['pending']
  assert v['tp']+v['fn']==v['mature_pivots']
  hits=[x['pivot_date'] for x in ev if x['status']=='TP'];assert len(hits)==len(set(hits))
  if v['precision'] is None:assert not v['dual80']
report={'prefix_rows':2500,'scores_checked':len(partial),'annual_model_threshold_selection_rows_checked':len(pr['annual_selection']),'issued_alarm_rows_checked':len(b),'full_run_event_accounting_rows':len(fe),'feature_prefix_checks':r['feature_prefix_checks'],'all_equal_with_numerical_tolerance':True,'score_absolute_tolerance':1e-12,'maximum_score_delta':maximum_score_delta,'threshold_choices_and_issuance_exactly_equal':True,'corrected_test_harness_issue':'Original-rule control initially retained indices beyond requested prefix; filtered to actual prefix. Full-data result SHA unchanged. This was a truncation-harness bug, not evidence the model read future prices.','historical_publication_time_certified':False,'independent_blind_test':False}
(P/'pipeline_prefix_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report))
