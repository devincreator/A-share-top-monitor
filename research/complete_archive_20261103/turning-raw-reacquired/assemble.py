"""Assemble only newly retrieved provider receipts; legacy CSV is audit-only."""
import csv,json,re,hashlib,datetime
from decimal import Decimal,InvalidOperation
from pathlib import Path
ROOT=Path(__file__).resolve().parent
START='2011-08-02';END='2026-08-25'
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def numeric(s):
 s=(s or '').strip().replace(',','').replace('%','')
 factor=Decimal(10**12) if s.endswith('万亿') else Decimal(10**8) if s.endswith('亿') else Decimal(10**4) if s.endswith('万') else Decimal(1)
 try:
  v=Decimal(s.replace('万亿','').replace('亿','').replace('万',''))*factor
  return v if v.is_finite() else None
 except InvalidOperation:return None
def decode_answer(raw):
 if not raw.get('ok'):return []
 result=[]
 for b in raw.get('data',{}).get('result',{}).get('content',[]):
  if b.get('type')!='text':continue
  try:o=json.loads(b['text'])
  except (ValueError,TypeError):continue
  a=o.get('data',{}).get('answer','')
  if o.get('code')==1 and a and not re.search('截断|部分数据',a):result.append(a)
 return result
def table(answer):
 header=None
 for line in answer.splitlines():
  if not line.strip().startswith('|'):continue
  cells=[v.strip() for v in line.strip().strip('|').split('|')]
  if '日期' in cells:header=cells;continue
  if header and len(cells)==len(header) and any(re.fullmatch(r'\d{4}-?\d{2}-?\d{2}',c) for c in cells):yield dict(zip(header,cells))
