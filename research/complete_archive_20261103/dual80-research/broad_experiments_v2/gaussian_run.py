"""Bounded research experiment: six feature families x two alert policies.
No test-period outcomes are used to choose thresholds or the live candidate.
"""
from pathlib import Path
import ast,csv,json,hashlib,sys,argparse,math
import numpy as np
ROOT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--limit',type=int);parser.add_argument('--out',type=Path);args=parser.parse_args()
OUT=args.out or ROOT;OUT.mkdir(parents=True,exist_ok=True)
source=ROOT.parent/'run.py';nodes=[]
for node in ast.parse(source.read_text(encoding='utf-8-sig')).body:
 if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='folds' for t in node.targets):break
 if isinstance(node,(ast.Import,ast.ImportFrom,ast.Assign,ast.FunctionDef)):nodes.append(node)
base={'__file__':str(source)};exec(compile(ast.Module(body=nodes,type_ignores=[]),str(source),'exec'),base)
N=min(args.limit or len(base['D']),len(base['D']));D=base['D'][:N];C=np.array(base['C'][:N]);A=np.array(base['A'][:N]);S=np.array(base['S'][:N]);LABELS={s:[g for g in gg if g[1]<N] for s,gg in base['LABELS'].items()}
GROUPS=['price','price_amount','price_style','price_amount_style','price_interactions','price_swing']
POLICIES=['crossing','hysteresis'];THRESHOLDS=[.02,.05,.10,.15,.20,.30,.40,.50]
PLAN={'model':'Shrinkage diagonal Gaussian; 50% covariance shrinkage, fixed','feature_families':GROUPS,'policies':POLICIES,'configurations':12,'thresholds':THRESHOLDS,'validation':'Last three years of historically generated out-of-fold scores, only labels mature by selection time','minimum_validation_support':{'alerts':5,'pivots':3},'fallback':'threshold0.10; price/crossing for live selector if no adequately supported validation','training':'Annual expanding fit on mature-frontier samples; feature standardization on training only','evaluation_start':'2016-01-01','maturity_buffer':140,'lead':[1,7],'negative_label_policy':'Window ends no later than latest pivot mature at training cutoff','source_sha256':base['PLAN']['source_sha256'],'sample_unseen':False,'PIT_certified':False,'production_changed':False,'prefix_limit':N,'warning':'All candidates and thresholds are research attempts, including failures. Historical scores are not future evidence.'}
planfile=OUT/'plan.json'
if planfile.exists():assert json.loads(planfile.read_text(encoding='utf-8'))==PLAN,'Plan changed: use a new output directory'
else:planfile.write_text(json.dumps(PLAN,ensure_ascii=False,indent=2),encoding='utf-8')

def make_features(c,a,s,scale):
 n=len(c);core=np.full((n,6),np.nan);amount=np.full((n,3),np.nan);style=np.full((n,3),np.nan);swing=np.full((n,4),np.nan)
 state=0;hi=lo=0;last_pivot=0;last_confirm=0;th=scale/100
 for i in range(n-1):
  price=c[i]
  if state==0:
   if price>=c[hi]:hi=i
   if price<=c[lo]:lo=i
   if price<=c[hi]*(1-th):state=-1;last_pivot=hi;last_confirm=i;lo=i
   elif price>=c[lo]*(1+th):state=1;last_pivot=lo;last_confirm=i;hi=i
  elif state==1:
   if price>=c[hi]:hi=i
   if price<=c[hi]*(1-th):state=-1;last_pivot=hi;last_confirm=i;lo=i
  else:
   if price<=c[lo]:lo=i
   if price>=c[lo]*(1+th):state=1;last_pivot=lo;last_confirm=i;hi=i
  di=i+1
  if di<252:continue
  v=max(float(np.std(np.diff(np.log(c[i-20:i+1])),ddof=1)),.001)
  r3=np.log(c[i]/c[i-3]);r20=np.log(c[i]/c[i-20]);previous3=np.log(c[i-3]/c[i-6]);l=min(c[i-62:i+1]);h=max(c[i-62:i+1])
  core[di]=[r3/v,r20/(v*np.sqrt(20)),(r3-previous3)/v,np.log(c[i]/max(c[i-19:i+1]))/v,np.log(c[i]/min(c[i-19:i+1]))/v,(c[i]-l)/(h-l) if h>l else .5]
  amount[di]=[np.log(np.mean(a[i-4:i+1])/np.mean(a[i-19:i+1])),np.log(a[i]/np.mean(a[i-19:i+1])),np.log(np.mean(a[i-4:i+1])/np.mean(a[i-9:i-4]))]
  style[di]=[np.log(s[i]/s[i-5])/(v*np.sqrt(5)),np.log(s[i]/s[i-20])/(v*np.sqrt(20)),(np.log(s[i]/s[i-5])-np.log(s[i-5]/s[i-10]))/(v*np.sqrt(5))]
  extreme=c[hi] if state==1 else c[lo];retracement=np.log(c[i]/extreme)/th
  swing[di]=[state,retracement,min(i-last_confirm,252)/252,np.log(c[i]/c[last_pivot])/th]
 interaction=np.column_stack([core[:,0]*core[:,1],core[:,1]*core[:,2],core[:,0]**2,core[:,2]**2])
 return {'price':core,'price_amount':np.column_stack([core,amount]),'price_style':np.column_stack([core,style]),'price_amount_style':np.column_stack([core,amount,style]),'price_interactions':np.column_stack([core,interaction]),'price_swing':np.column_stack([core,swing])}
