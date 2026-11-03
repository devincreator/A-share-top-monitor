from pathlib import Path
import runpy,contextlib,io,json,collections,random
P=Path(__file__).resolve().parent
with contextlib.redirect_stdout(io.StringIO()):m=runpy.run_path(str(P/'run.py'))
D,C=m['D'],m['C'];labels=m['LABELS'];signal=m['ALL'];score=m['score']
def eligible(scale,side,di):
 i=di-1;w,mom,lim,move=(63,20,.9,.015) if scale==5 else (126,60,.95,.055)
 if i<max(w-1,mom):return False
 lo=min(C[i-w+1:i+1]);hi=max(C[i-w+1:i+1]);loc=(C[i]-lo)/(hi-lo) if hi>lo else .5;ret=C[i]/C[i-mom]-1
 return loc>=lim and ret>=move if side=='TOP' else loc<=1-lim and ret<=-move
out={};details=[]
for scale in [5,9]:
 for side in ['TOP','BOTTOM']:
  task=f'{scale}_{side}';fn=collections.Counter();fp=collections.Counter();targets=potential=0
  for year in range(2016,2027):
   ix=[i for i,d in enumerate(D) if d.startswith(str(year))]
   if not ix:continue
   start,end=ix[0],ix[-1];last=min(end-7,len(D)-148)
   goals=[g for g in labels[scale] if g[2]==side and start+7<=g[0]<=last+7 and g[1]+140<len(D)]
   aa=[a for a in signal[scale,side,'baseline'] if start<=a<=last];met,pairs=score(aa,goals);matched_a={a for a,p in pairs};matched_p={p for a,p in pairs}
   possible_days=[di for di in range(start,last+1) if eligible(scale,side,di)]
   _,oracle=score(possible_days,goals);targets+=len(goals);potential+=len(oracle)
   for p,c,t in goals:
    if p in matched_p:continue
    candidates=[di for di in range(max(start,p-7),p) if eligible(scale,side,di)]
    kind='NO_ELIGIBLE_DAY_IN_WINDOW' if not candidates else 'ELIGIBLE_BUT_EDGE_OR_COOLDOWN_OR_MATCHING_BLOCKED';fn[kind]+=1
    details.append({'task':task,'year':year,'event':'FN','date':D[p],'reason':kind,'eligible_dates':[D[i] for i in candidates]})
   for a in aa:
    if a in matched_a:continue
    next_goals=[g[0]-a for g in labels[scale] if g[2]==side and g[0]>a]
    gap=min(next_goals) if next_goals else None
    kind='MATCH_COLLISION_OR_SCORING_BOUNDARY' if gap is not None and gap<=7 else 'NEXT_PIVOT_8_TO_20_SESSIONS' if gap is not None and gap<=20 else 'NO_SAME_DIRECTION_PIVOT_WITHIN_20_SESSIONS'
    fp[kind]+=1;details.append({'task':task,'year':year,'event':'FP','date':D[a],'reason':kind,'next_pivot_gap':gap})
  out[task]={'fn_reasons':dict(fn),'fp_reasons':dict(fp),'scored_pivots':targets,'maximum_matched_pivots_if_alert_on_every_baseline_eligible_day':potential,'gate_recall_upper_bound':potential/targets if targets else None,'oracle_is_hindsight_diagnostic_only':True}
# Independent exhaustive matcher checks, including seven-session boundaries.
rng=random.Random(20261102)
def brute(aa,pp,i=0,used=frozenset()):
 if i==len(aa):return 0
 best=brute(aa,pp,i+1,used)
 for j,p in enumerate(pp):
  if j not in used and 1<=p[0]-aa[i]<=7:best=max(best,1+brute(aa,pp,i+1,used|{j}))
 return best
for _ in range(500):
 aa=sorted(rng.sample(range(20),rng.randrange(6)));pp=[(i,i+1,'TOP') for i in sorted(rng.sample(range(20),rng.randrange(6)))];assert score(aa,pp)[0]['tp']==brute(aa,pp)
r={'diagnostics':out,'details':details,'exhaustive_match_checks_passed':500,'PIT_certified':False,'unseen_sample':False,'interpretation':'Upper bound applies only to candidates restricted to current baseline eligibility gate under the same scored opportunities. It is not a deployable model or a universal predictability bound.'}
(P/'diagnostic_result.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(out,indent=2))
