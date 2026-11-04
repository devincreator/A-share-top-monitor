from pathlib import Path
import ast,json
P=Path(__file__).resolve().parent;source=P/'phase2/run.py';nodes=[]
for n in ast.parse(source.read_text(encoding='utf-8-sig')).body:
 if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='folds' for t in n.targets):break
 if isinstance(n,(ast.Import,ast.ImportFrom,ast.Assign,ast.FunctionDef)):nodes.append(n)
m={'__file__':str(source)};exec(compile(ast.Module(body=nodes,type_ignores=[]),str(source),'exec'),m)
D=m['D'];records=[]
for scale in [5,9]:
 for side in ['TOP','BOTTOM']:
  for year in range(2016,2027):
   ids=[i for i,d in enumerate(D) if d.startswith(str(year))]
   if not ids:continue
   cutoff=ids[0]-1;last=cutoff-147
   goals=[g for g in m['LABELS'][scale] if g[2]==side and g[0]>=259 and g[1]+140<=cutoff and g[0]<=last+7]
   for mode in m['PLAN']['candidates']:
    aa=[a for a in m['ALL'][scale,side,mode] if 252<=a<=last];_,pairs=m['score'](aa,goals);matched={a for a,p in pairs}
    for a in aa:
     if a in matched:continue
     pp=[g for g in m['LABELS'][scale] if g[2]==side and 1<=g[0]-a<=7 and g[1]<=cutoff and g[1]+140>cutoff]
     if pp:records.append({'training_for_year':year,'task':f'{scale}_{side}','candidate':mode,'alert_date':D[a],'training_cutoff':D[cutoff],'pivot_date':D[pp[0][0]],'confirmation_date':D[pp[0][1]],'reason':'Confirmed by cutoff, but 140-session policy still pending; old score counted FP'})
result={'records':records,'candidate_rows':len(records),'unique_alerts':len({(r['task'],r['alert_date']) for r in records}),'unique_pivots':len({(r['task'],r['pivot_date']) for r in records}),'true_future_label_leakage_demonstrated':False}
(P/'pending_score_review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))
