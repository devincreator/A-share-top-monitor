"""Frozen label/clock migration. Bounded 2-label x 2-feature experiment; no test tuning."""
from pathlib import Path
import ast,csv,json,hashlib,statistics
import numpy as np
P=Path(__file__).resolve().parent;R=P.parent.parent
source=R/'turning-research-canonical/tables/research_inputs.csv';rows=list(csv.DictReader(source.open(encoding='utf-8-sig')));D=[r['date'] for r in rows];C=np.array([float(r['all_a_close']) for r in rows]);A=np.array([float(r['turnover']) for r in rows]);S=np.array([float(r['zz1000_close'])/float(r['hs300_close']) for r in rows]);N=len(D);pos={d:i for i,d in enumerate(D)}
label_file=R/'turning-label-comparison/all_labels.csv';ll=list(csv.DictReader(label_file.open(encoding='utf-8-sig')));LABELS={v:{s:[(pos[l['pivot_date']],pos[l['confirmation_date']],l['direction']) for l in ll if l['definition']==v and int(l['scale'])==s] for s in [5,9]} for v in ['close','intraday_extrema_close_confirm']}
sigmoid=lambda z:1/(1+np.exp(-np.clip(z,-35,35)))
# Extract pure, already audited numerical functions; do not execute old module-level plans or loops.
fsource=P.parent/'broad_experiments_v2/run.py'
for n in ast.parse(fsource.read_text(encoding='utf-8-sig')).body:
 if isinstance(n,ast.FunctionDef) and n.name in ['make_features','fit','predict']:exec(compile(ast.Module(body=[n],type_ignores=[]),str(fsource),'exec'),globals())
for n in ast.parse((P.parent/'run.py').read_text(encoding='utf-8-sig')).body:
 if isinstance(n,ast.FunctionDef) and n.name=='signals':exec(compile(ast.Module(body=[n],type_ignores=[]),str(P.parent/'run.py'),'exec'),globals())
