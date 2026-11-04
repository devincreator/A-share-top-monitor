import csv, json, hashlib, sys
from pathlib import Path
from decimal import Decimal
root=Path(__file__).resolve().parent
sys.path.insert(0,str(root/'research/v90_financing'))
from isolate_window import audit_financing
with (root/'ifind_financing/financing_daily.csv').open(encoding='utf-8') as f:
    rows=list(csv.DictReader(f))
bydate={r['date']:r for r in rows}
converted=[{'date':r['date'],'balance_sh_yuan':str(Decimal(r['balance_sh_100m_yuan'])*10**8),'balance_sz_yuan':str(Decimal(r['balance_sz_100m_yuan'])*10**8)} for r in rows]
with (root/'research/v97_event_intake/observations/index_000985_prices_20220223_20261020.csv').open(encoding='utf-8') as f:
    prices=[dict(r,code='000985') for r in csv.DictReader(f)]
coverage=json.loads((root/'ifind_financing/coverage_audit.json').read_text())
if coverage['missing_price_dates'] or coverage['extra_dates']:raise ValueError('Calendar mismatch')
report=audit_financing(converted,prices,'2026-10-20')
report['source_scope']='iFinD EDB, exchange-attributed, display values converted from 100M yuan; exact-Yuan precision NOT certified'
report['source_provider_changed_from_original']=True
report['source_is_independent_of_exchange']=False
report['original_v92_ledger_unchanged']=True
report['raw_response_sha256_manifest']='coverage_audit.json'
report['csv_sha256']=hashlib.sha256((root/'ifind_financing/financing_daily.csv').read_bytes()).hexdigest()
(root/'ifind_financing/v90_window_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
comparisons=[]
for folder in sorted((root/'research/v92_margin_recovery/records').iterdir()):
    if folder.name not in bydate:continue
    r=bydate[folder.name]
    for ex,key in [('SSE','balance_sh_100m_yuan'),('SZSE','balance_sz_100m_yuan')]:
        meta=json.loads((folder/(ex+'.json')).read_text())
        a=Decimal(r[key])*10**8;b=Decimal(str(meta['balance_yuan_from_display']))
        comparisons.append({'date':folder.name,'exchange':ex,'ifind_yuan_from_display':str(a),'v92_yuan_from_display':str(b),'delta_yuan':str(a-b),'publication_time_certified':False})
with (root/'ifind_financing/v92_cross_provider_comparison.csv').open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(comparisons[0]));w.writeheader();w.writerows(comparisons)
print(json.dumps({'rows':len(rows),'v90_status':report['status'],'compared_exchange_records':len(comparisons),'display_value_conflicts':sum(Decimal(x['delta_yuan'])!=0 for x in comparisons),'formal_signal_allowed':False}))
