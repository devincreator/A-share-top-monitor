from pathlib import Path
import csv,json,statistics
P=Path(r'E:\Codex\量化\dual80-research/label_clock_v4');R=P.parent.parent
D=[r['date'] for r in csv.DictReader((R/'turning-research-canonical/tables/research_inputs.csv').open(encoding='utf-8-sig'))];pos={d:i for i,d in enumerate(D)};labels=list(csv.DictReader((R/'turning-label-comparison/all_labels.csv').open(encoding='utf-8-sig')));scores=list(csv.DictReader((P/'scores.csv').open(encoding='utf-8-sig')));metrics=list(csv.DictReader((P/'metrics.csv').open(encoding='utf-8-sig')));events=list(csv.DictReader((P/'events.csv').open(encoding='utf-8-sig')))
# AUC uses average ranks for ties; dates overlap, so diagnostic only, not independent events.
def auc(v):
 v=sorted(v);n1=sum(y for s,y in v);n0=len(v)-n1
 if not n1 or not n0:return None
 total=0;i=0
 while i<len(v):
  j=i+1
  while j<len(v) and v[j][0]==v[i][0]:j+=1
  total+=sum(y for s,y in v[i:j])*(i+1+j)/2;i=j
 return (total-n1*(n1+1)/2)/(n1*n0)
rr=[]
for m in metrics:
 if m['group']=='original_rule':continue
 scale,side=m['task'].split('_');front=pos[m['frontier']];ss=[r for r in scores if all(r[k]==m[k] for k in ['label','task','group']) and '2016-01-01'<=r['date'] and pos[r['date']]+6<=front];goals=[l for l in labels if l['definition']==m['label'] and l['scale']==scale and l['direction']==side and D[next(i for i,d in enumerate(D) if d>='2016-01-01')+7]<=l['pivot_date']<=m['frontier']];positive={i for l in goals for i in range(pos[l['pivot_date']]-6,pos[l['pivot_date']]+1)};byi={pos[r['date']]:float(r['score']) for r in ss};vals=[(v,int(i in positive)) for i,v in byi.items()];covered=sum(any(byi.get(i,-1)>=.1 for i in range(pos[l['pivot_date']]-6,pos[l['pivot_date']]+1)) for l in goals)
 runs=[];run=0;previous=-2
 for i,v in sorted(byi.items()):
  if i!=previous+1:
   if run:runs.append(run)
   run=0
  if v>=.1:run+=1
  elif run:runs.append(run);run=0
  previous=i
 if run:runs.append(run)
 rr.append({k:m[k] for k in ['label','task','group']}|{'scored_days':len(vals),'positive_days':sum(y for s,y in vals),'auc':auc(vals),'days_above_threshold':sum(v>=.1 for v,y in vals),'fraction_above_threshold':sum(v>=.1 for v,y in vals)/len(vals) if vals else None,'longest_above_threshold_run':max(runs,default=0),'targets_with_any_above_threshold_day':covered,'targets':len(goals),'oracle_gate_recall_not_achievable_precision':covered/len(goals) if goals else None})
(P/'score_diagnostics.json').write_text(json.dumps(rr,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps([r for r in rr if r['label']!='close'],ensure_ascii=False,indent=2))
