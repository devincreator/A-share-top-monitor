from pathlib import Path
import json,csv,re,sys,decimal
from decimal import Decimal
P=Path(__file__).resolve().parent
sys.path.insert(0,str(P.parent/'turning-raw-reacquired'))
from assemble import numeric,decode_answer,table,get

def load_inputs():
 official={}
 for r in json.loads((P/'raw/official/000985_20110802_20260825.response.json').read_text(encoding='utf-8'))['data']:
  s=r['tradeDate'];d=f'{s[:4]}-{s[4:6]}-{s[6:]}'
  if d!='2018-06-18':official[d]=r
 observed={};conflicts=[];rejected=[]
 for f in sorted((P/'raw/turnover/float_a_history').glob('*.json')):
  obj=json.loads(f.read_text(encoding='utf-8-sig'))
  if not isinstance(obj,dict) or 'raw' not in obj:continue
  answers=decode_answer(obj['raw']);found=0
  for answer in answers:
   for r in table(answer):
    if r.get('证券代码')!='000985.CSI':continue
    ds=get(r,['日期']);s=ds.replace('-','');d=f'{s[:4]}-{s[4:6]}-{s[6:]}'
    if not obj['a']<=d<=obj['b']:rejected.append({'file':f.name,'reason':'OUTSIDE_REQUEST','date':d});continue
    if d not in official:continue
    display=get(r,['流通A股']);shares=numeric(display);vol_display=get(r,['成交量']);vol=numeric(vol_display)
    if shares is None or shares<=0 or vol is None or vol<=0:continue
    text=re.sub('[,]','',vol_display)
    scale=Decimal(10**12) if '万亿' in text else Decimal(10**8) if '亿' in text else Decimal(10**4) if '万' in text else Decimal(1)
    base=Decimal(text.replace('万亿','').replace('亿','').replace('万',''))
    quantum=scale*Decimal(10)**base.as_tuple().exponent
    officialvol=Decimal(str(official[d]['tradingVol']))
    if abs(officialvol-vol)>quantum/2:
     rejected.append({'file':f.name,'reason':'VOLUME_NOT_MATCH_OFFICIAL_AT_DISPLAY_PRECISION','date':d,'official_volume':str(officialvol),'provider_volume':str(vol),'quantum':str(quantum)})
     # One explicitly reviewed discrepancy: official repeated raw volume takes priority,
     # but the denominator remains a provider field, with a disclosed scope assumption.
     if d!='2012-12-07':continue
     policy=json.loads((P/'raw/turnover/volume_exception_policy.json').read_text(encoding='utf-8'))
     assert officialvol==Decimal(str(policy['official_volume_shares'])) and vol==Decimal(str(policy['ifind_volume_shares_displayed']))
    entry={'date':d,'float_a_shares':str(shares),'float_a_display':display,'provider_volume':str(vol),'provider_volume_display':vol_display,'official_volume_shares':str(officialvol),'source_file':str(f.relative_to(P)),'volume_cross_check_status':'MATCH_AT_DISPLAY_PRECISION' if abs(officialvol-vol)<=quantum/2 else 'DISCLOSED_DISAGREEMENT_OFFICIAL_SELECTED'}
    if d in observed and observed[d]['float_a_shares']!=str(shares):conflicts.append({'date':d,'first':observed[d],'later':entry})
    else:observed[d]=entry
    found+=1
  if not found:rejected.append({'file':f.name,'reason':'NO_ACCEPTED_ROWS'})
 return official,observed,conflicts,rejected
if __name__=='__main__':
 official,obs,conflicts,rejected=load_inputs();missing=sorted(set(official)-set(obs));obj={'official_dates':len(official),'accepted':len(obs),'missing':missing,'conflicts':conflicts,'rejected':rejected}
 (P/'float_a_coverage.json').write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'official_dates':len(official),'accepted':len(obs),'missing':len(missing),'conflicts':len(conflicts),'rejected':len(rejected)},ensure_ascii=False))
