from pathlib import Path
from decimal import Decimal
import csv,json,hashlib,html
P=Path(r'E:\Codex\量化\turning-label-comparison'); R=P.parent; O=P/'charts'; O.mkdir(exist_ok=True)
dates=[r['date'] for r in csv.DictReader((R/'turning-research-canonical/tables/research_inputs.csv').open(encoding='utf-8-sig'))]
existing=list(csv.DictReader((P/'all_labels.csv').open(encoding='utf-8-sig')))
def make_labels(bars,scale,intra):
 t=Decimal(scale)/100; C=[Decimal(str(x['close'])) for x in bars]; hi=lo=(C[0],0); state=0; out=[]
 for i,b in enumerate(bars):
  high=Decimal(str(b['high'])) if intra else C[i]; low=Decimal(str(b['low'])) if intra else C[i]; c=C[i]
  if state>=0 and high>=hi[0]:hi=(high,i)
  if state<=0 and low<=lo[0]:lo=(low,i)
  if state>=0 and c<=hi[0]*(1-t):
   out.append((hi[1],i,'TOP',str(hi[0]))); state=-1;lo=(c,i)
  elif state<=0 and c>=lo[0]*(1+t):
   out.append((lo[1],i,'BOTTOM',str(lo[0])));state=1;hi=(c,i)
 return out[1:]
indices={}; rows=[]; hashes={}
for code,name in [('000985','中证全指'),('000300','沪深300'),('000852','中证1000')]:
 f=R/f'turning-research-canonical/raw/official/{code}_20110802_20260825.response.json'; hashes[code]=hashlib.sha256(f.read_bytes()).hexdigest(); raw=json.loads(f.read_text(encoding='utf-8'))['data']; lookup={r['tradeDate']:r for r in raw}; bars=[lookup[d.replace('-','')] for d in dates]
 labels=[]
 for scale in [5,9]:
  for intra in [False,True]:
   definition='intraday_extrema_close_confirm' if intra else 'close'
   seq=make_labels(bars,scale,intra)
   assert all(p<=c for p,c,s,v in seq)
   assert all(seq[j][2]!=seq[j-1][2] and seq[j][0]>=seq[j-1][1] for j in range(1,len(seq)))
   for p,c,s,v in seq:
    x={'definition':definition,'scale':scale,'direction':s,'pivot_date':dates[p],'confirmation_date':dates[c],'pivot_price':v}; labels.append(dict(x,i=p,ci=c));rows.append(dict(index_code=code,index_name=name,**x))
 if code=='000985':
  normalized=[{k:str(v) for k,v in x.items() if k not in ['i','ci']} for x in labels]
  assert sorted(normalized,key=lambda x:tuple(x.values()))==sorted(existing,key=lambda x:tuple(x.values())), 'Label regression'
 indices[code]={'name':name,'close':[float(b['close']) for b in bars],'labels':labels}
data={'dates':dates,'indices':indices}
(O/'chart_data.json').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
with (O/'three_indices_all_pivots.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
# Static full-history SVG: one image with four panels, every confirmed label represented.
def svg():
 W=1600; H=1180; left=70; right=1570; panels=[]; v=indices['000985'];lo=min(v['close']+[float(x['pivot_price']) for x in v['labels']])*.96;hi=max(v['close']+[float(x['pivot_price']) for x in v['labels']])*1.04
 out=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}"><rect width="100%" height="100%" fill="#f5f7fb"/><g font-family="Microsoft YaHei,Arial" fill="#18233b"><text x="60" y="40" font-size="26">中证全指 · 全部已确认波段顶底</text><text x="60" y="68" font-size="15">2011-08-02 至 2026-08-25　红▼顶 / 绿▲底　事后研究标签，不是当日可知的预测警报</text>']
 for panel,(scale,definition) in enumerate([(5,'close'),(5,'intraday_extrema_close_confirm'),(9,'close'),(9,'intraday_extrema_close_confirm')]):
  y0=110+panel*260; base=y0+200; x=lambda i:left+i/(len(dates)-1)*(right-left); y=lambda p:base-(p-lo)/(hi-lo)*175
  ls=[l for l in v['labels'] if l['scale']==scale and l['definition']==definition]
  title=f'{scale}% · '+('收盘价顶底' if definition=='close' else '盘中极值 / 收盘反转确认')+f'　顶 {sum(l["direction"]=="TOP" for l in ls)} / 底 {sum(l["direction"]=="BOTTOM" for l in ls)}'
  out.append(f'<rect x="40" y="{y0-22}" width="1540" height="245" rx="12" fill="white"/><text x="65" y="{y0}" font-size="18">{title}</text>')
  for q in range(4):
   val=lo+(hi-lo)*q/3; yy=y(val);out.append(f'<path d="M{left},{yy} H{right}" stroke="#e7ebf2"/><text x="12" y="{yy+4}" font-size="11">{val:.0f}</text>')
  path=' '.join(('M' if i==0 else 'L')+f'{x(i):.2f},{y(p):.2f}' for i,p in enumerate(v['close']));out.append(f'<path d="{path}" fill="none" stroke="#6c7d97" stroke-width="1.2"/>')
  for l in ls:
   xx=x(l['i']); yy=y(float(l['pivot_price'])); top=l['direction']=='TOP';dy=-7 if top else 7; color='#d33f49' if top else '#078775';points=f'{xx},{yy} {xx-4},{yy+dy} {xx+4},{yy+dy}'
   tip=f'{l["pivot_date"]} {"顶" if top else "底"} {l["pivot_price"]}；{l["confirmation_date"]}收盘确认'
   out.append(f'<polygon points="{points}" fill="{color}"><title>{tip}</title></polygon>')
  for i,d in enumerate(dates):
   if i==0 or (d[:4]!=dates[i-1][:4] and int(d[:4])%2==0):out.append(f'<text x="{x(i):.0f}" y="{base+17}" font-size="12">{d[:4]}</text>')
 out.append('<text x="60" y="1170" font-size="13">来源：中证指数官方日线；首个边界事件和末端未确认波段不标注。盘中版并非日内触价即确认。</text></g></svg>');return ''.join(out)
