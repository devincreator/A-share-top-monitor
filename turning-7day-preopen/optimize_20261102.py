from pathlib import Path
import importlib.util,json,csv
P=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('e',P/'evaluate_baseline.py');e=importlib.util.module_from_spec(s);s.loader.exec_module(e);b=e.base
for r in b.RULES.values():r['lead']=7
D,C,V,H=b.load_sources(P/'inputs/index_000985_prices_20220223_20261020.csv',P/'inputs/partial_v52_derived_objective_pivots.csv')
PLAN={'candidates':['baseline','armed_1day','armed_3day'],'candidate_lifetime_sessions':7,'threshold_search':False,'scoring_window':7,'cooldown':'unchanged','sample_unseen':False,'PIT_certified':False}
(P/'experiment_plan_20261102.json').write_text(json.dumps(PLAN,indent=2),encoding='utf-8')
def generate(dates,closes,n):
 out=[]
 for task,r in b.RULES.items():
  armed_until=-1;last=-100000;previous=False
  for di in range(1,len(dates)):
   i=di-1;f=b.feature_at(closes,i,r);eligible=bool(f and f['eligible'])
   if eligible and not previous:armed_until=di+7
   previous=eligible
   if armed_until<di or i<n:continue
   reversal=closes[i]<closes[i-n] if r['direction']=='TOP' else closes[i]>closes[i-n]
   if reversal and di-last>r['cooldown']:
    out.append({'id':f'{task}_{dates[di]}','task':task,'date':dates[di].isoformat(),'scale':r['scale'],'direction':r['direction'],'last_observed':dates[i].isoformat()});last=di;armed_until=-1
 return sorted(out,key=lambda a:(a['date'],a['task']))
results={};events=[];periods=[('2022-2023','2022','2023'),('2024','2024','2024'),('2025-2026','2025','2026')]
for mode,n in [('baseline',0),('armed_1day',1),('armed_3day',3)]:
 if n:
  alerts=generate(D,C,n)
  for cutoff in [250,500,800]:
   prefix=generate(D[:cutoff],C[:cutoff],n);full=[a for a in alerts if a['date']<D[cutoff].isoformat()];assert prefix==full,'Future dependence'
 else:alerts,_=b.generate_alerts(D,C)
 details,metrics=b.event_replay(alerts,V,D)
 split={}
 for title,start,end in periods:
  split[title]={}
  for task,r in b.RULES.items():
   aa=[a for a in details if a['task']==task and start<=a['date'][:4]<=end]
   tp=sum(a['event_result']=='TP' for a in aa);fp=sum(a['event_result']=='FP' for a in aa)
   # Count matched pivots by pivot year separately; boundary alerts remain assigned globally.
   mature=[p for p in V if p['scale']==r['scale'] and p['direction']==r['direction'] and p['first_segment_left_censored']=='false' and D.index(__import__('datetime').date.fromisoformat(p['confirmation_date']))+b.MATURITY_BUFFER<len(D) and start<=p['date'][:4]<=end]
   hit_ids={a['matched_pivot_id'] for a in details if a['task']==task and a['event_result']=='TP'}
   hit=sum(p['id'] in hit_ids for p in mature)
   split[title][task]={'tp_alert_year':tp,'fp':fp,'precision':tp/(tp+fp) if tp+fp else None,'hit_pivot_year':hit,'mature_pivots':len(mature),'recall':hit/len(mature) if mature else None}
 results[mode]={'metrics':metrics,'chronological_diagnostics_not_blind_validation':split}
 events.extend({'candidate':mode,**a} for a in details)
report={'plan':PLAN,'source_hashes':H,'results':results,'future_prefix_checks_passed':6,'production_changed':False,'note':'Fixed structural probes, no fitted parameters. Historical period diagnostics are not independent out-of-sample results. Existing 140-session maturity buffer retained.'}
(P/'optimization_20261102.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
with (P/'optimization_events_20261102.csv').open('w',encoding='utf-8-sig',newline='') as f:
 fields=sorted(set().union(*(a.keys() for a in events)));w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(events)
for name,x in results.items():print(name,{k:(round(v['precision']*100,1) if v['precision'] is not None else None,round(v['recall']*100,1) if v['recall'] is not None else None,v['tp'],v['fp']) for k,v in x['metrics'].items()})
