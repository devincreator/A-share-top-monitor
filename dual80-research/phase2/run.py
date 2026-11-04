from pathlib import Path
import csv,json,hashlib,statistics,datetime
P=Path(__file__).resolve().parent
SRC=P.parent.parent/'turning-research-canonical/tables/research_inputs.csv'
rows=list(csv.DictReader(SRC.open(encoding='utf-8-sig')));D=[r['date'] for r in rows]
C=[float(r['all_a_close']) for r in rows];A=[float(r['turnover']) for r in rows];S=[float(r['zz1000_close'])/float(r['hs300_close']) for r in rows]
PLAN={'candidates':['baseline','deceleration','participation','deceleration_participation'],'test_years':list(range(2016,2027)),'selection':'per task maximize min(precision,recall) on prior matured events; ties precision then fixed candidate order','lead':[1,7],'maturity_buffer':140,'min_train_alerts':10,'min_train_pivots':10,'data_asof_certified':False,'unseen_test':False,'reason':'All history has previously been inspected; walk-forward simulates selection timing only','source_sha256':hashlib.sha256(SRC.read_bytes()).hexdigest()}
(P/'plan.json').write_text(json.dumps(PLAN,indent=2),encoding='utf-8')
def pivots(th):
 state=0;hi=lo=0;out=[]
 for i,c in enumerate(C):
  if state==0:
   if c>=C[hi]:hi=i
   if c<=C[lo]:lo=i
   if c<=C[hi]*(1-th):out.append((hi,i,'TOP'));state=-1;lo=i
   elif c>=C[lo]*(1+th):out.append((lo,i,'BOTTOM'));state=1;hi=i
  elif state==1:
   if c>=C[hi]:hi=i
   if c<=C[hi]*(1-th):out.append((hi,i,'TOP'));state=-1;lo=i
  else:
   if c<=C[lo]:lo=i
   if c>=C[lo]*(1+th):out.append((lo,i,'BOTTOM'));state=1;hi=i
 return out[1:]
LABELS={scale:pivots(scale/100) for scale in [5,9]}
def signals(scale,side,mode,end=None):
 n=len(C) if end is None else end;w,mom,lim,move,cool=(63,20,.9,.015,10) if scale==5 else (126,60,.95,.055,20)
 previous=False;last=-100000;out=[]
 for di in range(max(w,mom+1),n):
  i=di-1;look=C[i-w+1:i+1];lo=min(look);hi=max(look);loc=(C[i]-lo)/(hi-lo) if hi>lo else .5;ret=C[i]/C[i-mom]-1
  basic=(loc>=lim and ret>=move) if side=='TOP' else (loc<=1-lim and ret<=-move)
  fade=statistics.mean(A[i-4:i+1])<statistics.mean(A[i-19:i+1])
  div=S[i]<S[i-5] if side=='TOP' else S[i]>S[i-5]
  # Direction-specific hypotheses: top weak participation, bottom fading sell pressure.
  if mode=='baseline':yes=basic
  else:
   broad=(loc>=.7 and ret>0) if side=='TOP' else (loc<=.3 and ret<0)
   recent=C[i]/C[i-3]-1;prior=C[i-3]/C[i-6]-1
   slowing=recent<prior if side=='TOP' else recent>prior
   participation=A[i]<statistics.mean(A[i-19:i+1])
   yes=broad and (mode not in ['deceleration','deceleration_participation'] or slowing) and (mode not in ['participation','deceleration_participation'] or participation)
  if yes and not previous and di-last>cool:out.append(di);last=di
  previous=yes
 return out
