// Local Chromium rendering through Node's built-in WebSocket; no npm or other Skill.
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),cp=require('node:child_process');
const {pathToFileURL}=require('node:url');
const HELP='node scripts/render_poster.cjs --input poster.html --out new-output [--browser browser.exe] [--scale 1]\nRequires Node.js 22+ and an installed Edge/Chrome/Chromium. No Playwright or extra Skill is required.';
const flags={};for(let i=2;i<process.argv.length;i+=2){if(['--help','-h'].includes(process.argv[i])){console.log(HELP);process.exit(0)};if(!process.argv[i].startsWith('--')||!process.argv[i+1]){console.error(HELP);process.exit(2)}flags[process.argv[i].slice(2)]=process.argv[i+1]}
function browserPaths(){
  if(flags.browser && flags.browser!=='auto'){if(!fs.existsSync(flags.browser))throw Error('Specified browser does not exist');return [path.resolve(flags.browser)]}
  const candidates=[process.env.SZYG_BROWSER,
    path.join(process.env.PROGRAMFILES||'C:/Program Files','Google/Chrome/Application/chrome.exe'),
    path.join(process.env['PROGRAMFILES(X86)']||'C:/Program Files (x86)','Microsoft/Edge/Application/msedge.exe'),
    path.join(process.env.PROGRAMFILES||'C:/Program Files','Microsoft/Edge/Application/msedge.exe'),
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome','/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
    '/usr/bin/chromium','/usr/bin/chromium-browser','/usr/bin/google-chrome'];
  const found=[...new Set(candidates.filter(p=>p&&fs.existsSync(p)))];if(!found.length)throw Error('No local Edge/Chrome/Chromium found. Install a browser or provide --browser; no additional Skill is needed.');return found;
}
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function connect(url){
  const socket=new WebSocket(url),pending=new Map();let id=0;
  await new Promise((resolve,reject)=>{socket.addEventListener('open',resolve,{once:true});socket.addEventListener('error',()=>reject(Error('Cannot connect to local browser')),{once:true})});
  socket.addEventListener('message',event=>{const m=JSON.parse(event.data);if(!m.id||!pending.has(m.id))return;const r=pending.get(m.id);pending.delete(m.id);clearTimeout(r.timer);m.error?r.reject(Error(m.error.message)):r.resolve(m.result)});
  return {socket,send(method,params={}){return new Promise((resolve,reject)=>{const key=++id;const timer=setTimeout(()=>{pending.delete(key);reject(Error('Browser timeout: '+method))},30000);pending.set(key,{resolve,reject,timer});socket.send(JSON.stringify({id:key,method,params}))})}};
}
const checkExpression=`(()=>{
 const root=document.querySelector('#poster');if(!root)throw Error('HTML must contain #poster');const bounds=root.getBoundingClientRect(),errors=[];
 for(const e of root.querySelectorAll('[data-check-box]')){const b=e.getBoundingClientRect();if(!b.width||!b.height)continue;
 if(e.scrollWidth>e.clientWidth+2||e.scrollHeight>e.clientHeight+2)errors.push({kind:'textOverflow',text:e.textContent});
 if(b.left<bounds.left-1||b.right>bounds.right+1||b.top<bounds.top-1||b.bottom>bounds.bottom+1)errors.push({kind:'outsideCanvas',text:e.textContent})}
 const texts=Array.from(root.querySelectorAll('[data-copy]')).filter(e=>e.getBoundingClientRect().width).map(e=>{const r=document.createRange();r.selectNodeContents(e);return {e,text:e.textContent,rects:Array.from(r.getClientRects()).filter(b=>b.width>2&&b.height>2)}});
 for(let i=0;i<texts.length;i++)for(let j=i+1;j<texts.length;j++){const a=texts[i],b=texts[j];if(a.e.contains(b.e)||b.e.contains(a.e))continue;if(a.rects.some(x=>b.rects.some(y=>Math.min(x.right,y.right)-Math.max(x.left,y.left)>3&&Math.min(x.bottom,y.bottom)-Math.max(x.top,y.top)>3)))errors.push({kind:'textOverlap',text:a.text,with:b.text})}
 for(const im of root.querySelectorAll('img'))if(!im.naturalWidth)errors.push({kind:'imageFailed',source:im.getAttribute('src')});
 const fonts=Array.from(document.fonts).map(f=>({family:f.family,loaded:f.status==='loaded'}));for(const f of fonts)if(!f.loaded)errors.push({kind:'fontFailed',family:f.family});
 return {width:bounds.width,height:bounds.height,x:bounds.x+scrollX,y:bounds.y+scrollY,textBlocks:root.querySelectorAll('[data-check-box]').length,fonts,errors};})()`;
