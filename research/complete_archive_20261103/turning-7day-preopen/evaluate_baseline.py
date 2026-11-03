from pathlib import Path
import importlib.util,json,csv,io,hashlib,copy,sys
from datetime import date

HERE=Path(__file__).resolve().parent
def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
base=module('v101_frozen',HERE/'inputs/v101_frozen.py')
independent=module('v102_matching',HERE/'inputs/v102_frozen.py')
LEAD=7

def csvwrite(name,rows,fields):
 with (HERE/name).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def evaluate():
 dates,closes,pivots,hashes=base.load_sources(HERE/'inputs/index_000985_prices_20220223_20261020.csv',HERE/'inputs/partial_v52_derived_objective_pivots.csv')
 alerts,_=base.generate_alerts(dates,closes)
 pos={d.isoformat():i for i,d in enumerate(dates)};pos_date={d:i for i,d in enumerate(dates)}
 # Only the evaluation window changes. Do not tune signal thresholds or cooldowns.
 contract={'lead_min':1,'lead_max':LEAD,'decision_clock':'09:20 Asia/Shanghai before open','same_day_extreme_counts':False,'tasks':list(base.RULES),'index':'000985.CSI','objective_labels':'Frozen alternating close-reversal 5% and 9% labels; exact extreme date, not later confirmation date','one_to_one':'One formal-start alert to at most one same-direction same-scale pivot, and conversely. No cross-task pooling. Earliest lexicographic maximum-cardinality assignment.','precision':'TP/(TP+FP)','recall':'TP/(TP+FN)','required_each_task':{'precision':0.8,'recall':0.8},'zero_denominator':'UNDEFINED_NOT_PASS','daily_status_updates_are_alerts':False,'duplicates_against_used_pivot':'Unmatched, never counted as another hit','latest_incomplete_events':'PENDING with explicit count, never silently deleted','maturity_buffer_after_confirmation_sessions':base.MATURITY_BUFFER,'maturity_policy':'Preserved from existing frozen baseline, not optimized for the 7-day score','historical_PIT_certified':False,'source_release_time_requirement':'Every used raw datum must have certified publication/first availability no later than actual decision time; simply shifting to D-1 is insufficient','model_training_labels':'May enter training only after their confirmation/availability cutoff; exclude split-boundary overlapping outcomes','blind_validation':'Freeze rules first, evaluate subsequently unseen prospective evidence separately; no claim on repeatedly studied history','top_bottom_alert_alternation':'Not imposed: user requested one-to-one matching. Suppressing a previously issued same-side alert retrospectively is forbidden.'}
 metrics={};event_rows=[];pivot_rows=[]
 for task,rule in base.RULES.items():
  aa=sorted([a for a in alerts if a['task']==task],key=lambda r:(r['date'],r['id']))
  pp=sorted([p for p in pivots if p['scale']==rule['scale'] and p['direction']==rule['direction']],key=lambda r:(r['date'],r['id']))
  left=[p for p in pp if p['first_segment_left_censored'].lower()=='true'];eligible=[p for p in pp if p not in left]
  mature=[p for p in eligible if pos[p['confirmation_date']]+base.MATURITY_BUFFER<len(dates)]
  pending=[p for p in eligible if p not in mature]
  matched=independent.independent_max_match(aa,mature,pos,LEAD)
  greedy=base.match_chronological(aa,mature,pos_date,LEAD)
  assert len(matched)==len(greedy),'Independent assignment cardinalities disagree'
  matched_ids={p['id'] for p in matched.values()};assert len(matched_ids)==len(matched)
  counts={'TP':0,'FP':0,'PENDING':0,'EXCLUDED_LEFT_CENSORED':0}
  for a in aa:
   i=pos[a['date']];p=matched.get(a['id'])
   assert a['last_price_observation_index']==i-1
   if p:status='TP';assert 1<=pos[p['date']]-i<=LEAD
   elif any(1<=pos[x['date']]-i<=LEAD for x in left):status='EXCLUDED_LEFT_CENSORED'
   elif any(1<=pos[x['date']]-i<=LEAD for x in pending):status='PENDING'
   elif i+LEAD+base.MATURITY_BUFFER<len(dates):status='FP'
   else:status='PENDING'
   counts[status]+=1
   event_rows.append({'alert_id':a['id'],'task':task,'alert_date':a['date'],'decision_at':a['decision_at'],'last_price_observation_date':a['last_price_observation_date'],'status':status,'pivot_id':p['id'] if p else '', 'pivot_date':p['date'] if p else '', 'pivot_confirmation_date':p['confirmation_date'] if p else '', 'lead_trading_sessions':pos[p['date']]-i if p else '', 'historical_release_verified':False})
  for p in pp:
   a=next((a for a in aa if matched.get(a['id'],{}).get('id')==p['id']),None)
   status='EXCLUDED_LEFT_CENSORED' if p in left else 'PENDING' if p in pending else 'TP' if a else 'FN'
   pivot_rows.append({'pivot_id':p['id'],'task':task,'pivot_date':p['date'],'confirmation_date':p['confirmation_date'],'status':status,'alert_id':a['id'] if a else '', 'alert_date':a['date'] if a else ''})
  tp=counts['TP'];fp=counts['FP'];fn=len(mature)-tp
  precision=tp/(tp+fp) if tp+fp else None;recall=tp/(tp+fn) if tp+fn else None
  metrics[task]={**counts,'FN':fn,'mature_pivots':len(mature),'pending_pivots':len(pending),'all_formal_start_alerts':len(aa),'precision':precision,'recall':recall,'dual80_pass':precision is not None and recall is not None and precision>=.8 and recall>=.8}
 report={'evaluation':'FROZEN_PREOPEN_PRICE_ONLY_BASELINE_RESCORING_7_SESSIONS','source_period':{'first':dates[0].isoformat(),'last':dates[-1].isoformat(),'observed_trading_dates':len(dates)},'source_sha256':hashes,'contract':contract,'task_metrics':metrics,'alert_generation_rules_unchanged':True,'only_evaluation_window_changed':True,'independent_maximum_matching_cardinality_crosscheck_pass':True,'number_of_parameter_searches':0,'source_asof_publication_verified':False,'calendar_independently_certified':False,'sample_is_unseen':False,'research_only':True,'formal_signal_allowed':False,'production_updated':False,'double80_achieved':all(v['dual80_pass'] for v in metrics.values())}
 csvwrite('alert_to_pivot_7day.csv',event_rows,list(event_rows[0]));csvwrite('pivot_to_alert_7day.csv',pivot_rows,list(pivot_rows[0]));(HERE/'baseline_7day.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');(HERE/'evaluation_contract.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2),encoding='utf-8')
 return report
if __name__=='__main__':
 r=evaluate();print(json.dumps(r['task_metrics'],ensure_ascii=False,indent=2))
