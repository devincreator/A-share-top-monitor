from pathlib import Path
import csv,json,hashlib
import numpy as np
import run as base
P=Path(__file__).resolve().parent
PLAN={'hypothesis':'Fixed 0.10 fails to rearm when almost every day is above it; compare causal rank threshold without refitting','decision_before_replay':True,'attempt_informed_by_previous_results':True,'blind_test':False,'lookback':252,'minimum_previous_scores':126,'quantile':.90,'threshold_source':'Strictly prior out-of-time emitted scores; current score excluded','threshold_search':False,'lead':[0,6],'policy':'crossing with D..D+6 lock; rearm below that days historical threshold after lock','same_inputs_models_labels_cohort':True,'all_candidates_reported':True,'production_changed':False}
plan=P/'rank_replay_plan.json'
if plan.exists():assert json.loads(plan.read_text(encoding='utf-8'))==PLAN
else:plan.write_text(json.dumps(PLAN,ensure_ascii=False,indent=2),encoding='utf-8')
scores=list(csv.DictReader((P/'scores.csv').open(encoding='utf-8-sig')))
def replay(limit):
 metrics=[];events=[];thresholds=[];front={s:min(max(g[0] for g in base.LABELS[v][s] if g[1]+140<limit) for v in base.LABELS) for s in [5,9]}
 for variant in base.LABELS:
  for s in [5,9]:
   for side in ['TOP','BOTTOM']:
    task=f'{s}_{side}'
    for group in base.GROUPS:
     ss=sorted([r for r in scores if r['label']==variant and r['task']==task and r['group']==group and base.pos[r['date']]<limit],key=lambda r:r['date']);hist=[];ledger=[];st={'until':-1,'armed':True}
     for r in ss:
      i=base.pos[r['date']];v=float(r['score']);past=[p for j,p in hist if i-252<=j<i]
      if len(past)>=126:
       t=float(np.quantile(past,.90));thresholds.append({'label':variant,'task':task,'group':group,'date':r['date'],'threshold':t,'prior_scores':len(past),'last_threshold_input':base.D[hist[-1][0]]})
       if i>st['until'] and v<t:st['armed']=True
       if i>st['until'] and st['armed'] and v>=t:ledger.append(i);st.update(until=i+6,armed=False)
      hist.append((i,v));hist=[(j,p) for j,p in hist if j>=i-252]
     met,pairs,aa=base.evaluate(ledger,base.LABELS[variant][s],side,front[s],limit);metrics.append(dict(label=variant,task=task,group=group+'__past_rank90',**met));matched=dict(pairs)
     for a in ledger:
      if a<base.START:continue
      events.append({'label':variant,'task':task,'group':group+'__past_rank90','date':base.D[a],'status':'TP' if a in matched else 'FP' if a in aa else 'PENDING','pivot_date':base.D[matched[a]] if a in matched else ''})
 return metrics,events,thresholds
metrics,events,tt=replay(base.N);pm,pe,pt=replay(2500);keys=lambda rr:{(r['label'],r['task'],r['group'],r['date']) for r in rr}
assert keys(pe)==keys([r for r in events if r['date']<=base.D[2499]])
lookup={(r['label'],r['task'],r['group'],r['date']):r for r in tt};assert all(lookup[r['label'],r['task'],r['group'],r['date']]==r for r in pt)
assert all(r['last_threshold_input']<r['date'] for r in tt)
for name,rr in [('rank_metrics.csv',metrics),('rank_events.csv',events),('rank_thresholds.csv',tt)]:
 with (P/name).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
result={'plan':PLAN,'metrics':metrics,'prefix_threshold_count':len(pt),'prefix_alarm_count':len(pe),'prefix_pass':True,'dual80_cases':sum(m['dual80'] for m in metrics),'note':'This is a new registered research attempt prompted by inspected results, not untouched confirmation. Rank thresholds do not calibrate probabilities.'};(P/'rank_result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False,indent=2))
