from pathlib import Path
import ast,csv,json,hashlib,math
import numpy as np
P=Path(__file__).resolve().parent;old=P.parent/'run.py';nodes=[]
for n in ast.parse(old.read_text(encoding='utf-8-sig')).body:
 if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='folds' for t in n.targets):break
 if isinstance(n,(ast.Import,ast.ImportFrom,ast.Assign,ast.FunctionDef)):nodes.append(n)
m={'__file__':str(old)};exec(compile(ast.Module(body=nodes,type_ignores=[]),str(old),'exec'),m)
D,C,A,S=m['D'],np.array(m['C']),np.array(m['A']),np.array(m['S']);N=len(D);LABELS=m['LABELS']
N=2500;D=D[:N];C=C[:N];A=A[:N];S=S[:N];LABELS={scale:[g for g in gg if g[1]<N] for scale,gg in LABELS.items()};P=P/'prefix_2500';P.mkdir(exist_ok=True)
PLAN={'model':'L2 logistic regression, penalty 10, fixed; six continuous price features','features':['return3_scaled','return20_scaled','change_in_return3_scaled','distance_to_20day_high_scaled','distance_to_20day_low_scaled','position63_continuous'],'thresholds':[.05,.1,.2,.3,.4,.5],'training':'Annual refit; fit data available at previous calendar year start; preceding year validation for threshold; test year strictly later','label_policy':'Confirmation+140 by cutoff; negative windows end no later than latest mature pivot of either direction for this scale','alert_policy':'One live ledger per task, no year reset; valid seven sessions, rearm after below threshold and expiry; never rescind','score':'Continuous global same-direction same-scale one-to-one; unresolved tail PENDING','source_sha256':m['PLAN']['source_sha256'],'PIT_certified':False,'blind_sample':False,'production_changed':False}
(P/'plan.json').write_text(json.dumps(PLAN,indent=2),encoding='utf-8')
def features(closes):
 x=np.full((len(closes),6),np.nan)
 for di in range(252,len(closes)):
  i=di-1;cs=closes;rets=np.diff(np.log(cs[i-20:i+1]));v=max(float(np.std(rets,ddof=1)),.001)
  r3=np.log(cs[i]/cs[i-3]);r20=np.log(cs[i]/cs[i-20]);prev=np.log(cs[i-3]/cs[i-6]);lo=min(cs[i-62:i+1]);hi=max(cs[i-62:i+1])
  x[di]=[r3/v,r20/(v*np.sqrt(20)),(r3-prev)/v,np.log(cs[i]/max(cs[i-19:i+1]))/v,np.log(cs[i]/min(cs[i-19:i+1]))/v,(cs[i]-lo)/(hi-lo) if hi>lo else .5]
 return x
X=features(C)
for cut in [600,1500,2500]:assert np.allclose(features(C[:cut])[252:],X[252:cut],equal_nan=True)
def pool(scale,side,cutoff):
 known=[g for g in LABELS[scale] if g[1]+140<=cutoff]
 if not known:return np.array([],int),np.array([]),np.array([])
 end=max(g[0] for g in known)-7;ix=np.arange(252,end+1);y=np.zeros(len(ix));w=np.ones(len(ix))/7
 for p,c,direction in known:
  if direction!=side:continue
  mask=(ix>=p-7)&(ix<p);k=int(mask.sum())
  if k:y[mask]=1;w[mask]=1/k
 return ix,y,w
sigmoid=lambda z:1/(1+np.exp(-np.clip(z,-35,35)))
def fit(ix,y,w):
 if len(ix)<100 or y.sum()<7 or (1-y).sum()<7:return None
 mu=X[ix].mean(0);sd=X[ix].std(0);sd[sd<1e-8]=1;z=np.column_stack([np.ones(len(ix)),np.clip((X[ix]-mu)/sd,-8,8)]);b=np.zeros(7);b[0]=np.log((y.sum()+.5)/(len(y)-y.sum()+.5));pen=np.diag([0]+[10]*6)
 for _ in range(40):
  pred=sigmoid(z@b);grad=z.T@(w*(pred-y))+pen@b;H=z.T@((w*pred*(1-pred))[:,None]*z)+pen+np.eye(7)*1e-8;step=np.linalg.solve(H,grad);step=np.clip(step,-1,1);b-=step
  if max(abs(step))<1e-6:break
 assert np.isfinite(b).all()
 return mu,sd,b

def predict(model,ix):
 mu,sd,b=model;return sigmoid(np.column_stack([np.ones(len(ix)),np.clip((X[ix]-mu)/sd,-8,8)])@b)
