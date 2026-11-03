from pathlib import Path
from decimal import Decimal
import csv,json,statistics
R=Path(r'E:\Codex\量化'); P=R/'dual80-research/label_clock_v4'
rows=list(csv.DictReader((R/'turning-research-canonical/tables/research_inputs.csv').open(encoding='utf-8-sig')));D=[r['date'] for r in rows]; ix={d:i for i,d in enumerate(D)}
raw=json.loads((R/'turning-research-canonical/raw/official/000985_20110802_20260825.response.json').read_text(encoding='utf-8'))['data'];raw={r['tradeDate']:r for r in raw};bars=[raw[d.replace('-','')] for d in D]
labels=list(csv.DictReader((R/'turning-label-comparison/all_labels.csv').open(encoding='utf-8-sig')))
summary={};cases=[]
for scale in ['5','9']:
 for definition in ['close','intraday_extrema_close_confirm']:
  ll=[l for l in labels if l['scale']==scale and l['definition']==definition]; gaps=[ix[l['pivot_date']]-ix[ll[j-1]['pivot_date']] for j,l in enumerate(ll) if j];lags=[ix[l['confirmation_date']]-ix[l['pivot_date']] for l in ll]
  summary[scale+'_'+definition]={'targets':len(ll),'median_confirmation_lag':statistics.median(lags),'same_day_confirmation':lags.count(0),'median_pivot_gap':statistics.median(gaps),'pivot_gap_le_2':sum(g<=2 for g in gaps),'min_pivot_gap':min(gaps)}
 for l in [l for l in labels if l['scale']==scale and l['definition']=='close']:
  p=ix[l['pivot_date']]; near=min([g for g in labels if g['scale']==scale and g['definition']=='intraday_extrema_close_confirm' and g['direction']==l['direction']],key=lambda g:abs(ix[g['pivot_date']]-p)); q=ix[near['pivot_date']]
  cases.append({'scale':scale,'direction':l['direction'],'close_pivot':D[p],'intraday_nearest':D[q],'shift_sessions':q-p,'close_confirm':l['confirmation_date'],'intraday_confirm':near['confirmation_date'],'interpretation':'Nearest same-direction dates only; not a claim of identical wave identity','plot_start':D[max(0,min(p,q)-20)],'plot_end':D[min(len(D)-1,max(p,q)+25)]})
# Six largest date disagreements and four fixed stress episodes chosen for market structure, not alert outcomes.
selected=sorted(cases,key=lambda x:abs(x['shift_sessions']),reverse=True)[:6]
for date in ['2015-06-12','2020-07-24','2024-02-05','2024-09-13']:
 selected.append(min([c for c in cases if c['scale']=='5'],key=lambda c:abs(ix[c['close_pivot']]-ix[date])))
with (P/'label_cases.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(selected[0]));w.writeheader();w.writerows(selected)
(P/'label_structure.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
# One SVG case atlas; all four series of labels shown on actual OHLC envelope.
out=['<svg xmlns="http://www.w3.org/2000/svg" width="1500" height="2200" viewBox="0 0 1500 2200"><rect width="100%" height="100%" fill="#f4f7fb"/><g font-family="Microsoft YaHei,Arial"><text x="35" y="38" font-size="25" fill="#16273d">顶底标签差异抽查 · 最大日期差异与固定行情片段</text><text x="35" y="64" font-size="14" fill="#52647c">红▼顶 / 绿▲底；实心=盘中极值、收盘确认；空心=收盘；淡蓝范围=日内高低。最近同向日期不等于同一波段。</text>']
for k,c in enumerate(selected):
 a=ix[c['plot_start']];b=ix[c['plot_end']];oy=95+(k//2)*420;ox=35+(k%2)*735;W=700;ll=[l for l in labels if l['scale']==c['scale'] and a<=ix[l['pivot_date']]<=b];low=min(float(x['low']) for x in bars[a:b+1])*.98;high=max(float(x['high']) for x in bars[a:b+1])*1.02;x=lambda j:ox+55+(j-a)/max(1,b-a)*610;y=lambda price:oy+330-(price-low)/(high-low)*255
 out.append(f'<rect x="{ox}" y="{oy}" width="710" height="395" rx="10" fill="white"/><text x="{ox+15}" y="{oy+27}" font-size="16">{c["scale"]}% {"顶" if c["direction"]=="TOP" else "底"}：收盘 {c["close_pivot"]} / 盘中最近 {c["intraday_nearest"]}</text>')
 poly=' '.join(f'{x(j):.2f},{y(float(bars[j]["high"])):.2f}' for j in range(a,b+1))+' '+' '.join(f'{x(j):.2f},{y(float(bars[j]["low"])):.2f}' for j in reversed(range(a,b+1)));out.append(f'<polygon points="{poly}" fill="#e2ecfa"/>');path=' '.join(('M' if j==a else 'L')+f'{x(j):.2f},{y(float(bars[j]["close"])):.2f}' for j in range(a,b+1));out.append(f'<path d="{path}" fill="none" stroke="#63758e" stroke-width="1.4"/>')
 for l in ll:
  xx=x(ix[l['pivot_date']]);yy=y(float(l['pivot_price']));top=l['direction']=='TOP';color='#d33f49' if top else '#078775';dy=-9 if top else 9;fill=color if l['definition']!='close' else 'white';out.append(f'<polygon points="{xx},{yy} {xx-5},{yy+dy} {xx+5},{yy+dy}" fill="{fill}" stroke="{color}"><title>{l["pivot_date"]} {l["definition"]} {l["pivot_price"]}；{l["confirmation_date"]}确认</title></polygon>')
 for j in [a,(a+b)//2,b]:out.append(f'<text x="{x(j)-30}" y="{oy+360}" font-size="12" fill="#52647c">{D[j]}</text>')
out.append('</g></svg>');(P/'label_case_atlas.svg').write_text(''.join(out),encoding='utf-8');print(json.dumps({'structure':summary,'cases':selected},ensure_ascii=False,indent=2))
