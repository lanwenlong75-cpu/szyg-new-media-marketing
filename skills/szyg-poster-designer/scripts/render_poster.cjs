const fs=require('fs'),path=require('path'),{pathToFileURL}=require('url');
const flags={};for(let i=2;i<process.argv.length;i+=2)flags[process.argv[i].replace(/^--/,'')]=process.argv[i+1];
const skill=path.resolve(__dirname,'..');const cfg=JSON.parse(fs.readFileSync(path.join(skill,'references/runtime-config.json'),'utf8'));
const input=path.resolve(flags.input||'');const out=path.resolve(flags.out||path.dirname(input));fs.mkdirSync(out,{recursive:true});
const {chromium}=require(flags.playwright||cfg.playwright);
(async()=>{
  if(!fs.existsSync(input))throw new Error('HTML不存在');
  const browser=await chromium.launch({headless:true,executablePath:flags.browser||cfg.browser});
  const page=await browser.newPage({viewport:{width:1280,height:2000},deviceScaleFactor:Number(flags.scale||1)});
  const issues=[];page.on('pageerror',e=>issues.push({kind:'pageerror',text:e.message}));
  await page.goto(pathToFileURL(input).href);await page.evaluate(()=>document.fonts.ready);
  await page.locator('img').evaluateAll(imgs=>Promise.all(imgs.map(im=>im.decode().catch(()=>null))));
  const check=await page.evaluate(()=>{
    const root=document.querySelector('#poster'),bounds=root.getBoundingClientRect();const errors=[];
    for(const e of root.querySelectorAll('[data-check-box]')){
      const b=e.getBoundingClientRect();if(!b.width||!b.height)continue;
      if(e.scrollWidth>e.clientWidth+2||e.scrollHeight>e.clientHeight+2)errors.push({kind:'textOverflow',text:e.textContent});
      if(b.left<bounds.left-1||b.right>bounds.right+1||b.top<bounds.top-1||b.bottom>bounds.bottom+1)errors.push({kind:'outsideCanvas',text:e.textContent});
    }
    const texts=Array.from(root.querySelectorAll('[data-copy]')).filter(e=>e.getBoundingClientRect().width).map(e=>{const r=document.createRange();r.selectNodeContents(e);return{e,text:e.textContent,rects:Array.from(r.getClientRects()).filter(b=>b.width>2&&b.height>2)}});
    for(let i=0;i<texts.length;i++)for(let j=i+1;j<texts.length;j++){
      const a=texts[i],b=texts[j];if(a.e.contains(b.e)||b.e.contains(a.e))continue;
      if(a.rects.some(x=>b.rects.some(y=>Math.min(x.right,y.right)-Math.max(x.left,y.left)>3&&Math.min(x.bottom,y.bottom)-Math.max(x.top,y.top)>3)))errors.push({kind:'textOverlap',text:a.text,with:b.text});
    }
    for(const im of root.querySelectorAll('img'))if(!im.naturalWidth)errors.push({kind:'imageFailed',source:im.getAttribute('src')});
    const fonts=Array.from(document.fonts).map(f=>({family:f.family,loaded:f.status==='loaded'}));
    for(const f of fonts)if(!f.loaded)errors.push({kind:'fontFailed',family:f.family});
    return {width:bounds.width,height:bounds.height,textBlocks:root.querySelectorAll('[data-check-box]').length,fonts,errors};
  });issues.push(...check.errors);
  const toolbar=page.locator('.toolbar');await toolbar.evaluate(e=>e.style.visibility='hidden');
  const output=path.join(out,'poster.png');await page.locator('#poster').screenshot({path:output});
  await toolbar.evaluate(e=>e.style.visibility='');
  await page.locator('#edit').click();const editability=await page.locator('[data-copy]').first().evaluate(e=>e.isContentEditable);await page.locator('#edit').click();
  if(!editability)issues.push({kind:'editingUnavailable'});
  const mobileHeight=Math.round(check.height*390/check.width);
  const mobile=await browser.newPage({viewport:{width:390,height:mobileHeight},deviceScaleFactor:1});
  await mobile.goto(pathToFileURL(output).href);await mobile.addStyleTag({content:`body{margin:0;background:white}img{display:block;width:390px;height:${mobileHeight}px;margin:0;max-width:none}`});await mobile.locator('img').evaluate(im=>im.decode());await mobile.screenshot({path:path.join(out,'mobile-preview.png')});
  await browser.close();const report={...check,errors:issues,editability,mobilePreviewWidth:390,renderer:'Playwright + local Chromium',visualAcceptance:'not_assessed_by_script',passed:issues.length===0};
  fs.writeFileSync(path.join(out,'render-check.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));if(issues.length)process.exitCode=1;
})().catch(e=>{console.error(e.message);process.exitCode=1});