ALL={(s,t,m):signals(s,t,m) for s in [5,9] for t in ['TOP','BOTTOM'] for m in PLAN['candidates']}
def score(alerts,goals):
 # Equal-length forward windows: earliest eligible ordered matching maximizes cardinality.
 j=0;pairs=[]
 for a in alerts:
  while j<len(goals) and goals[j][0]<=a:j+=1
  if j<len(goals) and 1<=goals[j][0]-a<=7:pairs.append((a,goals[j][0]));j+=1
 tp=len(pairs);fp=len(alerts)-tp;fn=len(goals)-tp
 return {'tp':tp,'fp':fp,'fn':fn,'precision':tp/len(alerts) if alerts else None,'recall':tp/len(goals) if goals else None},pairs
folds=[];event_rows=[];total={};selection=[]
for scale in [5,9]:
 for side in ['TOP','BOTTOM']:
  task=f'{scale}_{side}';acc={'tp':0,'fp':0,'fn':0};baseacc={'tp':0,'fp':0,'fn':0}
  for year in PLAN['test_years']:
   ids=[i for i,d in enumerate(D) if d.startswith(str(year))]
   if not ids:continue
   start,end=ids[0],ids[-1]
   # Only completed forward windows enter scored pools; ignore first 252 observations for shared warmup.
   train_end=start-1
   train_goals=[g for g in LABELS[scale] if g[2]==side and g[0]>=259 and g[1]+140<=train_end]
   train_alert_end=train_end-147
   candidates=[]
   for order,mode in enumerate(PLAN['candidates']):
    aa=[a for a in ALL[scale,side,mode] if 252<=a<=train_alert_end]
    # Limit target times to the same scored opportunity span as alerts.
    gg=[g for g in train_goals if g[0]<=train_alert_end+7]
    met,_=score(aa,gg);valid=len(aa)>=10 and len(gg)>=10
    candidates.append((min(met['precision'] or 0,met['recall'] or 0) if valid else -1,met['precision'] or 0,-order,mode,met))
   best=max(candidates);mode=best[3] if best[0]>=0 else 'baseline'
   # Fold boundary intervals excluded symmetrically: only alerts and targets fully within the test year.
   last=min(end-7,len(D)-148)
   goals=[g for g in LABELS[scale] if g[2]==side and start+7<=g[0]<=last+7 and g[1]+140<len(D)]
   for label,m,aggregate in [('selected',mode,acc),('baseline','baseline',baseacc)]:
    aa=[a for a in ALL[scale,side,m] if start<=a<=last];met,pairs=score(aa,goals)
    for k in aggregate:aggregate[k]+=met[k]
    folds.append({'task':task,'year':year,'arm':label,'candidate':m,'last_scored_alert':D[last] if last>=start else None,'train_selection_score':best[0],**met})
    paired=dict(pairs)
    for a in aa:event_rows.append({'task':task,'year':year,'arm':label,'candidate':m,'alert_date':D[a],'last_input_date':D[a-1],'result':'TP' if a in paired else 'FP','pivot_date':D[paired[a]] if a in paired else ''})
  for x in [acc,baseacc]:
   x['precision']=x['tp']/(x['tp']+x['fp']) if x['tp']+x['fp'] else None;x['recall']=x['tp']/(x['tp']+x['fn']) if x['tp']+x['fn'] else None
  total[task]={'selected':acc,'baseline':baseacc}
# Causality: prefix rerun must equal all signals emitted before truncation.
for key,full in ALL.items():
 for cut in [600,1500,2500]:assert signals(*key,end=cut)==[i for i in full if i<cut]
report={'plan':PLAN,'metrics':total,'folds':folds,'causality_prefix_checks_passed':48,'production_updated':False,'double80':all(x['selected']['precision'] is not None and x['selected']['precision']>=.8 and x['selected']['recall']>=.8 for x in total.values()),'limits':['Annual within-fold scoring excludes boundary and maturity intervals; not a whole-history score','Maturity buffer applied to full archive endpoint, not separately to every test year','No historical publication-time certification','No genuinely untouched test set','No individual stock universe used; index composition history still not independently certified']}
(P/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
with (P/'events.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(event_rows[0]));w.writeheader();w.writerows(event_rows)
print(json.dumps(total,indent=2))