def emit(days,probs,threshold):
 out=[];active_until=-1;armed=True
 for i,p in zip(days,probs):
  if p<threshold and i>active_until:armed=True
  if i>active_until and armed and p>=threshold:out.append(int(i));active_until=i+7;armed=False
 return out
all_events=[];folds=[];scores={};metrics={}
for scale in [5,9]:
 for side in ['TOP','BOTTOM']:
  task=f'{scale}_{side}';ledger=[];daily=[];active=-1;armed=True
  for year in range(2016,2027):
   test=np.array([i for i,d in enumerate(D) if d.startswith(str(year))],int)
   if not len(test):continue
   cutoff=test[0]-1;starts=[i for i,d in enumerate(D) if d.startswith(str(year-1))];fitcut=(starts[0]-1) if starts else -1
   ix,y,w=pool(scale,side,fitcut);model=fit(ix,y,w)
   vi,vy,vw=pool(scale,side,cutoff);vi=vi[vi>fitcut]
   if model is None or not len(vi):folds.append({'task':task,'year':year,'state':'INSUFFICIENT_MATURE_TRAINING'});continue
   vp=predict(model,vi);goals=[g for g in LABELS[scale] if g[2]==side and g[1]+140<=cutoff and vi[0]+7<=g[0]<=vi[-1]+7]
   opts=[]
   for th in PLAN['thresholds']:
    va=emit(vi,vp,th);va=[a for a in va if a>=vi[0]+7];met,_=m['score'](va,goals);ok=len(goals)>=5 and len(va)>=5;opts.append((min(met['precision'] or 0,met['recall'] or 0) if ok else -1,met['precision'] or 0,th,met))
   best=max(opts);th=best[2] if best[0]>=0 else .2
   # Refit on all labels available before test, preserving the threshold chosen with earlier-fit validation.
   ti,ty,tw=pool(scale,side,cutoff);live=fit(ti,ty,tw)
   if live is None:continue
   probs=predict(live,test)
   for i,p in zip(test,probs):
    if p<th and i>active:armed=True
    if i>active and armed and p>=th:ledger.append(int(i));active=int(i)+7;armed=False
    daily.append({'task':task,'date':D[i],'last_input_date':D[i-1],'probability_score':float(p),'threshold':th})
   folds.append({'task':task,'year':year,'state':'RESEARCH_PREDICTIONS','training_samples':len(ti),'positive_days':int(ty.sum()),'latest_training_decision':D[ti[-1]],'validation_selected_threshold':th,'validation_objective':best[0],'test_labels_used_for_selection':False})
  # Mature frontier prevents unresolved objectives from becoming false negatives/positives.
  known=[g for g in LABELS[scale] if g[1]+140<N]
  frontier=max(g[0] for g in known);start=next((i for i,d in enumerate(D) if d>='2016-01-01'),N)
  aa=[a for a in ledger if start<=a and a+7<=frontier];gg=[g for g in known if g[2]==side and start+7<=g[0]<=frontier]
  # Match by dynamic programming to independently check the ordered greedy assignment.
  met,pairs=m['score'](aa,gg);matched=dict(pairs);met['pending_alerts']=len(ledger)-len(aa);met['frontier']=D[frontier];met['alerts_total']=len(ledger)
  metrics[task]=met
  for a in ledger:all_events.append({'task':task,'date':D[a],'result':'TP' if a in matched else 'FP' if a in aa else 'PENDING','pivot_date':D[matched[a]] if a in matched else ''})
  scores[task]=daily
  baseline_alarms=[a for a in m['ALL'][scale,side,'baseline'] if start<=a and a+7<=frontier]
  baseline_metrics,_=m['score'](baseline_alarms,gg)
  met['baseline_same_opportunities']=baseline_metrics
  assert len(matched)==len(set(matched.values()))
  assert all(1<=pp-aa<=7 for aa,pp in pairs)
  assert all(D[tirow['date'] and D.index(tirow['date'])-1]==tirow['last_input_date'] for tirow in daily)

report={'plan':PLAN,'metrics':metrics,'folds':folds,'feature_prefix_tests':3,'double80':all(v['precision'] is not None and v['precision']>=.8 and v['recall']>=.8 for v in metrics.values()),'warning':'Research only. Scores not certified calibrated probabilities. Mature-frontier scoring differs from old annual exclusions; do not compare old headline metrics directly.'}
(P/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
for name,rs in [('events.csv',all_events),('scores.csv',[r for rs in scores.values() for r in rs])]:
 with (P/name).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
print(json.dumps(metrics,indent=2))