async function main(){
 if(Number(process.versions.node.split('.')[0])<22||typeof WebSocket==='undefined')throw Error('Node.js 22+ is required for the included renderer');
 if(!flags.input)throw Error(HELP);const input=path.resolve(flags.input);if(!fs.statSync(input).isFile())throw Error('HTML does not exist');
 const candidates=browserPaths(),out=path.resolve(flags.out||path.dirname(input)),scale=Number(flags.scale||1);if(!Number.isFinite(scale)||scale<.25||scale>4)throw Error('--scale must be between 0.25 and 4');
 fs.mkdirSync(out,{recursive:true});const profile=fs.mkdtempSync(path.join(os.tmpdir(),'szyg-poster-browser-'));
 let proc,client;
 try{
  const portFile=path.join(profile,'DevToolsActivePort');let ready=false,selectedBrowser;
  for(const executable of candidates){
   proc=cp.spawn(executable,['--headless','--no-first-run','--no-default-browser-check','--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'],{stdio:'ignore',windowsHide:true});
   let spawnError;proc.on('error',e=>spawnError=e);
   for(let i=0;i<100;i++){if(spawnError||proc.exitCode!==null)break;if(fs.existsSync(portFile)){ready=true;selectedBrowser=path.basename(executable);break}await sleep(100)}
   if(ready)break;if(proc.exitCode===null)proc.kill();await sleep(250);
  }
  if(!ready)throw Error('Installed browsers could not start headless rendering; check browser policy or pass --browser with a working local browser');const port=Number(fs.readFileSync(portFile,'utf8').split('\n')[0]);
  const target=await (await fetch('http://127.0.0.1:'+port+'/json/new?about:blank',{method:'PUT'})).json();client=await connect(target.webSocketDebuggerUrl);
  const send=client.send.bind(client);await send('Page.enable');await send('Runtime.enable');
  const evaluate=async expression=>{const r=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.exception?.description||r.exceptionDetails.text);return r.result.value};
  await send('Emulation.setDeviceMetricsOverride',{width:1280,height:2000,deviceScaleFactor:scale,mobile:false});await send('Page.navigate',{url:pathToFileURL(input).href});
  for(let i=0;i<200;i++){if(await evaluate("document.readyState==='complete' && !!document.querySelector('#poster')"))break;if(i===199)throw Error('Poster page did not finish loading');await sleep(100)}
  await evaluate('(async()=>{await document.fonts.ready;await Promise.all(Array.from(document.images).map(im=>im.decode().catch(()=>null)));return true})()');
  const check=await evaluate(checkExpression);const editability=await evaluate("(()=>{const b=document.querySelector('#edit'),e=document.querySelector('[data-copy]');if(!b||!e)return false;b.click();const ok=e.isContentEditable;b.click();return ok})()");
  if(!editability)check.errors.push({kind:'editingUnavailable'});
  await evaluate("(()=>{const t=document.querySelector('.toolbar');if(t)t.style.visibility='hidden';return true})()");
  const screenshot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:true,clip:{x:check.x,y:check.y,width:check.width,height:check.height,scale:1}});
  const png=path.join(out,'poster.png');fs.writeFileSync(png,Buffer.from(screenshot.data,'base64'));
  const mobileHeight=Math.round(check.height*390/check.width);await send('Emulation.setDeviceMetricsOverride',{width:390,height:mobileHeight,deviceScaleFactor:1,mobile:false});
  await send('Page.navigate',{url:pathToFileURL(png).href});
  for(let i=0;i<100;i++){if(await evaluate("document.readyState==='complete' && !!document.querySelector('img')"))break;await sleep(100)}
  await evaluate(`(async()=>{const im=document.querySelector('img');await im.decode();document.body.style.cssText='margin:0;background:white';im.style.cssText='display:block;width:390px;height:${mobileHeight}px;margin:0;max-width:none';return true})()`);
  const mobile=await send('Page.captureScreenshot',{format:'png',clip:{x:0,y:0,width:390,height:mobileHeight,scale:1}});fs.writeFileSync(path.join(out,'mobile-preview.png'),Buffer.from(mobile.data,'base64'));
  const report={...check,editability,mobilePreviewWidth:390,browser:selectedBrowser,renderer:'Node.js built-in WebSocket + local Chromium',additional_skill_required:false,visualAcceptance:'not_assessed_by_script',passed:check.errors.length===0};
  fs.writeFileSync(path.join(out,'render-check.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));if(!report.passed)process.exitCode=1;
 }finally{
  if(client){try{await client.send('Browser.close')}catch{}client.socket.close()}
  if(proc&&proc.exitCode===null)proc.kill();await sleep(250);
  const resolved=path.resolve(profile),temp=path.resolve(os.tmpdir());if(path.dirname(resolved)===temp&&path.basename(resolved).startsWith('szyg-poster-browser-')){try{fs.rmSync(resolved,{recursive:true,force:true,maxRetries:10,retryDelay:150})}catch{}}
 }
}
main().catch(e=>{console.error(e.message);process.exitCode=2});
