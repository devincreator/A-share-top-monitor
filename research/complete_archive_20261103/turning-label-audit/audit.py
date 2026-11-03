from pathlib import Path
from decimal import Decimal
import csv,json,ast,statistics,hashlib
P=Path(__file__).resolve().parent;root=P.parent;src=root/'dual80-research/run.py';nodes=[]
for n in ast.parse(src.read_text(encoding='utf-8-sig')).body:
 if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='folds' for t in n.targets):break
 if isinstance(n,(ast.Import,ast.ImportFrom,ast.Assign,ast.FunctionDef)):nodes.append(n)
b={'__file__':str(src)};exec(compile(ast.Module(body=nodes,type_ignores=[]),str(src),'exec'),b)
D=b['D'];C=[Decimal(str(v)) for v in b['C']];pos={d:i for i,d in enumerate(D)}
rawpath=root/'turning-research-canonical/raw/official/000985_20110802_20260825.response.json';raw=json.loads(rawpath.read_text(encoding='utf-8'))['data'];rawmap={f"{r['tradeDate'][:4]}-{r['tradeDate'][4:6]}-{r['tradeDate'][6:]}":r for r in raw}
# Independent segment-search reconstruction using exact Decimal closes.
def rebuild(th):
 cursor=0;side=0;hi=lo=0;out=[]
 for j in range(len(C)):
  hi=j if C[j]>=C[hi] else hi;lo=j if C[j]<=C[lo] else lo
  if C[j]<=C[hi]*(1-th):out.append((hi,j,'TOP'));side=-1;cursor=j;break
  if C[j]>=C[lo]*(1+th):out.append((lo,j,'BOTTOM'));side=1;cursor=j;break
 while side and cursor<len(C)-1:
  extreme=cursor;found=None
  for j in range(cursor+1,len(C)):
   if (side==1 and C[j]>=C[extreme]) or (side==-1 and C[j]<=C[extreme]):extreme=j
   hit=C[j]<=C[extreme]*(1-th) if side==1 else C[j]>=C[extreme]*(1+th)
   if hit:found=j;out.append((extreme,j,'TOP' if side==1 else 'BOTTOM'));break
  if found is None:break
  cursor=found;side=-side
 return out
summary={};details=[];cross=[]
for scale in [5,9]:
 expected=b['LABELS'][scale];complete=rebuild(Decimal(scale)/100);exact=complete[1:];assert exact==expected,('DECIMAL_MISMATCH',scale)
 for i in range(1,len(exact)):assert exact[i][2]!=exact[i-1][2] and exact[i][0]>=exact[i-1][1]
 lags=[];ties=[];intraday_diff=[];prev_confirm=complete[0][1] if complete else 0
 for k,(p,confirm,side) in enumerate(exact):
  first=prev_confirm;window=list(range(first,confirm+1));best=max(C[i] for i in window) if side=='TOP' else min(C[i] for i in window);dates=[i for i in window if C[i]==best]
  assert p==dates[-1]
  field='high' if side=='TOP' else 'low';valid=[i for i in window if rawmap[D[i]].get(field) is not None];ibest=(max if side=='TOP' else min)(Decimal(str(rawmap[D[i]][field])) for i in valid);iday=[i for i in valid if Decimal(str(rawmap[D[i]][field]))==ibest][-1]
  lag=confirm-p;lags.append(lag)
  item={'scale':scale,'side':side,'pivot_date':D[p],'pivot_close':str(C[p]),'confirmation_date':D[confirm],'confirmation_lag_sessions':lag,'same_segment_intraday_extreme_date':D[iday],'intraday_date_shift_sessions':iday-p,'last_tie_selection':len(dates)>1,'is_2016_plus':D[p]>='2016-01-01'};details.append(item)
  if len(dates)>1:ties.append(item)
  if iday!=p:intraday_diff.append(item)
  prev_confirm=confirm
 summary[str(scale)]={'confirmed_pivots_after_initial_exclusion':len(exact),'exact_decimal_reconstruction_matches':True,'alternation_and_confirmation_order_pass':True,'confirmation_lag_median':statistics.median(lags),'confirmation_lag_max':max(lags),'confirmation_more_than_7_sessions':sum(i>7 for i in lags),'equal_close_tie_pivots':len(ties),'same_segment_intraday_extreme_on_different_date':len(intraday_diff),'intraday_examples':intraday_diff[:5]}
# Scales need not have identical pivot dates; same direction closest 5% label diagnostic only.
for p,c,side in b['LABELS'][9]:
 near=min((g for g in b['LABELS'][5] if g[2]==side),key=lambda g:abs(g[0]-p));cross.append({'9_pivot':D[p],'direction':side,'nearest_5_pivot':D[near[0]],'gap':near[0]-p})
# Inspect actually issued baselines: same-day excluded by the locked contract.
file=root/'dual80-research/broad_experiments_v2/events.csv';ev=list(csv.DictReader(file.open(encoding='utf-8-sig')));same=[]
for e in ev:
 if e['configuration']!='original_rule' or e['status']!='FP':continue
 scale=int(e['task'].split('_')[0]);side=e['task'].split('_')[1];matches=[g for g in b['LABELS'][scale] if g[2]==side and D[g[0]]==e['date']]
 if matches:same.append({'task':e['task'],'preopen_alert_date':e['date'],'close_pivot_date':e['date'],'current_status':'FP','note':'Same day excluded by existing D+1..D+7 contract; close happens after preopen alert in real time.'})
report={'summary':summary,'same_day_false_alert_examples':same,'cross_scale_date_differences':cross,'raw_prices_sha256':hashlib.sha256(rawpath.read_bytes()).hexdigest(),'definition':'Alternating 5%/9% reversal of daily closing price; pivot is prior close extreme, confirmation later; final unconfirmed segment omitted','business_definition_certified':False,'old_labels_or_scores_modified':False,'note':'Intraday comparison uses the same close-defined segment only, not a rebuilt OHLC pivot series. OHLC sequence cannot generally resolve intraday high/low order.'}
(P/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
with (P/'pivot_details.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(details[0]));w.writeheader();w.writerows(details)
print(json.dumps({'summary':summary,'same_day_exclusions':same},ensure_ascii=False,indent=2))
