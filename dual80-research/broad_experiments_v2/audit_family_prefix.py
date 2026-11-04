from pathlib import Path
import subprocess,csv,json
P=Path(__file__).resolve().parent;reports=[]
def read(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
for family in ['gaussian','knn50']:
 folder=P/family;out=folder/'prefix_2500';script=P/(family+'_run.py')
 cp=subprocess.run(['python','-B',str(script),'--limit','2500','--out',str(out)],capture_output=True,text=True)
 if cp.returncode:raise RuntimeError(cp.stderr)
 full={(r['task'],r['group'],r['date']):r for r in read(folder/'scores.csv')};partial=read(out/'scores.csv');maximum=0
 for x in partial:
  old=full[x['task'],x['group'],x['date']];assert all(old[k]==x[k] for k in x if k!='score');maximum=max(maximum,abs(float(old['score'])-float(x['score'])))
 assert maximum<=1e-12,(family,maximum)
 fr=json.loads((folder/'result.json').read_text(encoding='utf-8'));pr=json.loads((out/'result.json').read_text(encoding='utf-8'));folds={(x['task'],x['year'],x['group'],x['policy']):x for x in fr['annual_selection']}
 assert all(folds[x['task'],x['year'],x['group'],x['policy']]==x for x in pr['annual_selection'])
 end=max(x['date'] for x in partial);fe=read(folder/'events.csv');pe=read(out/'events.csv');a={(x['task'],x['configuration'],x['date']) for x in fe if x['date']<=end};b={(x['task'],x['configuration'],x['date']) for x in pe};assert a==b
 for task,configs in fr['results'].items():
  for config,v in configs.items():
   ev=[x for x in fe if x['task']==task and x['configuration']==config];assert sum(x['status']=='TP' for x in ev)==v['tp'];assert sum(x['status']=='FP' for x in ev)==v['fp'];assert sum(x['status']=='PENDING' for x in ev)==v['pending'];assert v['tp']+v['fn']==v['mature_pivots'];hits=[x['pivot_date'] for x in ev if x['status']=='TP'];assert len(hits)==len(set(hits))
 reports.append({'family':family,'prefix_rows':2500,'scores_checked':len(partial),'annual_choice_rows_checked':len(pr['annual_selection']),'alarm_rows_checked':len(b),'maximum_score_delta':maximum,'score_tolerance':1e-12,'exact_threshold_and_alarm_dates_unchanged':True})
 print('PASS',family,reports[-1],flush=True)
(P/'additional_pipeline_prefix_audits.json').write_text(json.dumps(reports,indent=2),encoding='utf-8')
