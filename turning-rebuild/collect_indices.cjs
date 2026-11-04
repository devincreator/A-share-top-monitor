const fs=require('fs'),path=require('path');
const {call}=require('C:/Users/devin/.agents/skills/ifind-finance-data/call-node.js');
async function main(){
for(const month of ['07','08','09','10']){
 const end=month==='10'?'20':month==='09'?'30':'31';
 for(const kind of ['market','style']){
  const file=path.join(__dirname,'sources',`ifind_${kind}_2026${month}.json`);
  if(fs.existsSync(file))continue;
  const query=kind==='market'?`中证全指000985.CSI，2026-${month}-01至2026-${month}-${end}每个交易日的收盘价（不复权）、成交金额（元）、换手率（%）。完整逐日表，不抽样。成交金额请用完整数字，不使用万亿等缩写，至少保留原始精度。仅交易日。`:`沪深300000300.SH、中证1000000852.SH，2026-${month}-01至2026-${month}-${end}每个交易日收盘价（不复权）。按证券代码、日期、收盘价输出完整表，不抽样，仅交易日。`;
  const raw=await call('index','index_data',{query});fs.writeFileSync(file,JSON.stringify(raw,null,2));
  console.log(path.basename(file),JSON.stringify(raw).length);
 }
}
}
main().catch(e=>{console.error(e.message);process.exitCode=1});