X=make_features(C,A,S,5);GROUPS=['price','price_amount_style'];START=next(i for i,d in enumerate(D) if d>='2016-01-01')
PLAN={'primary_label':'intraday_extrema_close_confirm','control_label':'close','lead':[0,6],'estimator':'Logistic L2=10; six price features, or same price plus three amount and three style features','groups':GROUPS,'training':'quarterly expanding fit; labels confirmed by previous close; >=10 independent positive events; full 7-decision positive windows, overlapping weights accumulated','safe_negative_end':'latest confirmed pivot minus6','threshold':.10,'threshold_calibrated':False,'notification':'one initial upward crossing; lock through D+6; rearm only on a subsequent below-threshold observation after lock','test_start':'2016-01-01','initial_target_boundary':'start+7, retained for exact historical cohort comparison','evaluation_maturity':'confirmation+140 common frontier across both labels; retained only as historical evaluation buffer, not training wait','baseline':'unchanged historical original price rule, rescored on same cohort','new_model_cases':16,'all_history_previously_inspected':True,'blind_sample':False,'PIT_certified':False,'production_changed':False,'input_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'labels_sha256':hashlib.sha256(label_file.read_bytes()).hexdigest(),'label_decision_sha256':hashlib.sha256((P/'label_decision.json').read_bytes()).hexdigest()}
if (P/'plan.json').exists():assert json.loads((P/'plan.json').read_text(encoding='utf-8'))==PLAN
else:(P/'plan.json').write_text(json.dumps(PLAN,ensure_ascii=False,indent=2),encoding='utf-8')
def pool(labels,side,cutoff):
 known=[g for g in labels if g[1]<=cutoff]
 if not known:return None
 safe=max(g[0] for g in known)-6;targets={i:[0.,1/7] for i in range(252,safe+1)};count=0
 for p,c,direction in known:
  if direction!=side or p-6<252:continue
  window=list(range(p-6,p+1));assert window[-1]<=cutoff
  count+=1
  for i in window:
   if i not in targets or targets[i][0]==0:targets[i]=[1.,0.]
   targets[i][1]+=1/7
 ix=np.array(sorted(targets),int);y=np.array([targets[i][0] for i in ix]);w=np.array([targets[i][1] for i in ix]);assert np.isclose(w[y==1].sum(),count)
 assert not len(ix) or ix.max()<=cutoff
 return ix,y,w,count

def match(aa,gg):
 j=0;pairs=[]
 for a in aa:
  while j<len(gg) and gg[j][0]<a:j+=1
  if j<len(gg) and gg[j][0]-a<=6:pairs.append((a,gg[j][0]));j+=1
 return pairs

def notify(st,i,p):
 if i>st['until'] and p<.1:st['armed']=True
 if i>st['until'] and st['armed'] and p>=.1:st.update(until=i+6,armed=False);return True
 return False

def evaluate(ledger,labels,side,front,end):
 goals=[g for g in labels if g[2]==side and START+7<=g[0]<=front and g[1]+140<end];ledger=[a for a in ledger if a>=START];aa=[a for a in ledger if a+6<=front];pairs=match(aa,goals);tp=len(pairs);fp=len(aa)-tp;fn=len(goals)-tp;pr=tp/len(aa) if aa else None;re=tp/len(goals) if goals else None
 assert len(set(p for a,p in pairs))==len(pairs) and all(0<=p-a<=6 for a,p in pairs)
 return {'TP':tp,'FP':fp,'FN':fn,'precision':pr,'recall':re,'alerts':len(aa),'targets':len(goals),'pending':len(ledger)-len(aa),'same_day_hits':sum(a==p for a,p in pairs),'frontier':D[front],'dual80':pr is not None and re is not None and pr>=.8 and re>=.8,'right_boundary_targets_last6':sum(g[0]>front-6 for g in goals)},pairs,aa

def run(end=N):
 scores=[];fits=[];events=[];metrics=[];LL={v:{s:[g for g in seq if g[1]<end] for s,seq in ss.items()} for v,ss in LABELS.items()};front={s:min(max(g[0] for g in LL[v][s] if g[1]+140<end) for v in LL) for s in [5,9]}
 for variant,ss in LL.items():
  for scale,labels in ss.items():
   for side in ['TOP','BOTTOM']:
    task=f'{scale}_{side}'
    ledgers={group:[] for group in GROUPS};states={group:{'until':-1,'armed':True} for group in GROUPS};models={};period=None
    for di in range(252,end):
     year=int(D[di][:4]);quarter=(int(D[di][5:7])-1)//3
     if year<2014:continue
     if (year,quarter)!=period:
      cutoff=di-1;pp=pool(labels,side,cutoff);models={}
      if pp:
       ix,y,w,k=pp
       for group in GROUPS:
        model=fit(X[group],ix,y,w) if k>=10 else None
        if model is not None:models[group]=model
        fits.append({'label':variant,'task':task,'group':group,'decision':D[di],'cutoff':D[cutoff],'events':k,'fit_supported':model is not None,'days':len(ix),'positive_weight':float(w[y==1].sum()),'latest_training_decision':D[ix[-1]] if len(ix) else '', 'latest_available_confirmation':D[max(g[1] for g in labels if g[1]<=cutoff)]})
      period=(year,quarter)
     for group,model in models.items():
      prob=float(predict(model,X[group],np.array([di]))[0]);scores.append({'label':variant,'task':task,'group':group,'date':D[di],'last_input':D[di-1],'score':prob})
      if notify(states[group],di,prob):ledgers[group].append(di)
    ledgers['original_rule']=signals(scale,side,'baseline',end)
    for group,ledger in ledgers.items():
     met,pairs,aa=evaluate(ledger,labels,side,front[scale],end);metrics.append(dict(label=variant,task=task,group=group,**met));matched=dict(pairs)
     for a in ledger:
      if a<START:continue
      events.append({'label':variant,'task':task,'group':group,'date':D[a],'status':'TP' if a in matched else 'FP' if a in aa else 'PENDING','pivot_date':D[matched[a]] if a in matched else '', 'lead_sessions':matched[a]-a if a in matched else ''})
 return metrics,events,scores,fits
if __name__=='__main__':
 metrics,events,scores,fits=run();pm,pe,ps,pf=run(2500);lookup={(r['label'],r['task'],r['group'],r['date']):r for r in scores}
 assert all(abs(lookup[r['label'],r['task'],r['group'],r['date']]['score']-r['score'])<1e-12 for r in ps)
 keys=lambda rr:{(r['label'],r['task'],r['group'],r['date']) for r in rr}
 assert keys(pe)==keys([r for r in events if r['date']<=D[2499]])
 fl={(r['label'],r['task'],r['group'],r['decision']):r for r in fits};assert all(fl[r['label'],r['task'],r['group'],r['decision']]==r for r in pf)
 # Independent feature prefix construction and label-prefix reconstruction, without reading future label dates.
 features=make_features(C[:2500],A[:2500],S[:2500],5)
 assert all(np.allclose(features[g][252:],X[g][252:2500],atol=1e-12,rtol=0) for g in GROUPS)
 chartsrc=R/'turning-label-comparison/build_charts.py';ns={'Decimal':__import__('decimal').Decimal}
 for n in ast.parse(chartsrc.read_text(encoding='utf-8-sig')).body:
  if isinstance(n,ast.FunctionDef) and n.name=='make_labels':exec(compile(ast.Module(body=[n],type_ignores=[]),str(chartsrc),'exec'),ns)
 raw=json.loads((R/'turning-research-canonical/raw/official/000985_20110802_20260825.response.json').read_text(encoding='utf-8'))['data'];byday={r['tradeDate']:r for r in raw};bars=[byday[d.replace('-','')] for d in D[:2500]]
 for variant in LABELS:
  for s in [5,9]:assert [(p,c,d) for p,c,d,v in ns['make_labels'](bars,s,variant!='close')]==[g for g in LABELS[variant][s] if g[1]<2500]
 # Match independent dynamic programming on randomly generated tiny streams.
 rng=np.random.default_rng(12)
 for _ in range(500):
  aa=sorted(rng.choice(20,size=int(rng.integers(0,8)),replace=False).tolist());gg=sorted(rng.choice(20,size=int(rng.integers(0,8)),replace=False).tolist());dp=np.zeros((len(aa)+1,len(gg)+1),int)
  for i,a in enumerate(aa,1):
   for j,p in enumerate(gg,1):dp[i,j]=max(dp[i-1,j],dp[i,j-1],dp[i-1,j-1]+1 if 0<=p-a<=6 else 0)
  assert len(match(aa,[(p,p,'X') for p in gg]))==int(dp[-1,-1])
 # Original-rule controls exactly reproduce the existing frozen comparison for both definitions.
 old=list(csv.DictReader((R/'turning-label-comparison/all_rescored_metrics.csv').open(encoding='utf-8-sig')))
 for m in [m for m in metrics if m['group']=='original_rule']:
  o=next(r for r in old if r['configuration']=='original_rule' and r['task']==m['task'] and r['label_definition']==m['label'] and r['window']=='new_D0_D6')
  assert all(m[k]==int(o[k]) for k in ['TP','FP','FN'])
 for name,rr in [('metrics.csv',metrics),('events.csv',events),('scores.csv',scores),('training_log.csv',fits)]:
  with (P/name).open('w',encoding='utf-8-sig',newline='') as f:
   w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
 result={'plan':PLAN,'metrics':metrics,'prefix_score_count':len(ps),'prefix_alarm_count':len(pe),'prefix_fit_count':len(pf),'prefix_training_features_labels_alarms_pass':True,'random_match_dp_checks':500,'original_rule_controls_match_previous':True,'passed_dual80':sum(m['dual80'] for m in metrics if m['group']!='original_rule'),'limitations':['History is repeatedly inspected, not a new blind test','Historical price/amount publication times and index composition not completely PIT-certified','Fixed 0.10 is a research score threshold, not a calibrated probability','Evaluation preserves the previous common mature cohort and +7 left boundary for comparability','Rightmost six target sessions may lack a fully observed scored alert window; counts disclosed, not silently optimized','Price and style inputs remain daily aggregates; label repair alone does not add new predictive information']}
 (P/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'metrics':metrics,'prefix':{k:v for k,v in result.items() if k.startswith('prefix')},'dual80_cases':result['passed_dual80']},ensure_ascii=False,indent=2))
