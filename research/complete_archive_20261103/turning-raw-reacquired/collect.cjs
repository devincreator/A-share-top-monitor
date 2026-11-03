const fs=require('fs'),path=require('path'),crypto=require('crypto');
const {call}=require('C:/Users/devin/.agents/skills/ifind-finance-data/call-node.js');
const root=__dirname,start='2011-08-02',end='2026-08-25';
const jobs=[];
function bound(a,b){return [a<start?start:a,b>end?end:b]}
for(let y=2011;y<=2026;y++)for(let q=1;q<=4;q++){
 let a=`${y}-${String(q*3-2).padStart(2,'0')}-01`,b=new Date(Date.UTC(y,q*3,0)).toISOString().slice(0,10);if(b<start||a>end)continue;[a,b]=bound(a,b);
 jobs.push({kind:'market',a,b,server:'index',tool:'index_data',query:`中证全指000985.CSI，从${a}到${b}，仅这段日期，每个交易日收盘价（不复权）、成交金额（单位元）、换手率（单位%）。返回完整逐日表格，不抽样。金额用完整数字，若显示缩写保留实际精度。`});
 // Existing 2022+ independent provider receipts will be reused, never legacy CSV values.
 if(a<'2022-02-23')jobs.push({kind:'finance',a,b:b<'2022-02-23'?b:'2022-02-22',server:'edb',tool:'get_edb_data',query:`从${a}到${b<'2022-02-23'?b:'2022-02-22'}，上交所:融资余额、深交所:融资余额，每个交易日完整序列。单位亿元，注明来源，不要融资融券余额，不要抽样或汇总。`});
}
for(let y=2011;y<=2026;y++)for(let m=1;m<=12;m++){
 let a=`${y}-${String(m).padStart(2,'0')}-01`,b=new Date(Date.UTC(y,m,0)).toISOString().slice(0,10);if(b<start||a>end)continue;[a,b]=bound(a,b);
 jobs.push({kind:'style',a,b,server:'index',tool:'index_data',query:`沪深300（仅000300.SH，排除399300.SZ）和中证1000（000852.SH），从${a}到${b}每个交易日收盘价，不复权。按证券代码、日期、收盘价输出全部数据，不抽样，不返回其他证券。若某指数当时尚无数据，明确留空。`});
}
jobs.sort((x,y)=>x.a.localeCompare(y.a)||x.kind.localeCompare(y.kind));
fs.writeFileSync(path.join(root,'request_plan.json'),JSON.stringify({start,end,jobs},null,2));
const state={start,end,total:jobs.length,completed:0,failed:[],records:[],started_at:new Date().toISOString()};let next=0;
function answers(raw){if(!raw.ok||raw.data?.result?.isError)throw Error('Provider transport/tool error');return (raw.data?.result?.content||[]).filter(x=>x.type==='text').map(x=>JSON.parse(x.text));}
function save(){fs.writeFileSync(path.join(root,'progress.json'),JSON.stringify({...state,updated_at:new Date().toISOString()},null,2));}
async function worker(){while(next<jobs.length){const job=jobs[next++],name=`${job.kind}_${job.a}_${job.b}.json`,dest=path.join(root,'raw',name);try{
 let receipt;
 if(fs.existsSync(dest))receipt=JSON.parse(fs.readFileSync(dest,'utf8'));
 else {const began=new Date().toISOString();const raw=await call(job.server,job.tool,{query:job.query});receipt={query:job.query,requested_start:job.a,requested_end:job.b,requested_at:began,received_at:new Date().toISOString(),provider:'iFinD MCP',raw};fs.writeFileSync(dest,JSON.stringify(receipt,null,2));}
 const parsed=answers(receipt.raw);
 if(!parsed.length||parsed.some(x=>x.code!==1))throw Error('Provider business error');
 const text=parsed.map(x=>x.data?.answer||'').join('\n');
 if(/截断|部分数据/.test(text))throw Error('TRUNCATED');
 const dates=[...text.matchAll(/\b(20\d{2})-?(\d{2})-?(\d{2})\b/g)].map(m=>`${m[1]}-${m[2]}-${m[3]}`);
 if(dates.some(d=>d<job.a||d>job.b))throw Error('RESPONSE_DATE_OUTSIDE_REQUEST');
 const rows=text.split('\n').filter(l=>/^\|\s*(?:\d{6}\.\w+\s*\|.*\d{8}|\d{4}-\d{2}-\d{2})/.test(l)).length;
 if(!rows)throw Error('NO_TABLE_ROWS');
 const sha=crypto.createHash('sha256').update(fs.readFileSync(dest)).digest('hex');
 state.records.push({file:name,kind:job.kind,start:job.a,end:job.b,table_rows:rows,sha256:sha,status:'RECEIVED_NOT_YET_COVERAGE_OR_SCOPE_CERTIFIED'});
 state.completed++;console.log('OK',state.completed+'/'+state.total,name,rows);
 }catch(e){
 const days=(Date.parse(job.b)-Date.parse(job.a))/86400000;
 if((e.message==='TRUNCATED'||e.message==='RESPONSE_DATE_OUTSIDE_REQUEST')&&days>=7){
  const mid=new Date(Date.parse(job.a)+Math.floor(days/2)*86400000).toISOString().slice(0,10);
  const after=new Date(Date.parse(mid)+86400000).toISOString().slice(0,10);
  for(const [a,b] of [[job.a,mid],[after,job.b]])jobs.push({...job,a,b,query:job.kind==='style'?`沪深300和中证1000，${a}至${b}每日收盘价，完整表格，不抽样。` : job.query.replaceAll(job.a,a).replaceAll(job.b,b)});
  state.total=jobs.length;console.log('SPLIT',job.kind,job.a,mid,job.b);
 }else{state.failed.push({kind:job.kind,start:job.a,end:job.b,error:e.message});console.log('FAILED',job.kind,job.a,e.message);}
 }
 save();
 // Do not amplify account-level failures to the rest of the batch.
 if(state.failed.length>=3&&state.completed===0){next=jobs.length;break;}
 }}
// Bounded two concurrent requests, respecting the skill's default free-tier limit.
Promise.all([worker(),worker()]).then(()=>{state.finished_at=new Date().toISOString();save();console.log('FINISHED',JSON.stringify({complete:state.completed,failed:state.failed.length,total:state.total}));}).catch(e=>{console.error(e);process.exitCode=1});
