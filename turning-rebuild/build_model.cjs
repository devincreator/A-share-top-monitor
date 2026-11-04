const fs=require('fs'),path=require('path');
const root=__dirname;process.chdir(root);
const model=require('./model_core.cjs');
const read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const write=(p,v)=>fs.writeFileSync(p,JSON.stringify(v,null,2));
const all=read('raw_history.json'),reference=read('reference.json');
const legacy=all.filter(r=>r.date<='2026-08-04');
const legacyIndicators=model.buildIndicators(legacy),legacySignals=model.buildSignals(legacyIndicators);
const historical=model.verifyHistorical(legacySignals,reference);
if(!historical.pass)throw Error('Original historical signal replay failed');
const financePath='sources/ifind_financing_daily.csv';
const finance=new Map(fs.readFileSync(financePath,'utf8').trim().split(/\r?\n/).slice(1).map(l=>{const a=l.split(',');return [a[0],(Number(a[1])+Number(a[2]))*1e8]}));
// Never stitch old and new financing balances inside a 63/756-session window.
const candidate=all.map(r=>({...r,financing_balance:finance.get(r.date)??null}));
write('outputs/candidate_raw_history.json',candidate);
const ind=model.buildIndicators(candidate),sig=model.buildSignals(ind);
const freeze=model.inferFreezePosition(legacyIndicators,reference);
const execution=model.calculateExecution(ind,sig,freeze);
function pivots(rows,threshold){
 let state='UNKNOWN',hi=null,lo=null,result=[];
 for(let i=0;i<rows.length;i++){
  const x={date:rows[i].date,price:rows[i].all_a_close,index:i};
  if(state==='UNKNOWN'){
   if(!hi||x.price>=hi.price)hi=x;if(!lo||x.price<=lo.price)lo=x;
   if(x.price<=hi.price*(1-threshold)){state='DOWN';result.push({...hi,direction:'TOP',confirmed_at:x.date});lo=x;}
   else if(x.price>=lo.price*(1+threshold)){state='UP';result.push({...lo,direction:'BOTTOM',confirmed_at:x.date});hi=x;}
  }else if(state==='UP'){
   if(x.price>=hi.price)hi=x;
   if(x.price<=hi.price*(1-threshold)){result.push({...hi,direction:'TOP',confirmed_at:x.date});state='DOWN';lo=x;}
  }else{
   if(x.price<=lo.price)lo=x;
   if(x.price>=lo.price*(1+threshold)){result.push({...lo,direction:'BOTTOM',confirmed_at:x.date});state='UP';hi=x;}
  }
 }
 return result.filter(x=>x.date>='2015-01-05');
}
const objective={};for(const [scale,th] of [[5,.05],[9,.09]])for(const side of ['TOP','BOTTOM'])objective[(side==='TOP'?'top':'bottom')+scale]=pivots(all,th).filter(x=>x.direction===side);
const objectiveAudit={};for(const [k,dates] of Object.entries(reference.objective)){
 const got=objective[k].filter(x=>x.confirmed_at<=reference.meta.end).map(x=>x.date),want=new Set(dates);
 objectiveAudit[k]={target:dates.length,calculated:got.length,missing:dates.filter(d=>!got.includes(d)),extra:got.filter(d=>!want.has(d))};
}
// Orthogonal temporal check: changing later raw observations cannot alter earlier emissions.
const cut=all.findIndex(r=>r.date==='2026-08-04');
const altered=candidate.map((r,i)=>i>cut?{...r,all_a_close:r.all_a_close*1.3,turnover:r.turnover*2}:r);
const alteredSig=model.buildSignals(model.buildIndicators(altered));
const temporal=Object.keys(reference.strategies).every(k=>sig.date.every((d,i)=>d>'2026-08-04'||sig[k+'Formal'][i]===alteredSig[k+'Formal'][i]));
if(!temporal)throw Error('Future perturbation changed past signals');
const timeline=sig.date.map((date,i)=>{
 const j=ind.date.indexOf(date),r={date,...candidate[j],phase5:sig.phase5[i],phase9:sig.phase9[i],source_status:date<='2026-08-04'?'ARCHIVED_RAW_WITH_NEW_FINANCING_RESEARCH':'NEW_SOURCE_RESEARCH_ONLY'};
 for(const key of ['ret5','up20','up60','up120','dd20','dd60','distance20High','rvP252','rvP756','ret63P756','turnoverAmtP252','turnoverRateP252','styleDd20','finance63GrowthP756','rv60P756'])r[key]=ind[key][j];
 for(const k of Object.keys(reference.strategies)){r[k+'_event']=sig[k+'Formal'][i];r[k+'_route']=sig[k+'Route'][i];}
 return r;
});
const events=[];for(const k of Object.keys(reference.strategies))for(let i=0;i<sig.date.length;i++)if(sig[k+'Formal'][i])events.push({module:k,date:sig.date[i],route:sig[k+'Route'][i],status:'RESEARCH_REPLAY_NOT_ORIGINAL_NOTIFICATION'});
events.sort((a,b)=>a.date.localeCompare(b.date));
const audit={historical_signal_replay:historical,frozen_nav_inference:freeze,objective_dates_replay:objectiveAudit,future_perturbation_does_not_change_past_signals:temporal,score_mapping_recovered:false,score_mapping_note:'V30 score curves retained only as original archive; not generated from reconstructed factors',new_financing_spliced_with_old:false,historical_publication_certified:false,production_updated:false,decision_clock:'AFTER_CLOSE_REPLAY_NOT_PREOPEN',asof:all.at(-1).date};
write('outputs/reconstruction_audit.json',audit);write('outputs/legacy_signals.json',legacySignals);write('outputs/candidate_indicators.json',ind);write('outputs/candidate_signals.json',sig);write('outputs/recomputed_pivots.json',objective);write('outputs/candidate_execution.json',execution);
function csv(name,rows){const keys=Object.keys(rows[0]);fs.writeFileSync(name,'\ufeff'+keys.join(',')+'\n'+rows.map(r=>keys.map(k=>r[k]===null||r[k]===undefined?'':JSON.stringify(r[k])).join(',')).join('\n')+'\n');}
csv('outputs/recomputed_daily.csv',timeline);csv('outputs/candidate_events.csv',events);
const bundle={audit,dataAudit:read('outputs/data_audit.json'),daily:timeline,events:events.filter(e=>e.date>'2026-08-04'),objective,execution:execution.daily,originalRules:Object.fromEntries(Object.entries(reference.strategies).map(([k,s])=>[k,s.rules])),originalMetrics:Object.fromEntries(Object.entries(reference.strategies).map(([k,s])=>[k,s.metrics]))};
write('outputs/dashboard_data.json',bundle);
console.log(JSON.stringify({history:historical,objectiveAudit,temporal,new_rows:all.length-legacy.length,candidate_events:bundle.events,freeze}));
