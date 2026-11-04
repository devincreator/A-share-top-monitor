from pathlib import Path
import ast,json,csv,collections,math,hashlib
P=Path(r'E:\Codex\量化\dual80-research');source=P/'run.py';nodes=[]
for n in ast.parse(source.read_text(encoding='utf-8-sig')).body:
 if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='folds' for t in n.targets):break
 if isinstance(n,(ast.Import,ast.ImportFrom,ast.Assign,ast.FunctionDef)):nodes.append(n)
m={'__file__':str(source)};exec(compile(ast.Module(body=nodes,type_ignores=[]),str(source),'exec'),m)
D,C=m['D'],m['C'];pos={d:i for i,d in enumerate(D)}
rows=list(csv.DictReader((P/'events.csv').open(encoding='utf-8-sig')));diagnostic=json.loads((P/'diagnostic_result.json').read_text(encoding='utf-8'));prior=json.loads((P/'result.json').read_text(encoding='utf-8'))
late={};fn={};count_constraints={}
def features(scale,side,di):
 i=di-1;w,mom,lim,move=(63,20,.9,.015) if scale==5 else (126,60,.95,.055)
 look=C[i-w+1:i+1];lo=min(look);hi=max(look);loc=(C[i]-lo)/(hi-lo) if hi>lo else .5;ret=C[i]/C[i-mom]-1
 return loc,ret,(loc>=lim if side=='TOP' else loc<=1-lim),(ret>=move if side=='TOP' else ret<=-move)
for task in ['5_TOP','5_BOTTOM','9_TOP','9_BOTTOM']:
 scale=int(task.split('_')[0]);side=task.split('_')[1];ct=collections.Counter();examples=[]
 for r in rows:
  if r['arm']!='baseline' or r['task']!=task or r['result']!='FP':continue
  i=pos[r['alert_date']];same=[g for g in m['LABELS'][scale] if g[2]==side and g[0]==i];past=[g for g in m['LABELS'][scale] if g[2]==side and g[0]<i]
  if same:ct['same_day']+=1
  if past and i-past[-1][0]<=7:ct['late_1_to_7']+=1;examples.append({'alert':D[i],'pivot':D[past[-1][0]],'lag':i-past[-1][0]})
 late[task]={'counts':dict(ct),'examples':examples[:3]}
 misses=[r for r in diagnostic['details'] if r['task']==task and r['event']=='FN' and r['reason']=='NO_ELIGIBLE_DAY_IN_WINDOW'];locfail=momfail=0
 for r in misses:
  pi=pos[r['date']];f=[features(scale,side,di) for di in range(pi-7,pi)]
  locfail+=not any(a[2] for a in f);momfail+=not any(a[3] for a in f)
 fn[task]={'misses_with_no_eligible_day':len(misses),'never_meets_location':locfail,'never_meets_momentum':momfail}
 b=prior['metrics'][task]['baseline'];A=b['tp']+b['fp'];N=b['tp']+b['fn'];count_constraints[task]={'alerts':A,'pivots':N,'required_hits_for_dual80':max(math.ceil(.8*A),math.ceil(.8*N)),'possible_hits_at_most':min(A,N),'alarm_count_feasible_band_given_hindsight_pivot_count':[math.ceil(.8*N),math.floor(N/.8)]}
examples=[]
for date,scale,side in [('2016-02-22',5,'TOP'),('2018-03-12',5,'TOP'),('2020-07-24',5,'BOTTOM')]:
 pi=pos[date];f=[features(scale,side,di) for di in range(pi-7,pi)];examples.append({'pivot_date':date,'task':f'{scale}_{side}','last_7_forecast_dates':[D[pi-7],D[pi-1]],'prior_input_dates':[D[pi-8],D[pi-2]],'location_min':min(a[0] for a in f),'location_max':max(a[0] for a in f),'momentum_min':min(a[1] for a in f),'momentum_max':max(a[1] for a in f)})
report={'review_date':'2026-11-02','sources_sha256':{name:hashlib.sha256((P/name).read_bytes()).hexdigest() for name in ['run.py','phase2/run.py','result.json','diagnostic_result.json']},'late_alerts':late,'FN_gate_failures':fn,'concrete_examples':examples,'alarm_count_necessary_conditions_not_live_budget':count_constraints,'prior_claim_correction':'No future same-direction pivot within20 does not distinguish late signals from unrelated signals. 23/104 FP are on or 1..7 sessions after a same-direction pivot.','production_updated':False}
(P/'architecture_review_evidence.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'gate_failures':fn,'examples':examples,'late':{k:v['counts'] for k,v in late.items()}},indent=2))
