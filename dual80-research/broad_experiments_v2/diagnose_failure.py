from pathlib import Path
import ast,json,csv,collections,math,statistics
import numpy as np
P=Path(__file__).resolve().parent;source=P.parent/'run.py';nodes=[]
for n in ast.parse(source.read_text(encoding='utf-8-sig')).body:
 if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='folds' for t in n.targets):break
 if isinstance(n,(ast.Import,ast.ImportFrom,ast.Assign,ast.FunctionDef)):nodes.append(n)
b={'__file__':str(source)};exec(compile(ast.Module(body=nodes,type_ignores=[]),str(source),'exec'),b)
D=b['D'];pos={d:i for i,d in enumerate(D)};r=json.loads((P/'result.json').read_text(encoding='utf-8'))
def auc(y,s):
 y=np.array(y,bool);s=np.array(s,float);order=np.argsort(s,kind='stable');ranks=np.empty(len(s));start=0
 while start<len(s):
  end=start+1
  while end<len(s) and s[order[end]]==s[order[start]]:end+=1
  ranks[order[start:end]]=(start+1+end)/2;start=end
 n1=int(y.sum());n0=len(y)-n1
 return float((ranks[y].sum()-n1*(n1+1)/2)/(n1*n0)) if n1 and n0 else None
scores=list(csv.DictReader((P/'scores.csv').open(encoding='utf-8-sig')));groups=collections.defaultdict(list)
for x in scores:
 if x['date']>='2016-01-01':groups[x['task'],x['group']].append(x)
rank_metrics=[];annual=[]
for (task,group),rs in groups.items():
 scale=int(task.split('_')[0]);side=task.split('_')[1];front=pos[r['results'][task]['original_rule']['frontier']];start=pos[next(d for d in D if d>='2016-01-01')]
 goals=[g[0] for g in b['LABELS'][scale] if g[2]==side and g[1]+140<len(D) and start+7<=g[0]<=front]
 rs=[x for x in rs if pos[x['date']]+7<=front];yy=[any(1<=p-pos[x['date']]<=7 for p in goals) for x in rs];ss=[float(x['score']) for x in rs]
 metric={'task':task,'feature_group':group,'first':rs[0]['date'],'last':rs[-1]['date'],'days':len(rs),'positive_days':sum(yy),'positive_day_rate':sum(yy)/len(yy),'daily_AUC_not_event_accuracy':auc(yy,ss)}
 if task=='5_BOTTOM' and group=='price_style':
  ix=np.argsort(-np.array(ss),kind='stable')[:math.ceil(len(ss)*.1)];metric['top_decile_days']=len(ix);metric['top_decile_positive_fraction']=float(np.mean(np.array(yy)[ix]));metric['top_decile_daily_positive_recall']=float(np.sum(np.array(yy)[ix])/sum(yy))
  for year in sorted({x['date'][:4] for x in rs}):
   index=[i for i,x in enumerate(rs) if x['date'].startswith(year)];annual.append({'year':year,'AUC':auc([yy[i] for i in index],[ss[i] for i in index]),'days':len(index),'positive_days':sum(yy[i] for i in index)})
 rank_metrics.append(metric)
seen=set();ages=[];support=[];small=[];tail=[]
for fold in r['annual_selection']:
 task=fold['task'];year=fold['year'];key=task,year
 if key not in seen:
  seen.add(key);cutoff=next(i for i,d in enumerate(D) if d.startswith(str(year)))-1;last=pos[fold['latest_train_decision']];scale=int(task.split('_')[0]);side=task.split('_')[1]
  mature=[g for g in b['LABELS'][scale] if g[1]+140<=cutoff];events=[g for g in mature if g[2]==side and g[0]>252 and g[0]-7<=last]
  ages.append({'task':task,'year':year,'cutoff':D[cutoff],'latest_training_day':D[last],'lag_sessions':cutoff-last,'independent_positive_events':len(events)})
  if len(events)<5:small.append(ages[-1])
  if events:
   g=events[-1];overlap=[i for i in range(max(252,g[0]-7),g[0]) if i<=last]
   if len(overlap)<7:tail.append({'task':task,'year':year,'latest_event':D[g[0]],'training_positive_days_for_this_event':len(overlap)})
 if fold['live_selected'] and year>=2016:support.append({'task':task,'year':year,'validation_pivots':fold['validation_pivots'],'validation_alerts':fold['validation_alerts']})
report={'daily_rank_diagnostics':rank_metrics,'five_bottom_style_annual_auc':annual,'training_age':ages,'median_training_frontier_lag_sessions':statistics.median(x['lag_sessions'] for x in ages),'max_training_frontier_lag_sessions':max(x['lag_sessions'] for x in ages),'small_independent_event_training':small,'truncated_latest_event_windows':tail,'selected_validation_support':support,'selected_validation_rows_with_at_most_5_pivots':sum(x['validation_pivots']<=5 for x in support),'note':'Daily ranking uses overlapping positive windows and is not event precision/recall or a blind-test significance result.'}
(P/'failure_diagnostics.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'AUC_price':[{k:x[k] for k in ['task','daily_AUC_not_event_accuracy']} for x in rank_metrics if x['feature_group']=='price'],'top_decile':[x for x in rank_metrics if x['task']=='5_BOTTOM' and x['feature_group']=='price_style'],'median_age':report['median_training_frontier_lag_sessions'],'max_age':report['max_training_frontier_lag_sessions'],'validation_small':report['selected_validation_rows_with_at_most_5_pivots'],'validation_total':len(support),'2026_training':[x for x in ages if x['year']==2026],'early_small':small[:2]},indent=2))
