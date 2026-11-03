from pathlib import Path
import ast,json,csv,hashlib
import numpy as np
P=Path(__file__).resolve().parent;src=P.parent/'run.py';nodes=[]
for n in ast.parse(src.read_text(encoding='utf-8-sig')).body:
 if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='folds' for t in n.targets):break
 if isinstance(n,(ast.Import,ast.ImportFrom,ast.Assign,ast.FunctionDef)):nodes.append(n)
b={'__file__':str(src)};exec(compile(ast.Module(body=nodes,type_ignores=[]),str(src),'exec'),b)
D=b['D'];C=np.array(b['C']);A=np.array(b['A']);S=np.array(b['S']);N=len(D);LABELS=b['LABELS'];sigmoid=lambda z:1/(1+np.exp(-np.clip(z,-35,35)))
source=P.parent/'broad_experiments_v2/run.py';tree=ast.parse(source.read_text(encoding='utf-8'))
# Reuse audited feature construction and fixed estimator/notification code, not its search loop.
for n in tree.body:
 if isinstance(n,ast.FunctionDef) and n.name in ['make_features','fit','predict','update']:
  exec(compile(ast.Module(body=[n],type_ignores=[]),str(source),'exec'),globals())
X={s:make_features(C,A,S,s)['price'] for s in [5,9]}
PLAN={'policies':[[140,'annual'],[140,'quarterly'],[0,'annual'],[0,'quarterly']],'estimator':'Fixed price-only six-feature logistic regression L2=10','threshold':.10,'minimum_independent_positive_events':10,'training_clock':'Only pivot confirmation+policy buffer no later than previous observation','positive_samples':'Complete known positive windows, overlap event weights accumulated','negative_samples':'Only windows ending no later than latest known eligible pivot','evaluation':'Same continuous 2016+ cohort and confirmation+140 maturity frontier for all four policies','threshold_search':False,'PIT_certified':False,'blind_sample':False,'production_changed':False,'source_sha256':b['PLAN']['source_sha256']}
(P/'plan.json').write_text(json.dumps(PLAN,indent=2),encoding='utf-8')
def build_pool(scale,side,cutoff,buffer):
 known=[g for g in LABELS[scale] if g[1]+buffer<=cutoff]
 if not known:return None
 safe_end=max(g[0] for g in known)-7;target={i:[0.,1/7] for i in range(252,safe_end+1)};event_count=0
 for p,confirm,direction in known:
  if direction!=side:continue
  window=[i for i in range(max(252,p-7),p) if i<=cutoff]
  if not window:continue
  event_count+=1
  for i in window:
   if i not in target or target[i][0]==0:target[i]=[1.,0.]
   target[i][1]+=1/len(window)
 ix=np.array(sorted(target),int);y=np.array([target[i][0] for i in ix]);w=np.array([target[i][1] for i in ix]);assert np.isclose(w[y==1].sum(),event_count)
 assert all(g[1]+buffer<=cutoff for g in known)
 return ix,y,w,event_count

def run(limit=None):
 end=limit or N;metrics={};events=[];scores=[];fits=[]
 for buffer,cadence in PLAN['policies']:
  config=f'buffer{buffer}_{cadence}';metrics[config]={}
  for scale in [5,9]:
   for side in ['TOP','BOTTOM']:
    task=f'{scale}_{side}';x=X[scale];model=None;last_period=None;state={'active_until':-1,'armed':True};ledger=[]
    for di in range(252,end):
     year=int(D[di][:4]);month=int(D[di][5:7]);period=(year,1 if cadence=='annual' else (month-1)//3+1)
     if year<2014:continue
     if period!=last_period:
      cutoff=di-1;pool=build_pool(scale,side,cutoff,buffer);model=None
      if pool:
       ix,y,w,k=pool
       if k>=10:model=fit(x,ix,y,w)
       fits.append({'configuration':config,'task':task,'decision':D[di],'cutoff':D[cutoff],'positive_events':k,'training_days':len(ix),'positive_days':int(y.sum()),'positive_weight':float(w[y==1].sum()),'latest_training_decision':D[ix[-1]],'fit_supported':model is not None})
      last_period=period
     if model is None:continue
     prob=float(predict(model,x,np.array([di]))[0]);scores.append({'configuration':config,'task':task,'date':D[di],'last_input':D[di-1],'score':prob})
     if update(state,di,prob,.10,'crossing'):ledger.append(di)
    known=[g for g in LABELS[scale] if g[1]+140<end];frontier=max(g[0] for g in known);start=next(i for i,d in enumerate(D) if d>='2016-01-01');goals=[g for g in known if g[2]==side and start+7<=g[0]<=frontier]
    ledger=[a for a in ledger if a>=start];aa=[a for a in ledger if a+7<=frontier];met,pairs=b['score'](aa,goals);matched=dict(pairs)
    met.update(pending=len(ledger)-len(aa),targets=len(goals),frontier=D[frontier],double80=met['precision'] is not None and met['precision']>=.8 and met['recall']>=.8)
    metrics[config][task]=met
    for a in ledger:events.append({'configuration':config,'task':task,'date':D[a],'status':'TP' if a in matched else 'FP' if a in aa else 'PENDING','pivot':D[matched[a]] if a in matched else ''})
 return metrics,events,scores,fits
if __name__=='__main__':
 metrics,events,scores,fits=run()
 # Full training and issue-time invariance; later labels cannot alter earlier fits.
 _,pe,ps,pf=run(2500);lookup={(r['configuration'],r['task'],r['date']):r for r in scores}
 assert all(abs(lookup[r['configuration'],r['task'],r['date']]['score']-r['score'])<=1e-12 for r in ps)
 end=max(r['date'] for r in ps);assert {(r['configuration'],r['task'],r['date']) for r in pe}=={(r['configuration'],r['task'],r['date']) for r in events if r['date']<=end}
 for name,rows in [('events.csv',events),('scores.csv',scores),('training_log.csv',fits)]:
  with (P/name).open('w',encoding='utf-8-sig',newline='') as f:
   w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 result={'plan':PLAN,'results':metrics,'prefix_scores_checked':len(ps),'prefix_alarms_checked':len(pe),'prefix_pass':True,'new_training_construction_applied_to_all_4_arms':True,'note':'Threshold intentionally fixed to isolate training policy. No claim of calibrated probabilities or PIT certification.'}
 (P/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(metrics,indent=2))
