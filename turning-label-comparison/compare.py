from pathlib import Path
from decimal import Decimal
import ast,csv,json,hashlib,statistics
P=Path(__file__).resolve().parent;root=P.parent;source=root/'dual80-research/run.py';nodes=[]
for n in ast.parse(source.read_text(encoding='utf-8-sig')).body:
 if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='folds' for t in n.targets):break
 if isinstance(n,(ast.Import,ast.ImportFrom,ast.Assign,ast.FunctionDef)):nodes.append(n)
b={'__file__':str(source)};exec(compile(ast.Module(body=nodes,type_ignores=[]),str(source),'exec'),b)
D=b['D'];pos={d:i for i,d in enumerate(D)};rawpath=root/'turning-research-canonical/raw/official/000985_20110802_20260825.response.json';raw=json.loads(rawpath.read_text(encoding='utf-8'))['data'];lookup={r['tradeDate']:r for r in raw};bars=[lookup[d.replace('-','')] for d in D];C=[Decimal(str(r['close'])) for r in bars]

def intraday_extrema_close_confirm(scale):
 th=Decimal(scale)/100;state=0;hi=(C[0],0);lo=(C[0],0);out=[]
 for i,bar in enumerate(bars):
  high=Decimal(str(bar['high']));low=Decimal(str(bar['low']));close=C[i]
  if state==0:
   if high>=hi[0]:hi=(high,i)
   if low<=lo[0]:lo=(low,i)
   if close<=hi[0]*(1-th):out.append((hi[1],i,'TOP',str(hi[0])));state=-1;lo=(close,i)
   elif close>=lo[0]*(1+th):out.append((lo[1],i,'BOTTOM',str(lo[0])));state=1;hi=(close,i)
  elif state==1:
   if high>=hi[0]:hi=(high,i)
   if close<=hi[0]*(1-th):out.append((hi[1],i,'TOP',str(hi[0])));state=-1;lo=(close,i)
  else:
   if low<=lo[0]:lo=(low,i)
   if close>=lo[0]*(1+th):out.append((lo[1],i,'BOTTOM',str(lo[0])));state=1;hi=(close,i)
 return out[1:]
LABELS={'close':{s:[(*g,str(C[g[0]])) for g in b['LABELS'][s]] for s in [5,9]},'intraday_extrema_close_confirm':{s:intraday_extrema_close_confirm(s) for s in [5,9]}}
for variant,scales in LABELS.items():
 for scale,gg in scales.items():
  assert all(p<=c for p,c,side,price in gg)
  assert all(gg[i][2]!=gg[i-1][2] and gg[i][0]>=gg[i-1][1] for i in range(1,len(gg)))
# OHLC path scenarios diagnose unobservable high/low ordering; never treated as true intraday history.
def ohlc_scenario(scale,order):
 th=Decimal(scale)/100;state=0;hi=lo=(C[0],0);out=[]
 for i,bar in enumerate(bars):
  for key in order:
   price=Decimal(str(bar[key]))
   if state==0:
    if price>=hi[0]:hi=(price,i)
    if price<=lo[0]:lo=(price,i)
    if price<=hi[0]*(1-th):out.append((hi[1],i,'TOP'));state=-1;lo=(price,i)
    elif price>=lo[0]*(1+th):out.append((lo[1],i,'BOTTOM'));state=1;hi=(price,i)
   elif state==1:
    if price>=hi[0]:hi=(price,i)
    if price<=hi[0]*(1-th):out.append((hi[1],i,'TOP'));state=-1;lo=(price,i)
   else:
    if price<=lo[0]:lo=(price,i)
    if price>=lo[0]*(1+th):out.append((lo[1],i,'BOTTOM'));state=1;hi=(price,i)
 return out[1:]
scenarios={}
for scale in [5,9]:
 a=ohlc_scenario(scale,['open','high','low','close']);bb=ohlc_scenario(scale,['open','low','high','close']);sa={(p,c,s) for p,c,s in a};sb={(p,c,s) for p,c,s in bb};scenarios[str(scale)]={'high_first_count':len(a),'low_first_count':len(bb),'common_exact_events':len(sa&sb),'high_first_only':len(sa-sb),'low_first_only':len(sb-sa),'actual_path_certified':False}
# Preserve each issued alarm. Scores and trained models are NOT recomputed under new labels.
ALERTS={}
for model,folder in [('logistic',root/'dual80-research/broad_experiments_v2'),('gaussian',root/'dual80-research/broad_experiments_v2/gaussian'),('knn50',root/'dual80-research/broad_experiments_v2/knn50')]:
 for e in csv.DictReader((folder/'events.csv').open(encoding='utf-8-sig')):
  if e['configuration']=='original_rule':
   if model!='logistic':continue
   key=('original_rule',e['task'])
  else:key=(model+'/'+e['configuration'],e['task'])
  ALERTS.setdefault(key,[]).append(pos[e['date']])
