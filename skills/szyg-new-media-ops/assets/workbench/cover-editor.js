/* The cover is a code-native layout composed from an actual video frame. */
let coverSession=null;
function coverLines(text){
  const ctx=document.createElement('canvas').getContext('2d');ctx.font='900 108px "Microsoft YaHei",sans-serif';
  const lines=[];
  text.split('\n').forEach(line=>{
    let current='';const tokens=line.trim().match(/[A-Za-z0-9]+(?:[-.][A-Za-z0-9]+)*|[^A-Za-z0-9]/gu)||[];
    for(const token of tokens){if(current&&ctx.measureText(current+token).width>990){lines.push(current.trim());current=token.trimStart()}else current+=token}
    if(current.trim())lines.push(current.trim());
  });return lines.slice(0,4);
}
async function openCoverEditor(id){
  const v=local(id);if(!v)return;
  if($('#form-dialog').open)$('#form-dialog').close();
  $('#form-content').replaceChildren();
  toast('正在读取当前视频的高清画面…');
  const data=await api('/api/cover-source',{videoId:id});
  const saved=data.cover?.profile;
  coverSession={id,media:data.media,source:data.source,profile:saved||{title:v.title.replace(/（.*?）|\(.*?\)/g,''),enabled:false,fit:v.width>=v.height?'contain':'cover',positionY:0,titleY:65}};
  if($('#form-dialog').open)$('#form-dialog').close();
  $('#form-content').innerHTML=`<div class="dialog-head"><div><div class="eyebrow">${esc(id)} · 抖音发布封面预览</div><h2>先看到发布后的样子</h2></div><button class="close" data-action="close-form" aria-label="关闭封面编辑">×</button></div><form id="cover-form" class="cover-editor"><div class="cover-preview-column"><div class="cover-design-preview"><img id="cover-image" src="${file(data.source.path)}?v=${encodeURIComponent(data.source.modifiedNs)}" alt="当前视频高清画面"><div id="cover-shade" class="cover-shade"></div><div id="cover-words" class="cover-words"></div><span class="cover-play">▷ 待发布预览</span></div><p class="small muted" style="margin-top:10px">${esc(v.title)}<br>作品页 3:4 · 发布封面 1080 × 1440</p></div><div class="cover-controls"><label for="cover-fit">画面方式</label><select id="cover-fit"><option value="cover">铺满封面（可调整上下位置）</option><option value="contain">完整保留画面（留边）</option></select><label for="cover-position">画面上下位置 <span id="cover-position-value"></span></label><input id="cover-position" type="range" min="0" max="100"><label class="cover-checkbox"><input id="cover-enabled" type="checkbox"> 叠加封面标题</label><p class="small muted">画面已有标题时可关闭叠加；新增标题采用白字与黄字、黑色描边。</p><label for="cover-title">封面标题</label><textarea id="cover-title" maxlength="80" rows="3" placeholder="每行建议6至9个字，可换行"></textarea><label for="cover-title-y">标题高度 <span id="cover-title-y-value"></span></label><input id="cover-title-y" type="range" min="30" max="85"><div class="notice" style="margin-top:17px">保存为绑定当前视频版本的新封面草稿。实际发布时由蚁小二读取这张封面，再完成发布前确认。</div><button class="button" type="submit">保存发布封面 →</button><p id="cover-feedback" class="small success-text" role="status" style="margin-top:12px"></p></div></form>`;
  $('#form-dialog').showModal();
  $('#cover-fit').value=coverSession.profile.fit;
  $('#cover-position').value=coverSession.profile.positionY;
  $('#cover-enabled').checked=coverSession.profile.enabled;
  $('#cover-title').value=coverSession.profile.title;
  $('#cover-title-y').value=coverSession.profile.titleY;
  updateCoverPreview();
}
function updateCoverPreview(){
  if(!coverSession||!$('#cover-image'))return;
  const profile={fit:$('#cover-fit').value,positionY:Number($('#cover-position').value),enabled:$('#cover-enabled').checked,title:$('#cover-title').value,titleY:Number($('#cover-title-y').value)};
  coverSession.profile=profile;
  $('#cover-image').style.objectFit=profile.fit;
  $('#cover-image').style.objectPosition=`center ${profile.positionY}%`;
  $('#cover-shade').style.background=profile.enabled?(profile.titleY<50?'linear-gradient(to bottom,rgba(0,0,0,.55),transparent 65%)':'linear-gradient(to top,rgba(0,0,0,.65),transparent 60%)'):'none';
  $('#cover-words').style.top=profile.titleY+'%';
  $('#cover-words').innerHTML=profile.enabled?coverLines(profile.title).map((text,i)=>`<span class="${i?'yellow':''}">${esc(text)}</span>`).join(''):'';
  $('#cover-position-value').textContent=profile.positionY+'%';
  $('#cover-title-y-value').textContent=profile.titleY+'%';
}
async function renderCoverPng(){
  const image=$('#cover-image');await image.decode();
  const p=coverSession.profile,w=1080,h=1440,canvas=document.createElement('canvas');canvas.width=w;canvas.height=h;
  const ctx=canvas.getContext('2d');ctx.fillStyle='#000';ctx.fillRect(0,0,w,h);
  const scale=p.fit==='cover'?Math.max(w/image.naturalWidth,h/image.naturalHeight):Math.min(w/image.naturalWidth,h/image.naturalHeight);
  const dw=image.naturalWidth*scale,dh=image.naturalHeight*scale,dx=(w-dw)/2,dy=(h-dh)*p.positionY/100;
  ctx.drawImage(image,dx,dy,dw,dh);
  if(p.enabled){
    const shade=p.titleY<50?ctx.createLinearGradient(0,0,0,h*.65):ctx.createLinearGradient(0,h,0,h*.4);
    shade.addColorStop(0,p.titleY<50?'rgba(0,0,0,.55)':'rgba(0,0,0,.65)');shade.addColorStop(1,'rgba(0,0,0,0)');
    ctx.fillStyle=shade;ctx.fillRect(0,0,w,h);
    const lines=coverLines(p.title),font=108,lineHeight=122;
    ctx.font=`900 ${font}px "Microsoft YaHei",sans-serif`;ctx.textAlign='center';ctx.textBaseline='middle';ctx.lineJoin='round';ctx.strokeStyle='#080808';ctx.lineWidth=14;
    let y=p.titleY/100*h-(lines.length-1)*lineHeight/2;
    lines.forEach((text,i)=>{ctx.strokeText(text,w/2,y,w-70);ctx.fillStyle=i?'#fff128':'#fff';ctx.fillText(text,w/2,y,w-70);y+=lineHeight});
  }
  return canvas.toDataURL('image/png');
}
document.addEventListener('input',e=>{if(e.target.closest('#cover-form'))updateCoverPreview()});
document.addEventListener('change',e=>{if(e.target.closest('#cover-form'))updateCoverPreview()});
document.addEventListener('submit',async e=>{
  if(e.target.id!=='cover-form')return;e.preventDefault();const b=e.target.querySelector('button[type="submit"]');b.disabled=true;
  try{
    const png=await renderCoverPng();const result=await api('/api/cover-save',{videoId:coverSession.id,media:coverSession.media,profile:coverSession.profile,png});
    $('#cover-feedback').innerHTML=`封面已保存，作品卡片已更新。<a href="${file(result.record.file)}" download="${esc(coverSession.id)}_发布封面_1080x1440.png">下载PNG ↗</a>`;
    await load();toast('发布封面已保存，作品卡片已更新');
  }catch(error){$('#cover-feedback').textContent=error.message}finally{b.disabled=false}
});
