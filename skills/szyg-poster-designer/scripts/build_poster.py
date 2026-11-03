from pathlib import Path
import argparse,json,html,shutil,re
from datetime import datetime, timezone
from countdown import calculate

SKILL=Path(__file__).resolve().parent.parent
p=argparse.ArgumentParser();p.add_argument('--spec',required=True);p.add_argument('--style',choices=['editorial','commercial','bold','countdown','case'],required=True);p.add_argument('--out',required=True)
a=p.parse_args();spec_path=Path(a.spec).resolve();s=json.loads(spec_path.read_text(encoding='utf-8-sig'));out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
for rel in ['assets/fonts','assets/images','licenses']:(out/rel).mkdir(parents=True,exist_ok=True)
for font in (SKILL/'assets/fonts').iterdir():shutil.copy2(font,out/'assets/fonts'/font.name)
for license in (SKILL/'licenses').iterdir():shutil.copy2(license,out/'licenses'/license.name)
def esc(v):return html.escape(str(v),quote=True).replace('\n','<br>')
def text(key,tag='div',cls='',default='',check=True):
    v=s.get(key,default);return f'<{tag} class="{cls}" data-copy data-key="{key}"'+(' data-check-box' if check else '')+'>'+esc(v)+f'</{tag}>'
def image(key,cls):
    value=s.get(key)
    if not value:return f'<div class="{cls}" style="display:flex;align-items:center;justify-content:center;color:#777;font:30px/1.6 HanSans">素材待提供</div>'
    src=Path(value)
    if not src.is_absolute():src=(spec_path.parent/src).resolve()
    if not src.is_file():raise ValueError('找不到图片：'+str(src))
    dest=out/'assets/images'/(key+src.suffix.lower());shutil.copy2(src,dest)
    return f'<img class="{cls}" src="assets/images/{dest.name}" alt="项目素材">'
kind=s.get('kind','product')
if a.style=='countdown' and kind!='countdown':raise ValueError('倒计时风格需要kind=countdown')
if a.style=='case' and kind!='case':raise ValueError('案例风格需要kind=case')
if kind=='countdown' and not s.get('sample'):
    if not all(s.get(k) for k in ['deadline','timezone','countdownBasis']):raise ValueError('正式倒计时必须有deadline、timezone与countdownBasis')
    if s['countdownBasis'] not in ['calendarDays','durationDaysCeiling']:raise ValueError('countdownBasis应为calendarDays或durationDaysCeiling')
    result=calculate(s['deadline'],s.get('referenceNow',datetime.now(timezone.utc).isoformat()))
    if result['expired']:raise ValueError('活动已到期，不生成仍在倒计时的正式稿')
    s['countdownCalculation']=result;s['countdownValue']=str(result[s['countdownBasis']]);s['unit']='天'
if kind=='case' and not s.get('sample') and not s.get('evidence'):raise ValueError('正式案例必须有evidence；没有结果时做过程案例')
required=['brand','cta']+({'product':['strap','heroMessage','delivery'],'countdown':['countdownValue','eventName','deadlineText'],'case':['caseTitle','beforeTitle','beforeText','afterTitle','afterText','process','evidence']}[kind])
for k in required:
    if k not in s or str(s[k]).strip()=='':raise ValueError('缺少字段：'+k)
masthead='<header class="masthead">'+text('brandTag','span',default=s['brand'])+text('audience','span')+'</header>'
footer='<footer class="bottom">'+text('cta','div','cta')+text('brand','div','mini-brand')+'</footer>'+text('disclaimer','div','disclaimer',check=False)
marker='<div class="sample-marker">用途示范 · 非真实活动或经营结果</div>' if s.get('sample') and kind=='countdown' else ''
if kind=='product':
    features=s.get('features',[])
    if not features or len(features)>6:raise ValueError('起点模板支持1至6项；更多内容请调整模板或拆页')
    modules=[]
    for i,f in enumerate(features):
        modules.append(f'<section class="module"><div class="module-head"><span class="num">{i+1:02d}</span><h3 data-copy data-check-box data-key="feature-{i}">{esc(f["title"])}</h3></div><p data-copy data-check-box>{esc(f["description"])}</p></section>')
    strap=s['strap']
    strap_markup=text('strap','div','strap')
    if a.style=='bold':
        s['strap']=re.sub(r'\s*[·、]\s*','\n',strap)
        strap_markup='<div class="strap" data-copy data-check-box data-key="strap">'+''.join('<span>'+esc(line)+'</span>' for line in s['strap'].splitlines())+'</div>'
    body=masthead+text('brand','h1','title')+strap_markup+'<section class="hero"><div>'+text('heroMessage','div','hero-message')+text('intro','span','intro',default='从安装上手，到真实业务实操')+'</div>'+image('image','portrait')+'</section><section class="features">'+''.join(modules)+'</section>'+text('delivery','div','delivery')+footer
elif kind=='countdown':
    body=marker+masthead+text('brand','h1','title')+text('remainingLabel','div','remaining-label',default='距活动开始还有')+'<div class="time">'+text('countdownValue','strong')+text('unit','span',default='天')+'</div>'+text('eventName','div','event-name')+text('deadlineText','div','deadline-text')+footer
else:
    body=masthead+text('caseTitle','h1','title')+text('caseDeck','div','case-deck')+'<section class="comparison"><div class="proof-card">'+text('beforeTitle','div','proof-title')+image('beforeImage','proof-image')+text('beforeText','div','proof-caption')+'</div><div class="proof-card">'+text('afterTitle','div','proof-title')+image('afterImage','proof-image')+text('afterText','div','proof-caption')+'</div></section>'+text('process','div','process')+text('evidence','div','evidence')+text('delivery','div','delivery')+footer
template=(SKILL/'assets/templates/poster.html').read_text(encoding='utf-8')
values={'brand':esc(s['brand']),'style':a.style,'body':body,'status':'本地试做，待用户审稿；移动HTML时请保留assets目录'}
for key,value in values.items():template=template.replace('{{'+key+'}}',value)
if re.search(r'\{\{\w+\}\}',template):raise ValueError('模板存在未替换字段')
(out/'poster.html').write_text(template,encoding='utf-8')
(out/'input.json').write_text(json.dumps(s,ensure_ascii=False,indent=2),encoding='utf-8')
copy=[f'{k}: {v}' for k,v in s.items() if isinstance(v,(str,int,float)) and k not in ['image','beforeImage','afterImage']]
copy += [f'{f["title"]}：{f["description"]}' for f in s.get('features',[])]
(out/'文案.txt').write_text('\n'.join(copy),encoding='utf-8')
print(json.dumps({'html':str(out/'poster.html'),'style':a.style,'kind':kind,'sample':bool(s.get('sample'))},ensure_ascii=False))
