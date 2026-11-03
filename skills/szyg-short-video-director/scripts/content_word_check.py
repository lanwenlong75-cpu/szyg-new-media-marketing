"""Version-bound publication text checks. No claim of platform approval."""
from pathlib import Path
import argparse,json,re,hashlib,datetime,html

def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def load_lexicon(path,seen=None):
 path=Path(path).resolve();seen=set() if seen is None else seen
 if path in seen:raise ValueError('词库循环引用')
 seen.add(path);d=read(path);rules=[];sources=[];bindings=[]
 for name in d.get('includes',[]):
  p=Path(name);p=p if p.is_absolute() else path.parent/p
  a,b,c=load_lexicon(p,seen.copy());rules+=a;sources+=b;bindings+=c
 rules+=d.get('rules',[]);sources+=d.get('sources',[]);bindings.append({'file':str(path),'sha256':sha(path)})
 if len({r['id'] for r in rules})!=len(rules):raise ValueError('词库规则ID重复')
 return rules,sources,bindings
def policy(root,entity):
 p=root/'.agents/publish-word-policy.json'
 if p.exists():
  d=read(p);scope=d['scope']
  if scope['entityId']!=entity or Path(scope['projectRoot']).resolve()!=root:raise ValueError('项目/IP范围与用词偏好不符')
  return d,root/d['lexicon']
 return {'audioPolicy':'preserve','defaultOnly':True},Path(__file__).resolve().parents[1]/'assets/publish-risk-terms.json'
def matching(text,rule):
 if rule.get('pattern'):pattern=rule['pattern']
 else:pattern=re.escape(rule['term'])
 return list(re.finditer(pattern,text,re.I if rule.get('ignoreCase') else 0))
def hits(text,rules,platforms,entity):
 found=[];occupied=[]
 # Longer explicit user replacements win. Context rules may still report aliases.
 for r in sorted(rules,key=lambda x:len(x.get('term','')),reverse=True):
  if r.get('entityId') and r['entityId']!=entity:continue
  if not set(r['platforms']).intersection(platforms):continue
  for m in matching(text,r):
   if r['action']=='replace' and any(m.start()<b and m.end()>a for a,b in occupied):continue
   if r['action']=='replace':occupied.append((m.start(),m.end()))
   found.append({'ruleId':r['id'],'term':m.group(),'start':m.start(),'end':m.end(),'action':r['action'],'replacement':r.get('replacement'),'category':r['category'],'evidenceKind':r['evidenceKind'],'note':r['note'],'context':text[max(0,m.start()-25):min(len(text),m.end()+25)]})
 return sorted(found,key=lambda x:(x['start'],x['end']))
def extract(path,fmt):
 text=path.read_text(encoding='utf-8-sig')
 if fmt=='text':return [{'location':'text','text':text}]
 if fmt=='ass':
  out=[]
  for i,line in enumerate(text.splitlines()):
   if line.startswith('Dialogue:'):
    parts=line.split(',',9)
    if len(parts)!=10:raise ValueError('ASS事件格式不完整')
    out.append({'location':f'line:{i+1}','start':parts[1],'end':parts[2],'text':re.sub(r'\{[^}]*\}','',parts[9]).replace(r'\N','\n')})
  return out
 if fmt=='captions':
  d=json.loads(text)
  return [{'location':f'cue:{i+1}','start':c['start'],'end':c['end'],'text':c.get('displayText',c['text'])} for i,c in enumerate(d)]
 if fmt=='models':
  d=json.loads(text);return [{'location':m['id']+'/'+n['id'],'start':n.get('at'),'end':n.get('until'),'text':n['text']} for m in d['models'] for n in m['nodes']]
 raise ValueError('未支持的可见文本格式：'+fmt)
def substitute(text,rules,platforms,entity):
 changes=[h for h in hits(text,rules,platforms,entity) if h['action']=='replace']
 for h in reversed(changes):text=text[:h['start']]+h['replacement']+text[h['end']:]
 return text,changes