FEATURES={s:make_features(C,A,S,s) for s in [5,9]};prefix_feature_checks=0
for cut in [600,min(1500,N-1)]:
 if cut>=N:continue
 for scale in [5,9]:
  smaller=make_features(C[:cut],A[:cut],S[:cut],scale)
  for group in GROUPS:assert np.allclose(smaller[group][252:],FEATURES[scale][group][252:cut],rtol=0,atol=1e-12,equal_nan=True);prefix_feature_checks+=1

def pool(scale,side,cutoff):
 known=[g for g in LABELS[scale] if g[1]+140<=cutoff]
 if not known:return np.array([],int),np.array([]),np.array([])
 end=max(g[0] for g in known)-7;ix=np.arange(252,end+1);y=np.zeros(len(ix));w=np.ones(len(ix))/7
 for p,confirm,direction in known:
  if direction!=side:continue
  mask=(ix>=p-7)&(ix<p);k=int(mask.sum())
  if k:y[mask]=1;w[mask]=1/k
 return ix,y,w
sigmoid=lambda z:1/(1+np.exp(-np.clip(z,-35,35)))
def fit(x,ix,y,w):
 if len(ix)<100 or y.sum()<7 or (1-y).sum()<7:return None
 mu=x[ix].mean(0);sd=x[ix].std(0);sd[sd<1e-8]=1;z=np.clip((x[ix]-mu)/sd,-8,8)
 means=[];variances=[];priors=[]
 for label in [0,1]:
  mask=y==label;weights=w[mask];values=z[mask];avg=np.average(values,axis=0,weights=weights);var=np.average((values-avg)**2,axis=0,weights=weights)
  means.append(avg);variances.append(np.maximum(.5*var+.5*np.var(z,axis=0),.05));priors.append(float(weights.sum()/w.sum()))
 return mu,sd,np.array(means),np.array(variances),np.array(priors)
def predict(model,x,ix):
 mu,sd,means,variances,priors=model;z=np.clip((x[ix]-mu)/sd,-8,8)
 logp=[np.log(priors[k])-.5*np.sum(np.log(variances[k])+(z-means[k])**2/variances[k],axis=1) for k in [0,1]]
 return sigmoid(logp[1]-logp[0])

def update(state,i,p,t,policy):
 reset=t if policy=='crossing' else t*.5
 if i>state['active_until'] and p<reset:state['armed']=True
 fire=i>state['active_until'] and state['armed'] and p>=t
 if fire:state['active_until']=int(i)+7;state['armed']=False
 return fire

def emit(ix,probs,t,policy):
 st={'active_until':-1,'armed':True};return [int(i) for i,p in zip(ix,probs) if update(st,int(i),float(p),t,policy)]
