"""Restore original raw columns; append separately identified iFinD candidates."""
import csv,json,re,hashlib
from pathlib import Path
from decimal import Decimal
ROOT=Path(__file__).resolve().parent
FIELDS=['date','all_a_close','hs300_close','zz1000_close','turnover','turnover_rate','financing_balance']
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def number(s):
 s=s.strip().replace(',','')
 if not s or s in ['--','—','null']:return None
 factor=10**12 if s.endswith('万亿') else 10**8 if s.endswith('亿') else 1
 try:return float(Decimal(s.replace('万亿','').replace('亿',''))*factor)
 except Exception:return None
def tables(file):
 receipt=load(file)
 if not receipt.get('ok'):raise ValueError('Provider failed '+str(file))
 for c in receipt['data']['result']['content']:
  obj=json.loads(c['text']);answer=obj.get('data',{}).get('answer','')
  if '截断' in answer or '部分数据' in answer:raise ValueError('Truncated '+str(file))
  header=None
  for line in answer.splitlines():
   if not line.startswith('|'):continue
   cells=[x.strip() for x in line.strip().strip('|').split('|')]
   if '证券代码' in cells:header=cells;continue
   if header and cells and re.match(r'^\d{6}\.',cells[0]):yield dict(zip(header,cells))
def pick(r,name):return next((v for k,v in r.items() if k.startswith(name)),None)
def main():
 old=list(csv.DictReader((ROOT/'sources/a_share_5_9_daily_reconstruction.csv').open(encoding='utf-8-sig')))
 rows=[{k:r[k] if k=='date' else number(r[k]) for k in FIELDS} for r in old]
 datesfile=ROOT/'sources/pinned_index_sessions.csv'
 calendar={r['date'] for r in csv.DictReader(datesfile.open(encoding='utf-8'))}
 candidate={};excluded=[]
 for kind in ['market','style']:
  for p in sorted((ROOT/'sources').glob(f'ifind_{kind}_2026??.json')):
   for r in tables(p):
    stamp=pick(r,'日期');d=f'{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}'
    code=r['证券代码']
    if code not in ['000985.CSI','000300.SH','000852.SH']:continue
    if d not in calendar:excluded.append({'date':d,'code':code,'reason':'NOT_IN_PINNED_INDEX_SESSION_SEQUENCE'});continue
    item=candidate.setdefault(d,{'date':d})
    if kind=='market':
     item.update(all_a_close=number(pick(r,'收盘价') or ''),turnover=number(pick(r,'成交金额') or ''),turnover_rate=number(pick(r,'换手率') or ''))
    else:item['hs300_close' if code=='000300.SH' else 'zz1000_close']=number(pick(r,'收盘价') or '')
 financefile=ROOT/'sources/ifind_financing_daily.csv'
 finance={r['date']:r for r in csv.DictReader(financefile.open(encoding='utf-8'))}
 for d,r in candidate.items():
  if d in finance:r['financing_balance']=float((Decimal(finance[d]['balance_sh_100m_yuan'])+Decimal(finance[d]['balance_sz_100m_yuan']))*10**8)
 oldmap={r['date']:r for r in rows};overlap=[]
 for d in sorted(candidate.keys()&oldmap.keys()):
  for field in FIELDS[1:]:
   a=oldmap[d][field];b=candidate[d].get(field)
   if a is not None and b is not None:overlap.append({'date':d,'field':field,'original':a,'ifind':b,'difference':b-a})
 expected=sorted(d for d in calendar if '2026-08-04'<d<='2026-10-20')
 missing=[{'date':d,'missing_fields':[k for k in FIELDS[1:] if candidate.get(d,{}).get(k) is None]} for d in expected if any(candidate.get(d,{}).get(k) is None for k in FIELDS[1:])]
 if missing:save(ROOT/'outputs/data_gaps.json',missing);raise ValueError('Missing candidate rows; see data_gaps.json')
 rows.extend({k:candidate[d][k] for k in FIELDS} for d in expected)
 assert len({r['date'] for r in rows})==len(rows)
 save(ROOT/'raw_history.json',rows)
 with (ROOT/'outputs/raw_history.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(rows)
 with (ROOT/'outputs/source_overlap.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(overlap[0]));w.writeheader();w.writerows(overlap)
 stats={field:{'rows':len(a:=[x for x in overlap if x['field']==field]),'max_abs_difference':max(abs(x['difference']) for x in a)} for field in FIELDS[1:]}
 audit={'original_rows':len(old),'appended_candidate_rows':len(expected),'last_date':rows[-1]['date'],'source_boundary':'2026-08-04','candidate_amount_display_rounded':True,'old_turnover_definition_equal_to_new_not_certified':True,'old_financing_market_scope_not_certified':True,'historical_publication_certified':False,'calendar_source':'Pinned V101 observed index session sequence; not independently exchange-certified','overlap':stats,'excluded_provider_non_session_rows':len(excluded),'model_clock':'AFTER_CLOSE: uses same-day close; NOT D-day preopen','production_updated':False}
 save(ROOT/'outputs/data_audit.json',audit);save(ROOT/'outputs/excluded_provider_rows.json',excluded)
 manifest=[{'path':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted((ROOT/'sources').rglob('*')) if p.is_file()]
 save(ROOT/'outputs/input_manifest.json',manifest)
 print(json.dumps(audit,ensure_ascii=False))
if __name__=='__main__':main()