def transform(root,entity,src,fmt,dst,platforms):
 pol,lex=policy(root,entity);rules,sources,binds=load_lexicon(lex);src=src.resolve();dst=dst.resolve()
 if not src.is_relative_to(root) or not dst.is_relative_to(root):raise ValueError('输入/输出必须在本项目')
 if src==dst or dst.exists():raise ValueError('修订必须另存新文件，不能覆盖原输入或已有交付')
 raw=src.read_bytes();content=raw.decode('utf-8-sig');changes=[]
 if fmt=='captions':
  data=json.loads(content)
  for i,c in enumerate(data):
   value,found=substitute(c.get('displayText',c['text']),rules,platforms,entity)
   if found:
    c['displayText']=value;c['displaySubstitutions']=found;c['spokenText']=c['text'];changes += [x|{'cue':i+1,'startTime':c['start'],'endTime':c['end']} for x in found]
  output=json.dumps(data,ensure_ascii=False,indent=2)+'\n'
 elif fmt=='ass':
  lines=[]
  for i,line in enumerate(content.splitlines(keepends=True)):
   if line.startswith('Dialogue:'):
    p=line.split(',',9);parts=re.split(r'(\{[^}]*\})',p[9]);new=[]
    for part in parts:
     if part.startswith('{'):new.append(part);continue
     value,found=substitute(part,rules,platforms,entity);new.append(value);changes += [x|{'line':i+1,'startTime':p[1],'endTime':p[2]} for x in found]
    p[9]=''.join(new);line=','.join(p)
   lines.append(line)
  output=('\ufeff' if raw.startswith(b'\xef\xbb\xbf') else '')+''.join(lines)
 elif fmt=='text':output,changes=substitute(content,rules,platforms,entity)
 else:raise ValueError('此格式仅检查，不自动改图形或来源证据')
 dst.parent.mkdir(parents=True,exist_ok=True)
 with dst.open('x',encoding='utf-8',newline='') as f:f.write(output)
 return {'source':str(src),'sourceSha256':sha(src),'output':str(dst),'outputSha256':sha(dst),'changes':changes,'audioPolicy':pol['audioPolicy'],'lexiconBindings':binds}
def scan(root,entity,manifest):
 pol,lex=policy(root,entity);rules,sources,binds=load_lexicon(lex);man=read(manifest)
 if man['entityId']!=entity:raise ValueError('检查清单的服务对象不匹配')
 platforms=man['platforms'];result=[];allhits=[]
 kinds={s['kind'] for s in man['surfaces']}
 missing=['kind:'+k for k in pol.get('requiredSurfaces',['captions','graphics','cover','title','publish_copy']) if k not in kinds]
 if len({s['id'] for s in man['surfaces']})!=len(man['surfaces']):raise ValueError('检查表面ID重复')
 for s in man['surfaces']:
  if s.get('status')=='not_present':result.append({'id':s['id'],'kind':s['kind'],'status':'not_present','reason':s['reason']});continue
  if not s.get('path'):
   result.append({'id':s['id'],'kind':s['kind'],'status':'not_checked','reason':s.get('reason','未提供')});missing.append(s['id']);continue
  p=Path(s['path']);p=p if p.is_absolute() else root/p;p=p.resolve()
  if not p.is_relative_to(root) or not p.is_file():raise ValueError('检查文件缺失或不在本项目：'+str(p))
  records=extract(p,s['format']);hs=[]
  for rec in records:
   for h in hits(rec['text'],rules,platforms,entity):hs.append(h|{'surface':s['id'],'location':rec['location'],'startTime':rec.get('start'),'endTime':rec.get('end')})
  # Speech is audited as original evidence, never auto-rewritten or treated as visible text.
  speech=s['kind']=='speech';allhits += [h for h in hs if not speech]
  result.append({'id':s['id'],'kind':s['kind'],'status':'checked','file':str(p),'sha256':sha(p),'records':len(records),'hits':hs,'speechPreservedByUserPolicy':speech and pol['audioPolicy']=='preserve'})
 auto=[h for h in allhits if h['action']=='replace'];review=[h for h in allhits if h['action']=='review']
 return {'schema':'publication-word-check/1','checkedAt':datetime.datetime.now().astimezone().isoformat(timespec='seconds'),'entityId':entity,'platforms':platforms,'lexiconBindings':binds,'surfaces':result,'remainingUserReplacements':auto,'contextReview':review,'uncheckedSurfaces':missing,'textReplacementPassed':not auto,'allVisibleSurfacesChecked':not missing,'platformApproval':None,'audioPolicy':pol['audioPolicy'],'disclaimer':'词库不是平台完整禁词清单，命中不等于违规，替换不等于平台认可；截图、录屏、原声和发布上下文仍须按实际范围核对。'}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('command',choices=['scan','transform']);ap.add_argument('--root',type=Path,required=True);ap.add_argument('--entity',required=True);ap.add_argument('--manifest',type=Path);ap.add_argument('--input',type=Path);ap.add_argument('--format',choices=['ass','captions','text']);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--platform',action='append',default=[]);a=ap.parse_args();root=a.root.resolve()
 if a.command=='scan':
  r=scan(root,a.entity,a.manifest);write(a.output,r);print(json.dumps({'report':str(a.output),'replacements':len(r['remainingUserReplacements']),'reviews':len(r['contextReview']),'unchecked':r['uncheckedSurfaces'],'platformApproval':None},ensure_ascii=False));return 2 if r['remainingUserReplacements'] or r['contextReview'] or r['uncheckedSurfaces'] else 0
 r=transform(root,a.entity,a.input,a.format,a.output,a.platform or ['douyin','weixin_channels']);write(a.output.with_name(a.output.name+'.changes.json'),r);print(json.dumps({'output':str(a.output),'changes':len(r['changes']),'audioPolicy':r['audioPolicy']},ensure_ascii=False));return 0
if __name__=='__main__':raise SystemExit(main())
