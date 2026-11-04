from pathlib import Path
import csv,json,hashlib,statistics,math,re
from decimal import Decimal,ROUND_HALF_UP
from audit_float_a import load_inputs
P=Path(__file__).resolve().parent

def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def save(p,o):p.write_text(json.dumps(o,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def readcsv(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
def writecsv(name,rows):
 with (P/'tables'/name).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def quantum(text):
 s=text.replace(',','');scale=Decimal(10**12) if s.endswith('万亿') else Decimal(10**8) if s.endswith('亿') else Decimal(10**4) if s.endswith('万') else Decimal(1)
 v=Decimal(s.replace('万亿','').replace('亿','').replace('万',''));return scale*Decimal(10)**v.as_tuple().exponent

def main():
 official,observed,conflicts,rejected=load_inputs()
 missing=sorted(set(official)-set(observed));assert not missing,('MISSING',len(missing),missing[:12]);assert not conflicts,('CONFLICTS',conflicts[:2])
 fresh={r['date']:r for r in readcsv(P.parent/'turning-raw-reacquired/tables/raw_six_fields.csv')}
 source_rows=readcsv(P/'tables/research_inputs.csv');assert {r['date'] for r in source_rows}==set(official)
 backup=P/'tables/research_inputs_before_turnover_selection.csv'
 if not backup.exists():backup.write_bytes((P/'tables/research_inputs.csv').read_bytes())
 rates=[];out=[];jumps=[];previous=None
 for r in source_rows:
  d=r['date'];o=observed[d];vol=Decimal(o['official_volume_shares']);shares=Decimal(o['float_a_shares']);half=quantum(o['float_a_display'])/2
  rate=vol/shares*100;lower=vol/(shares+half)*100;upper=vol/(shares-half)*100
  assert vol>0 and shares>half and rate.is_finite() and 0<rate<100
  native=Decimal(fresh[d]['turnover_rate'])
  rates.append({**o,'turnover_rate_pct':str(rate),'turnover_rate_lower_from_display_precision_pct':str(lower),'turnover_rate_upper_from_display_precision_pct':str(upper),'ifind_native_turnover_rate_pct':str(native),'native_minus_recomputed_pct_points':str(native-rate),'denominator_display_quantum_shares':str(half*2),'definition':'CSI official volume / iFinD index float A shares * 100','status':'RESEARCH_DERIVED_SAME_INDEX_ASSUMPTION_NOT_CONSTITUENT_CERTIFIED'})
  out.append({**r,'turnover_rate':str(rate)})
  if previous:
   pct=(shares/previous[1]-1)*100
   if abs(pct)>Decimal(3):jumps.append({'date':d,'previous_date':previous[0],'change_pct':str(pct),'previous_shares':str(previous[1]),'current_shares':str(shares)})
  previous=d,shares
 writecsv('turnover_rate_recomputed.csv',rates);writecsv('research_inputs_with_recomputed_turnover.csv',out);writecsv('research_inputs.csv',out)
 # These copies hold only the comparison experiment; all other five fields are identical.
 writecsv('research_inputs_ifind_native_turnover_control.csv',[{**r,'turnover_rate':fresh[r['date']]['turnover_rate']} for r in out])
 writecsv('research_inputs_turnover_lower.csv',[{**r,'turnover_rate':v['turnover_rate_lower_from_display_precision_pct']} for r,v in zip(out,rates)])
 writecsv('research_inputs_turnover_upper.csv',[{**r,'turnover_rate':v['turnover_rate_upper_from_display_precision_pct']} for r,v in zip(out,rates)])
 lineage=[r for r in readcsv(P/'tables/field_lineage.csv') if r['field']!='turnover_rate']
 for o in rates:lineage.append({'date':o['date'],'field':'turnover_rate','source':o['source_file']+' | raw/official/000985_20110802_20260825.response.json','transform':o['definition'],'status':o['status']})
 writecsv('field_lineage.csv',lineage)
 yearly=[]
 for y in sorted({r['date'][:4] for r in rates}):
  rs=[r for r in rates if r['date'].startswith(y)];relative=[100*(float(r['ifind_native_turnover_rate_pct'])/float(r['turnover_rate_pct'])-1) for r in rs]
  yearly.append({'year':y,'days':len(rs),'native_minus_recomputed_median_relative_pct':statistics.median(relative),'max_abs_difference_pct_points':max(abs(float(r['native_minus_recomputed_pct_points'])) for r in rs)})
 audit={'rows':len(rates),'start':rates[0]['date'],'end':rates[-1]['date'],'missing':0,'conflicts':0,'invalid':0,'official_volume_matched_to_provider_at_display_precision_days':sum(r['volume_cross_check_status']=='MATCH_AT_DISPLAY_PRECISION' for r in rates),'official_volume_disagreement_dates':[r['date'] for r in rates if r['volume_cross_check_status']!='MATCH_AT_DISPLAY_PRECISION'],'denominator_distinct_values':len({r['float_a_shares'] for r in rates}),'denominator_jumps_over_3pct':jumps,'annual_native_vs_recomputed':yearly,'definition_is_project_authored':True,'vendor_native_formula_verified':False,'historical_constituents_independently_verified':False,'historical_publication_times_certified':False,'denominator_source':'iFinD MCP index_data, table field 流通A股（单位：股）, 000985.CSI','rounding_interval_assumes_provider_rounds_to_nearest':True,'scope_assumption':'Provider historical index float A shares and official volume refer to the same date/index universe; not independently summed stock by stock','rejected_response_or_row_count':len(rejected)}
 save(P/'turnover_selection_audit.json',audit)
 policy=load(P/'source_policy.json');policy['turnover_rate']={'selected':'PROJECT_RECOMPUTED_FLOAT_A_SHARE_TURNOVER','formula':'Official CSI 000985 daily tradingVol (shares) / iFinD 000985.CSI historical 流通A股 (shares) * 100','unit':'percent, 2 means 2%','native_vendor_rate':'retained separately; exact vendor formula unresolved','assumption':audit['scope_assumption'],'use':'research baseline, not certified reproduction of legacy turnover'};policy['full_model_ready']=True;policy['full_model_ready_scope']='local research replay only; production and backtest performance not validated';save(P/'source_policy.json',policy)
 val=load(P/'validation.json');val.update(accepted_fields=6,turnover_rate_blank=0,full_model_ready=True,full_model_ready_scope='local research replay only',turnover_native_formula_verified=False,turnover_derived_definition_explicit=True,missing_accepted_values=0,reason='Six positive numeric inputs complete. Recomputed turnover is a new research definition, not certified legacy equivalence.');save(P/'validation.json',val)
 manifest=load(P/'input_manifest.json');existing={r['file'] for r in manifest}
 for f in sorted((P/'raw/turnover').rglob('*.json')):
  name=str(f.relative_to(P))
  if name not in existing:manifest.append({'file':name,'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'bytes':f.stat().st_size})
 save(P/'input_manifest.json',manifest)
 print(json.dumps({'rows':len(rates),'distinct_denominators':audit['denominator_distinct_values'],'jumps_over_3pct':jumps,'annual_comparison':yearly},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
