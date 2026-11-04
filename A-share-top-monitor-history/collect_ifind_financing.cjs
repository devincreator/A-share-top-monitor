const fs=require('fs');
const path=require('path');
const crypto=require('crypto');
const {call}=require('C:/Users/devin/.agents/skills/ifind-finance-data/call-node.js');
const root=__dirname, out=path.join(root,'ifind_financing');
fs.mkdirSync(out,{recursive:true});
async function main(){
 const all=new Map(), batches=[];
 for(let y=2022;y<=2026;y++)for(let q=1;q<=4;q++){
  let start=`${y}-${String(q*3-2).padStart(2,'0')}-01`;
  let end=new Date(Date.UTC(y,q*3,0)).toISOString().slice(0,10);
  if(end<'2022-02-23'||start>'2026-10-20')continue;
  if(start<'2022-02-23')start='2022-02-23';if(end>'2026-10-20')end='2026-10-20';
  const file=path.join(out,`${start}_${end}_raw.json`);
  let raw;
  if(fs.existsSync(file))raw=JSON.parse(fs.readFileSync(file,'utf8'));
  else {raw=await call('edb','get_edb_data',{query:`${start}至${end}每个交易日的上交所:融资余额、深交所:融资余额，完整逐日表格，保留原始精度，单位亿元，注明数据来源。不要融资融券合计，不要抽样和汇总。`});fs.writeFileSync(file,JSON.stringify(raw,null,2));}
  const texts=raw.data?.result?.content?.filter(x=>x.type==='text').map(x=>x.text)||[];
  const parsed=texts.map(t=>JSON.parse(t));
  if(!raw.ok||parsed.some(x=>x.code!==1))throw Error('Provider error: '+file);
  let n=0;
  for(const obj of parsed){
   const answer=obj.data?.answer||'';
   if(/截断|部分数据/.test(answer))throw Error('Truncated batch: '+file);
   if(!/上交所.*融资余额.*亿元/.test(answer)||!/深交所.*融资余额.*亿元/.test(answer))throw Error('Unexpected table: '+file);
   const header=answer.split('\n').find(x=>x.includes('日期')&&x.includes('上交所'));
   if(header.indexOf('上交所')>header.indexOf('深交所'))throw Error('Column order changed');
   for(const m of answer.matchAll(/\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|/g)){
    const [_,d,sh,sz]=m;if(d<start||d>end||!(Number(sh)>0&&Number(sz)>0))throw Error('Invalid row');
    if(all.has(d)&&JSON.stringify(all.get(d))!==JSON.stringify([sh,sz]))throw Error('Conflict '+d);
    all.set(d,[sh,sz]);n++;
   }
  }
  if(!n)throw Error('No rows: '+file);
  batches.push({start,end,rows:n,sha256:crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')});
  console.log(start,end,n,'rows');
 }
 const csv='date,balance_sh_100m_yuan,balance_sz_100m_yuan,source,publication_time_certified\n'+[...all].sort().map(([d,v])=>`${d},${v[0]},${v[1]},iFinD_EDB_exchange_attributed,false`).join('\n')+'\n';
 fs.writeFileSync(path.join(out,'financing_daily.csv'),csv);
 const dates=fs.readFileSync(path.join(root,'research/v97_event_intake/observations/index_000985_prices_20220223_20261020.csv'),'utf8').trim().split('\n').slice(1).map(l=>l.split(',')[0]);
 const report={rows:all.size,expected_price_sessions:dates.length,missing_price_dates:dates.filter(d=>!all.has(d)),extra_dates:[...all.keys()].filter(d=>!dates.includes(d)),batches,publication_time_certified:false,exact_yuan_certified:false,production_updated:false};
 fs.writeFileSync(path.join(out,'coverage_audit.json'),JSON.stringify(report,null,2));console.log('COMPLETE',JSON.stringify({rows:all.size,missing:report.missing_price_dates.length,extra:report.extra_dates.length}));
}
main().catch(e=>{console.error(e.message);process.exitCode=1;});