score=base['score'];allfolds=[];all_events=[];allscores=[];result={};fallbacks={};support_logs=[]
for scale in [5,9]:
 for side in ['TOP','BOTTOM']:
  task=f'{scale}_{side}';hist={g:{} for g in GROUPS};states={(g,p):{'active_until':-1,'armed':True} for g in GROUPS for p in POLICIES};ledgers={k:[] for k in states};live_state={'active_until':-1,'armed':True};live=[];fallback_counts=0
  for year in range(2014,2027):
   test=np.array([i for i,d in enumerate(D) if d.startswith(str(year))],int)
   if not len(test):continue
   cutoff=int(test[0])-1;ix,y,w=pool(scale,side,cutoff)
   mature=[g for g in LABELS[scale] if g[1]+140<=cutoff];frontier=max((g[0] for g in mature),default=-1)
   val_start=next((i for i,d in enumerate(D) if d>=f'{year-3}-01-01'),N)
   candidate_info={};models={};predictions={}
   for group in GROUPS:
    x=FEATURES[scale][group];model=fit(x,ix,y,w)
    if model is None:continue
    models[group]=model;predictions[group]=predict(model,x,test)
    past=sorted(i for i in hist[group] if i+7<=frontier)
    gg=[g for g in mature if g[2]==side and past and past[0]+7<=g[0]<=frontier]
    for policy in POLICIES:
     choices=[]
     for threshold in THRESHOLDS:
      va=emit(past,[hist[group][i] for i in past],threshold,policy);met,pairs=score(va,gg)
      # Global matching preserves crossing-year pairs; cohort counts use event timestamps.
      selected_alerts=[a for a in va if a>=val_start];matched_alerts={a for a,p in pairs};selected_goals=[g for g in gg if g[0]>=val_start];matched_pivots={p for a,p in pairs}
      hit_a=sum(a in matched_alerts for a in selected_alerts);hit_p=sum(g[0] in matched_pivots for g in selected_goals)
      precision=hit_a/len(selected_alerts) if selected_alerts else None;recall=hit_p/len(selected_goals) if selected_goals else None
      supported=len(selected_alerts)>=5 and len(selected_goals)>=3
      objective=min(precision or 0,recall or 0) if supported else -1
      choices.append((objective,precision or 0,-len(selected_alerts),threshold,{'validation_precision':precision,'validation_recall':recall,'validation_alerts':len(selected_alerts),'validation_pivots':len(selected_goals),'supported':supported}))
     chosen=max(choices,key=lambda q:q[:4]);threshold=chosen[3] if chosen[0]>=0 else .10
     candidate_info[group,policy]={'threshold':threshold,'objective':chosen[0],**chosen[4]}
   supported=[(info['objective'],info['validation_precision'] or 0,-GROUPS.index(key[0]),-POLICIES.index(key[1]),key) for key,info in candidate_info.items() if info['objective']>=0]
   if supported:live_key=max(supported)[-1]
   else:live_key=('price','crossing');fallback_counts+=1
   if live_key not in candidate_info and candidate_info:live_key=next(iter(candidate_info))
   for key,info in candidate_info.items():
    allfolds.append({'task':task,'year':year,'group':key[0],'policy':key[1],'train_days':len(ix),'positive_days':int(y.sum()),'latest_train_decision':D[ix[-1]],'live_selected':key==live_key,'test_outcomes_used':False,**info})
   for offset,i in enumerate(test):
    for key,info in candidate_info.items():
     group,policy=key;p=float(predictions[group][offset]);t=info['threshold']
     if update(states[key],int(i),p,t,policy):ledgers[key].append(int(i))
    if live_key in candidate_info:
     info=candidate_info[live_key];prob=float(predictions[live_key[0]][offset])
     if update(live_state,int(i),prob,info['threshold'],live_key[1]):live.append(int(i))
   # Test-year forecasts become available only to future year's validation selection.
   for group,probs in predictions.items():
    for i,p in zip(test,probs):hist[group][int(i)]=float(p);allscores.append({'task':task,'group':group,'date':D[i],'last_input_date':D[i-1],'score':float(p)})
  known=[g for g in LABELS[scale] if g[1]+140<N];frontier=max(g[0] for g in known);start=next(i for i,d in enumerate(D) if d>='2016-01-01');gg=[g for g in known if g[2]==side and start+7<=g[0]<=frontier]
  entries={f'{g}__{policy}':v for (g,policy),v in ledgers.items()};entries['past_only_selector']=live;entries['original_rule']=base['ALL'][scale,side,'baseline']
  result[task]={}
  for name,ledger in entries.items():
   ledger=[i for i in ledger if start<=i<N];aa=[i for i in ledger if i+7<=frontier];met,pairs=score(aa,gg);matched=dict(pairs)
   assert len(matched)==len(set(matched.values()));assert all(1<=p-a<=7 for a,p in pairs)
   met.update(pending=len(ledger)-len(aa),all_alerts=len(ledger),mature_pivots=len(gg),frontier=D[frontier],dual80=met['precision'] is not None and met['precision']>=.8 and met['recall']>=.8)
   result[task][name]=met
   for a in ledger:all_events.append({'task':task,'configuration':name,'date':D[a],'status':'TP' if a in matched else 'FP' if a in aa else 'PENDING','pivot_date':D[matched[a]] if a in matched else ''})
  fallbacks[task]=fallback_counts
  print('FINISHED',task,'selector',result[task]['past_only_selector'],flush=True)
report={'plan':PLAN,'results':result,'annual_selection':allfolds,'fallback_year_counts':fallbacks,'feature_prefix_checks':prefix_feature_checks,'historical_all_four_tasks_double80':all(result[t]['past_only_selector']['dual80'] for t in result),'production_changed':False,'limits':['Historical data repeatedly inspected, not a blind test','Only 3 validation pivots are required: weak calibration evidence, counts disclosed','Historical release timestamps and index constituent history not certified','Scores are not independently calibrated probabilities','The original-rule control predates 2014 whereas probability ledgers begin 2014; evaluation begins2016 and retains actual candidate states','No future pivot counts used as live alarm budgets']}
(OUT/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
for name,records in [('events.csv',all_events),('scores.csv',allscores)]:
 with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
  writer=csv.DictWriter(f,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