(O/'all_pivots_overview.svg').write_text(svg(),encoding='utf-8')
page='''<!doctype html><html lang="zh"><meta charset="utf-8"><title>波段顶底全景</title><style>body{font:15px 'Microsoft YaHei',Arial;background:#f4f7fb;color:#17263d;margin:24px}h1{font-size:26px;margin-bottom:8px}.note{line-height:1.8;color:#52627a}.controls{display:flex;flex-wrap:wrap;gap:14px;margin:18px 0;background:white;padding:16px;border-radius:12px}select,input,button{font:inherit;padding:6px;border:1px solid #ccd4df;border-radius:5px}svg{background:white;border-radius:12px;width:100%;margin-top:12px}table{width:100%;border-collapse:collapse;background:white;margin-top:15px}th,td{text-align:left;padding:9px;border-bottom:1px solid #edf0f5}summary{cursor:pointer}#tip{position:fixed;display:none;background:#17263d;color:white;padding:10px;border-radius:6px;pointer-events:none;white-space:pre;z-index:9}</style>
<h1>波段顶底全景</h1><div class="note">红▼顶　绿▲底。每个标记都是事后确认的研究标签；鼠标指向标记可查看拐点日与确认日。<br>全部历史：2011-08-02 至 2026-08-25，共3659个交易日。盘中版取最高/最低价，收盘反转5%或9%才确认。首个边界事件与末端未确认波段不标。<br>中证1000在2014-10-17发布；更早的指数历史属于回溯区间，不能当作当时已发布。切换指数只比较标签，尚未比较三指数预测准确率。</div>
<div class="controls"><label>指数 <select id="idx"><option value="000985">中证全指 · 主标准</option><option value="000300">沪深300 · 大盘</option><option value="000852">中证1000 · 小盘</option></select></label><label>标注 <select id="def"><option value="intraday_extrema_close_confirm">盘中极值 / 收盘确认</option><option value="close">收盘价</option><option value="both">两种同时对照</option></select></label><label>开始 <input type="date" id="from" value="2011-08-02"></label><label>结束 <input type="date" id="to" value="2026-08-25"></label><button id="all">全部</button><button id="recent">近3年</button></div><div id="counts"></div><div id="plots"></div><details><summary>展开当前范围全部顶底明细</summary><table><thead><tr><th>幅度</th><th>口径</th><th>顶/底</th><th>拐点日</th><th>点位</th><th>确认日</th></tr></thead><tbody id="rows"></tbody></table></details><p class="note">价格来源：中证指数官方日线。离线自包含，无网络依赖。两种定义平行保留，不按回测分数挑选真值。 2026-11-02复核：混合盘中版不保证相邻反向拐点之间的实际最高/最低，5%有14处、9%有6处不一致；收盘版暂作研究基准，盘中版仅作实验对照。详见 label_clock_v4 标签审计。</p><div id="tip"></div><script>const DATA=__DATA__;
const $=s=>document.getElementById(s);function draw(){let v=DATA.indices[$('idx').value],a=DATA.dates.findIndex(d=>d>=$('from').value),b=DATA.dates.findLastIndex(d=>d<=$('to').value),def=$('def').value;if(a<0||b<a){$('plots').textContent='日期范围没有数据';$('rows').innerHTML='';$('counts').textContent='';return}let ls=v.labels.filter(l=>l.i>=a&&l.i<=b&&(def==='both'||def===l.definition));$('counts').textContent=v.name+'：当前范围 '+ls.filter(l=>l.direction==='TOP').length+' 个顶 / '+ls.filter(l=>l.direction==='BOTTOM').length+' 个底（两种口径同时显示时分别计数）';$('plots').innerHTML=[5,9].map(scale=>{let labels=ls.filter(l=>l.scale===scale),ps=v.close.slice(a,b+1).concat(labels.map(l=>+l.pivot_price)),lo=Math.min(...ps)*.98,hi=Math.max(...ps)*1.02,x=i=>65+(i-a)/Math.max(1,b-a)*1450,y=p=>330-(p-lo)/(hi-lo)*265;let s='<svg viewBox="0 0 1550 375" role="img" aria-label="'+v.name+scale+'%顶底"><text x="65" y="30" font-size="20">'+v.name+' · '+scale+'%波段</text>';for(let j=0;j<5;j++){let p=lo+(hi-lo)*j/4,yy=y(p);s+='<path d="M65 '+yy+' H1515" stroke="#e6ebf1"/><text x="8" y="'+(yy+4)+'" font-size="12">'+p.toFixed(0)+'</text>'}s+='<path d="'+v.close.slice(a,b+1).map((p,j)=>(j?'L':'M')+x(j+a).toFixed(2)+','+y(p).toFixed(2)).join(' ')+'" fill="none" stroke="#718199" stroke-width="1.4"/>';labels.forEach(l=>{let xx=x(l.i),yy=y(+l.pivot_price),top=l.direction==='TOP',dy=top?-10:10,c=top?'#d33f49':'#078775',solid=l.definition!=='close';s+='<polygon tabindex="0" data-tip="'+[l.pivot_date,scale+'% '+(top?'顶':'底')+' '+l.pivot_price,solid?'盘中极值 / 收盘确认':'收盘价',l.confirmation_date+' 收盘确认'].join('&#10;')+'" points="'+xx+','+yy+' '+(xx-6)+','+(yy+dy)+' '+(xx+6)+','+(yy+dy)+'" fill="'+(solid?c:'white')+'" stroke="'+c+'" stroke-width="1.5"/>'});for(let j=0;j<=6;j++){let i=Math.round(a+(b-a)*j/6);s+='<text x="'+(x(i)-30)+'" y="355" font-size="12">'+DATA.dates[i]+'</text>'}return s+'</svg>'}).join('');$('rows').innerHTML=ls.slice().sort((a,b)=>a.i-b.i||a.scale-b.scale).map(l=>'<tr><td>'+l.scale+'%</td><td>'+(l.definition==='close'?'收盘':'盘中极值')+'</td><td>'+(l.direction==='TOP'?'顶':'底')+'</td><td>'+l.pivot_date+'</td><td>'+l.pivot_price+'</td><td>'+l.confirmation_date+'</td></tr>').join('');document.querySelectorAll('[data-tip]').forEach(el=>{el.onmousemove=e=>{let t=$('tip');t.textContent=el.dataset.tip;t.style.display='block';t.style.left=Math.min(e.clientX+15,innerWidth-260)+'px';t.style.top=Math.max(0,e.clientY-95)+'px'};el.onmouseleave=()=>{$('tip').style.display='none'}})}['idx','def','from','to'].forEach(id=>$(id).onchange=draw);$('all').onclick=()=>{$('from').value=DATA.dates[0];$('to').value=DATA.dates.at(-1);draw()};$('recent').onclick=()=>{$('from').value='2023-08-25';$('to').value=DATA.dates.at(-1);draw()};draw();</script></html>'''
(O/'all_pivots.html').write_text(page.replace('__DATA__',json.dumps(data,ensure_ascii=False,separators=(',',':'))),encoding='utf-8')
validation={'000985_labels_exactly_match_previous_comparison':True,'all_three_indices_alternation_and_date_order_pass':True,'dates':len(dates),'range':[dates[0],dates[-1]],'total_labels':len(rows),'by_index':{k:{f'{s}_{d}':sum(l['scale']==s and l['definition']==d for l in v['labels']) for s in [5,9] for d in ['close','intraday_extrema_close_confirm']} for k,v in indices.items()},'source_sha256':hashes,'production_modified':False}
(O/'validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(validation,ensure_ascii=False,indent=2))
