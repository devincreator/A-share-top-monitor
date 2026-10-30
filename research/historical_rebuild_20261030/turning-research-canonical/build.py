from pathlib import Path
import csv,json,hashlib,math
from decimal import Decimal
P=Path(r'E:\Codex\量化\turning-research-canonical'); S=P.parent/'turning-raw-reacquired'
(P/'tables').mkdir(exist_ok=True)
def write(name,rows,fields=None):
    with (P/'tables'/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields or list(rows[0]));w.writeheader();w.writerows(rows)
def js(name,obj): (P/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
fresh=list(csv.DictReader((S/'tables/raw_six_fields.csv').open(encoding='utf-8-sig'))); dates={r['date'] for r in fresh}
indices={}; quarantined=[]; lineage=[]
for code in ['000985','000300','000852']:
    path=P/f'raw/official/{code}_20110802_20260825.response.json'
    result=json.loads(path.read_text(encoding='utf-8')); assert str(result['code'])=='200'
    rows={}
    for r in result['data']:
        d=r['tradeDate'];d=f'{d[:4]}-{d[4:6]}-{d[6:]}'
        assert r['indexCode']==code and d not in rows
        if d=='2018-06-18':
            assert r['open'] is None and r['tradingValue']==0
            quarantined.append(dict(date=d,index_code=code,reason='SSE announced holiday; null OHLC and zero volume',evidence_url='https://www.sse.com.cn/disclosure/announcement/general/c/c_20180606_4567900.shtml'));continue
        assert r['close']>0 and r['tradingValue']>0
        rows[d]=r
    assert set(rows)==dates
    indices[code]=rows
out=[];diff=[];candidates=[]
for r in fresh:
    d=r['date']; values=dict(date=d,all_a_close=indices['000985'][d]['close'],hs300_close=indices['000300'][d]['close'],zz1000_close=indices['000852'][d]['close'],turnover=str(Decimal(str(indices['000985'][d]['tradingValue']))*Decimal(100000000)),turnover_rate='',financing_balance=r['financing_balance'])
    out.append(values)
    candidates.append(dict(date=d,ifind_turnover_rate_pct=r['turnover_rate'],status='QUARANTINED_DEFINITION_UNVERIFIED'))
    for field in ['all_a_close','hs300_close','zz1000_close','turnover']:
        code={'hs300_close':'000300','zz1000_close':'000852'}.get(field,'000985')
        lineage.append(dict(date=d,field=field,source=f'raw/official/{code}_20110802_20260825.response.json',transform='tradingValue (100m CNY) * 100000000' if field=='turnover' else 'close',status='OFFICIAL_HISTORY_NOT_PIT'))
        old=Decimal(r[field]);new=Decimal(str(values[field]));delta=new-old
        if delta: diff.append(dict(date=d,field=field,prior_ifind_value=str(old),official_value=str(new),difference=str(delta)))
    lineage.append(dict(date=d,field='financing_balance',source='../turning-raw-reacquired/tables/field_lineage.csv',transform='retain independently reacquired SH+SZ financing balance CNY',status='PROVIDER_HISTORY_NOT_PIT'))
write('research_inputs.csv',out);write('turnover_rate_candidates.csv',candidates);write('official_vs_ifind.csv',diff);write('quarantined_official_rows.csv',quarantined);write('field_lineage.csv',lineage)
probe=[]
for d,volume,rate,cap,free,total in [('2025-10-09',1476.2977,2.127,96.2114,3.2609,7.8887),('2025-10-10',1456.1632,2.0976,95.0237,3.2627,7.8889),('2025-10-13',1409.9945,2.0312,94.6279,3.2605,7.8866)]:
    probe.append(dict(date=d,ifind_rate_pct=rate,volume_div_total_float_pct=volume*1e8/(total*1e12)*100,volume_div_free_float_pct=volume*1e8/(free*1e12)*100,official_amount_div_float_cap_pct=float(Decimal(str(indices['000985'][d]['tradingValue']))*Decimal(1e8))/(cap*1e12)*100,status='NO_MATCH_DENOMINATOR_ASOF_AND_SCOPE_UNCERTIFIED'))
write('turnover_formula_probe.csv',probe)
js('source_policy.json',dict(accepted_fields={'all_a_close':'CSI official 000985 close','hs300_close':'CSI official 000300 close','zz1000_close':'CSI official 000852 close','turnover':'CSI official 000985 tradingValue, 100m CNY converted to CNY','financing_balance':'New independently reacquired iFinD SH+SZ financing balance, CNY'},turnover_rate='quarantined until exact formula, constituent scope and historical denominator are verified',tradingValue_precision='Official display precision 0.01 hundred million CNY; conversion does not add precision',pit_certified=False,full_model_ready=False))
js('validation.json',dict(rows=len(out),start=out[0]['date'],end=out[-1]['date'],unique_dates=len(dates),accepted_fields=5,turnover_rate_blank=sum(r['turnover_rate']=='' for r in out),official_rows_quarantined=len(quarantined),date_sets_equal_after_quarantine=True,missing_accepted_values=0,full_model_ready=False,reason='Original model coerces null into zero; do not run full model on this file before resolving turnover definition'))
manifest=[]
for f in sorted((P/'raw').rglob('*')):
    if f.is_file(): manifest.append(dict(file=str(f.relative_to(P)),sha256=hashlib.sha256(f.read_bytes()).hexdigest(),bytes=f.stat().st_size))
for name in ['raw_six_fields.csv','field_lineage.csv']:
    f=S/'tables'/name;manifest.append(dict(file=str(f),sha256=hashlib.sha256(f.read_bytes()).hexdigest(),bytes=f.stat().st_size))
js('input_manifest.json',manifest)
print(json.dumps({'rows':len(out),'quarantined':len(quarantined),'official_vs_ifind_different_cells':len(diff),'probe':probe},ensure_ascii=False,indent=2))