def get(r,prefixes):return next((v for k,v in r.items() if any(k.startswith(p) for p in prefixes)),None)
def main():
 progress=load(ROOT/'progress.json');accepted={r['file'] for r in progress['records']}
 values={};conflicts=[];raw_manifest=[];excluded=[];precision=[];alias_precision=[]
 def put(d,field,value,src,raw_value=None,provider_code=None):
  if not START<=d<=END or value is None:return
  key=(d,field)
  if key in values and values[key]['value']!=value:
   previous=values[key]
   allowed={'hs300_close':{'000300.SH','399300.SZ'},'zz1000_close':{'000852.SH','399852.SZ'}}
   if field in allowed and {previous.get('provider_code'),provider_code}==allowed[field]:
    quantum=Decimal(10)**max(previous['value'].as_tuple().exponent,value.as_tuple().exponent)
    if abs(previous['value']-value)<quantum:
     alias_precision.append({'date':d,'field':field,'first_value':str(previous['value']),'later_value':str(value),'first_code':previous.get('provider_code'),'later_code':provider_code,'source_file':src,'lower_precision_quantum':str(quantum),'classification':'DIFFERENT_BROADCAST_CODE_DISPLAY_PRECISION_KEEP_SH_WHEN_PRESENT'})
     if provider_code.endswith('.SH'):values[key]={'value':value,'source':src,'raw_display':raw_value,'provider_code':provider_code}
     return
   conflicts.append({'date':d,'field':field,'first':str(values[key]['value']),'later':str(value),'first_source':values[key]['source'],'later_source':src});return
  values[key]={'value':value,'source':src,'raw_display':raw_value,'provider_code':provider_code}
 files=[(p,load(p)['raw']) for p in sorted((ROOT/'raw').glob('*.json')) if p.name in accepted]
 # These are independently acquired iFinD source receipts, not old model inputs.
 for p in sorted((ROOT/'raw/finance_2022plus').glob('*_raw.json')):files.append((p,load(p)))
 for p,raw in files:
  src=p.relative_to(ROOT).as_posix();raw_manifest.append({'file':src,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
  for answer in decode_answer(raw):
   for r in table(answer):
    ds=get(r,['日期']);ds=ds.replace('-','');d=f'{ds[:4]}-{ds[4:6]}-{ds[6:8]}'
    code=r.get('证券代码')
    if code:
     if code not in ['000985.CSI','000300.SH','399300.SZ','000852.SH','399852.SZ']:continue
     if code=='000985.CSI':
      c=get(r,['收盘价']);a=get(r,['成交金额','成交额']);t=get(r,['换手率'])
      price=numeric(c);amount=numeric(a);rate=numeric(t)
      # Exclude synthetic holiday/weekend carry-forward quotes, never forward-fill.
      if datetime.date.fromisoformat(d).weekday()>=5 or amount is None or amount<=0:
       excluded.append({'date':d,'source':src,'reason':'NON_TRADING_OR_NO_AMOUNT_PROVIDER_ROW','close_display':c});continue
      put(d,'all_a_close',price,src,c);put(d,'turnover',amount,src,a);put(d,'turnover_rate',rate,src,t)
      if a and any(x in a for x in ['万','亿']):precision.append({'date':d,'field':'turnover','display':a,'note':'display-scaled, not exact-yuan certified'})
     else:put(d,'hs300_close' if code in ['000300.SH','399300.SZ'] else 'zz1000_close',numeric(get(r,['收盘价'])),src,get(r,['收盘价']),code)
    else:
     # Column labels and explicit yuan scale belong to this receipt, not the prompt.
     sh=get(r,['上交所','上海证券交易所']);sz=get(r,['深交所','深圳证券交易所'])
     if sh is not None and sz is not None:
      if '亿元' not in answer:raise ValueError('Unknown finance unit '+src)
      put(d,'finance_sh_yuan',numeric(sh)*10**8 if numeric(sh) is not None else None,src,sh)
      put(d,'finance_sz_yuan',numeric(sz)*10**8 if numeric(sz) is not None else None,src,sz)
 fields=['all_a_close','hs300_close','zz1000_close','turnover','turnover_rate','financing_balance']
 dates=sorted({d for d,f in values if f=='all_a_close'})
 rows=[];lineage=[];missing=[];invalid=[]
 for d in dates:
  r={'date':d}
  for f in fields:
   if f=='financing_balance':
    sh=values.get((d,'finance_sh_yuan'));sz=values.get((d,'finance_sz_yuan'))
    v=sh['value']+sz['value'] if sh and sz else None
    source=' | '.join(sorted({x['source'] for x in [sh,sz] if x}))
   else:
    item=values.get((d,f));v=item['value'] if item else None;source=item['source'] if item else ''
   r[f]=str(v) if v is not None else ''
   lineage.append({'date':d,'field':f,'source_file':source,'provider_code':values.get((d,f),{}).get('provider_code') or ('S004273896 + S004273905' if f=='financing_balance' else '000985.CSI'),'status':'PROVIDER_HISTORY_REACQUIRED_NOT_PIT' if v is not None else 'MISSING'})
   if v is None:missing.append({'date':d,'field':f})
   elif v<=0:invalid.append({'date':d,'field':f,'value':str(v),'reason':'NONPOSITIVE_RAW_VALUE'})
  rows.append(r)
 def writecsv(name,items,columns=None):
  if not items:return
  with (ROOT/'tables'/name).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=columns or list(items[0]));w.writeheader();w.writerows(items)
 writecsv('raw_six_fields.csv',rows);writecsv('field_lineage.csv',lineage);writecsv('amount_precision.csv',precision);writecsv('alias_display_precision.csv',alias_precision)
 # Always write current empty reports too; stale diagnostic rows must not survive a repaired run.
 writecsv('missing_fields.csv',missing or [],['date','field']) if missing else (ROOT/'tables/missing_fields.csv').write_text('date,field\n',encoding='utf-8-sig')
 writecsv('invalid_fields.csv',invalid) if invalid else (ROOT/'tables/invalid_fields.csv').write_text('date,field,value,reason\n',encoding='utf-8-sig')
 writecsv('source_conflicts.csv',conflicts) if conflicts else (ROOT/'tables/source_conflicts.csv').write_text('date,field,first,later,first_source,later_source\n',encoding='utf-8-sig')
 finance_rows=[{'date':d,'balance_sh_yuan':str(values[(d,'finance_sh_yuan')]['value']) if (d,'finance_sh_yuan') in values else '', 'balance_sz_yuan':str(values[(d,'finance_sz_yuan')]['value']) if (d,'finance_sz_yuan') in values else ''} for d in dates]
 writecsv('financing_sh_sz.csv',finance_rows)
 for field in fields:writecsv(field+'.csv',[{'date':r['date'],field:r[field]} for r in rows])
 # Original dates and values enter only comparison outputs, never rows above.
 oldpath=ROOT.parent/'turning-rebuild/sources/a_share_5_9_daily_reconstruction.csv'
 old=list(csv.DictReader(oldpath.open(encoding='utf-8-sig')));fresh={r['date']:r for r in rows};comparison=[];scope={}
 for f in fields:
  changes=[]
  for o in old:
   r=fresh.get(o['date']);a=numeric(o[f]);b=numeric(r[f]) if r else None
   if a is not None and b is not None:
    delta=b-a;changes.append(abs(delta));comparison.append({'date':o['date'],'field':f,'old':str(a),'fresh':str(b),'difference':str(delta)})
  scope[f]={'received_nonmissing_days':sum(bool(r[f]) for r in rows),'overlap_days':len(changes),'max_abs_difference':str(max(changes)) if changes else None}
 writecsv('legacy_comparison.csv',comparison)
 olddates={r['date'] for r in old}
 audit={'requested_start':START,'requested_end':END,'first_observed_market_day':dates[0] if dates else None,'last_observed_market_day':dates[-1] if dates else None,'market_days_received':len(dates),'provider_batches_completed':progress['completed'],'failed_batches':progress['failed'],'missing_field_count':len(missing),'invalid_field_count':len(invalid),'conflicts':len(conflicts),'old_market_dates_absent_from_new_source':sorted(olddates-set(dates)),'fields':scope,'legacy_values_used_as_input':False,'calendar_is_officially_certified':False,'source_scope_identical_to_legacy':False,'historical_original_publication_certified':False,'all_six_fields_complete':not missing and not invalid and not conflicts and not(olddates-set(dates)) and bool(dates) and dates[-1]==END,'note':'numeric completeness is separate from source-definition equivalence and historical as-of certification'}
 save(ROOT/'coverage_audit.json',audit);save(ROOT/'input_manifest.json',raw_manifest);save(ROOT/'excluded_rows.json',excluded)
 print(json.dumps({k:v for k,v in audit.items() if k not in ['old_market_dates_absent_from_new_source','failed_batches']},ensure_ascii=False))
if __name__=='__main__':main()