def match(aa,gg,lo,hi):
 j=0;pairs=[]
 for a in aa:
  while j<len(gg) and gg[j][0]<a+lo:j+=1
  if j<len(gg) and gg[j][0]<=a+hi:pairs.append((a,gg[j]));j+=1
 return pairs
START=next(i for i,d in enumerate(D) if d>='2016-01-01');front={s:min(max(g[0] for g in LABELS[v][s] if g[1]+140<len(D)) for v in LABELS) for s in [5,9]}
metrics=[];events=[];comparisons=[]
for variant,scales in LABELS.items():
 for scale,pp in scales.items():
  for side in ['TOP','BOTTOM']:
   task=f'{scale}_{side}';goals=[g for g in pp if g[2]==side and START+7<=g[0]<=front[scale] and g[1]+140<len(D)]
   for (config,t),alarms in ALERTS.items():
    if t!=task:continue
    for window,lo,hi in [('old_D1_D7',1,7),('new_D0_D6',0,6)]:
     aa=sorted(a for a in alarms if START<=a and a+hi<=front[scale]);pairs=match(aa,goals,lo,hi);paired={a:g for a,g in pairs};assert len(paired)==len({(g[0],g[1],g[2]) for a,g in pairs});tp=len(pairs);fp=len(aa)-tp;fn=len(goals)-tp;precision=tp/len(aa) if aa else None;recall=tp/len(goals) if goals else None
     metrics.append({'configuration':config,'task':task,'label_definition':variant,'window':window,'TP':tp,'FP':fp,'FN':fn,'scored_alerts':len(aa),'mature_targets':len(goals),'precision':precision,'recall':recall,'common_mature_frontier':D[front[scale]],'dual80':precision is not None and precision>=.8 and recall>=.8})
     if config=='original_rule':
      for a in aa:
       g=paired.get(a);events.append({'configuration':config,'task':task,'label_definition':variant,'window':window,'alert_date':D[a],'status':'TP' if g else 'FP','pivot_date':D[g[0]] if g else '', 'confirmed_date':D[g[1]] if g else '', 'lead_sessions':g[0]-a if g else ''})
for scale in [5,9]:
 for p,c,side,price in LABELS['close'][scale]:
  near=min((g for g in LABELS['intraday_extrema_close_confirm'][scale] if g[2]==side),key=lambda g:abs(g[0]-p));comparisons.append({'scale':scale,'direction':side,'close_pivot':D[p],'close_confirmed':D[c],'intraday_pivot_nearest_same_side':D[near[0]],'intraday_confirmed':D[near[1]],'date_delta_sessions':near[0]-p,'pairing':'NEAREST_DIAGNOSTIC_NOT_ONE_TO_ONE_LABEL_IDENTITY'})
for name,rr in [('all_rescored_metrics.csv',metrics),('original_rule_events.csv',events),('label_date_comparison.csv',comparisons)]:
 with (P/name).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
label_rows=[{'definition':v,'scale':s,'direction':side,'pivot_date':D[p],'confirmation_date':D[c],'pivot_price':price} for v,ss in LABELS.items() for s,gg in ss.items() for p,c,side,price in gg]
with (P/'all_labels.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(label_rows[0]));w.writeheader();w.writerows(label_rows)
report={'window_user_confirmed':'D through D+6 inclusive, preopen D, seven observed trading sessions','comparison_holds_alerts_fixed':True,'models_retrained':False,'primary_intraday_definition':'Daily high/low extrema; close-based reversal confirmation; new leg begins at confirmation close, earlier same-bar low/high not reused','pure_intraday_reversal_certified':False,'OHLC_path_sensitivity':scenarios,'baseline_comparison':[x for x in metrics if x['configuration']=='original_rule'],'no_label_chosen_by_score':True,'production_changed':False,'PIT_certified':False,'raw_sha256':hashlib.sha256(rawpath.read_bytes()).hexdigest(),'limits':['Primary intraday labels are close-confirmed extrema, not fully intraday-confirmed zigzag','Current predictors were trained with old close labels and D1..7 targets; rescore is label/window sensitivity, not validation of a new matching model','Final score frontier common across definitions; target counts can differ because definitions differ','No intraday tick order reconstructed from daily OHLC']}
(P/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report['baseline_comparison'],indent=2));print('PATH_DIAGNOSTIC',json.dumps(scenarios))
