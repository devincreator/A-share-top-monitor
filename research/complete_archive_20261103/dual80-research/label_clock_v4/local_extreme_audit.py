from pathlib import Path
import csv,json
P=Path(r'E:\Codex\量化\dual80-research/label_clock_v4');R=P.parent.parent
D=[r['date'] for r in csv.DictReader((R/'turning-research-canonical/tables/research_inputs.csv').open(encoding='utf-8-sig'))];pos={d:i for i,d in enumerate(D)};raw=json.loads((R/'turning-research-canonical/raw/official/000985_20110802_20260825.response.json').read_text(encoding='utf-8'))['data'];byday={r['tradeDate']:r for r in raw};bars=[byday[d.replace('-','')] for d in D];labels=list(csv.DictReader((R/'turning-label-comparison/all_labels.csv').open(encoding='utf-8-sig')));summary=[];cases=[]
for definition in ['close','intraday_extrema_close_confirm']:
 for scale in ['5','9']:
  ll=[l for l in labels if l['definition']==definition and l['scale']==scale];count=0;maxdiff=0
  for j,l in enumerate(ll[1:-1],1):
   a=pos[ll[j-1]['pivot_date']]+1;b=pos[ll[j+1]['pivot_date']]-1
   if a>b:continue
   field='close' if definition=='close' else 'high' if l['direction']=='TOP' else 'low';f=max if l['direction']=='TOP' else min;q=f(range(a,b+1),key=lambda i:float(bars[i][field]));p=float(l['pivot_price']);v=float(bars[q][field]);better=v>p+1e-8 if l['direction']=='TOP' else v<p-1e-8
   if better:
    delta=abs(v/p-1)*100;count+=1;maxdiff=max(maxdiff,delta);cases.append({'definition':definition,'scale':scale,'side':l['direction'],'marked_date':l['pivot_date'],'marked_price':p,'confirmed_date':l['confirmation_date'],'more_extreme_date':D[q],'more_extreme_price':v,'difference_pct':delta,'interval_prior_opposite':ll[j-1]['pivot_date'],'interval_next_opposite':ll[j+1]['pivot_date'],'more_extreme_after_confirmation':D[q]>l['confirmation_date']})
  summary.append({'definition':definition,'scale':scale,'interior_labels':len(ll)-2,'not_extreme_between_adjacent_opposite_dates':count,'max_difference_pct':maxdiff})
(P/'local_extreme_audit.json').write_text(json.dumps({'summary':summary,'cases':cases,'note':'Diagnostic of hindsight extrema between adjacent marked opposite dates, excluding endpoints; not a proposed replacement labeling rule. Confirmed directional reversal labels need not equal these hindsight extrema.'},ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'summary':summary,'cases':cases[:12]},ensure_ascii=False,indent=2))
