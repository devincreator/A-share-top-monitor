const fs=require('fs'),path=require('path'),{pathToFileURL}=require('url');
const {chromium}=require('C:/Users/devin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
const browser=await chromium.launch({headless:true,channel:'msedge'});
const page=await browser.newPage({viewport:{width:1440,height:1100}}),errors=[];
page.on('pageerror',e=>errors.push(e.message));
await page.goto(pathToFileURL(path.join(__dirname,'index.html')).href);
await page.screenshot({path:path.join(__dirname,'outputs/desktop.png'),fullPage:true});
for(const key of ['top5','top9','bottom5','bottom9','audit','summary']){await page.click(`button[data-key="${key}"]`);await page.locator('#chart').screenshot({path:path.join(__dirname,'outputs/chart-'+key+'.png')});}
for(const val of ['price','rvP756','ret63P756','turnoverAmtP252','turnoverRateP252','styleDd20','finance63GrowthP756'])await page.selectOption('#feature',val);
await page.selectOption('#window','all');await page.selectOption('#day','0');
await page.selectOption('#day',String(await page.locator('#day option').count()-1));
const downloadWait=page.waitForEvent('download');await page.click('#download');const download=await downloadWait;await download.saveAs(path.join(__dirname,'outputs/browser_export.csv'));
await page.setViewportSize({width:390,height:844});await page.selectOption('#feature','price');await page.selectOption('#window','126');await page.screenshot({path:path.join(__dirname,'outputs/mobile.png'),fullPage:true});
const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
await page.goto(pathToFileURL(path.join(__dirname,'original_v30_archive.html')).href);
const result={javascript_errors:errors,mobile_horizontal_overflow:overflow,download_success:true,module_tabs_checked:6,chart_fields_checked:7,original_archive_loaded:true};
fs.writeFileSync(path.join(__dirname,'outputs/browser_check.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));await browser.close();if(errors.length||overflow)process.exitCode=1;
})().catch(e=>{console.error(e);process.exitCode=1});
