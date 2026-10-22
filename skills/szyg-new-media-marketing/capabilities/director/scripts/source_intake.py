"""Flat, stable source intake. Preview by default; --apply commits a verified plan.
No publishing, automatic editing, or background watching is performed.
"""
from pathlib import Path
import argparse,json,re,hashlib,os,sys,datetime,shutil
from urllib.parse import quote
MEDIA={'.mp4','.mov','.mkv','.m4v','.avi','.webm','.mts','.m2ts'}
def read(p,default):
 return json.loads(p.read_text(encoding='utf-8-sig')) if p.exists() else default
def save(p,d):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p):
 with p.open('rb') as f:
  h=hashlib.sha256()
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
  return h.hexdigest()
def now():return datetime.datetime.now().astimezone().isoformat(timespec='seconds')
def rel(p,r):return p.relative_to(r).as_posix()
def plan(root):
 inbox=(root/'待剪素材').resolve();assert inbox.is_dir()
 cat=read(root/'发布管理/内容登记.json',{'videos':[]});reg=read(root/'发布管理/原片登记.json',{'schema':'flat-source-registry/1','sources':[],'runs':[]})
 maxid=max([int(v['id'][2:]) for v in cat['videos'] if re.fullmatch(r'V-\d{3,}',v['id'])]+[0])
 used={};items=[];reserved=set();hashmap={x['sha256']:x for x in reg['sources']};seen={}
 for p in sorted(inbox.rglob('*'),key=lambda p:p.as_posix().casefold()):
  if not p.is_file():continue
  assert p.resolve().is_relative_to(inbox),str(p)
  if p.suffix.lower() not in MEDIA:raise ValueError('待剪素材中有非视频文件，保留并人工核对：'+str(p))
  old=rel(p,root);v=next((v for v in cat['videos'] if old in v.get('sources',[])),None)
  digest=sha(p);prior=hashmap.get(digest);migration_id=None
  if digest in seen:raise ValueError('本批有两份相同字节的原片，未删除文件：'+seen[digest]+' / '+old)
  seen[digest]=old
  old_record=next((x for x in reg['sources'] if x['path']==old),None)
  if old_record and old_record['sha256']!=digest:raise ValueError('已登记的原片被外部替换，先核对字节：'+old)
  if prior:
   vid=prior['contentId'];slot=prior['slot']
   if v and v['id']!=vid:raise ValueError('相同文件摘要出现不同内容编号，先核对：'+old)
   if (root/prior['path']).exists() and not p.samefile(root/prior['path']):
    raise ValueError('发现相同字节的第二份原片，未删除任何文件，请先核对：'+old)
  else:
   if v and re.fullmatch(r'V-\d{3,}',v['id']):vid=v['id']
   elif re.fullmatch(r'(V-\d{3,})_原片_(\d{2,})',p.stem):vid=p.stem.split('_')[0];maxid=max(maxid,int(vid[2:]))
   else:
    maxid+=1;vid=f'V-{maxid:03}';migration_id=v['id'] if v else None
   used.setdefault(vid,{x['slot'] for x in reg['sources'] if x['contentId']==vid})
   slot=next(n for n in range(1,10000) if n not in used[vid]);used[vid].add(slot)
  target=inbox/f'{vid}_原片_{slot:02}{p.suffix.lower()}';new=rel(target,root)
  assert target.resolve().parent==inbox and new not in reserved,new;reserved.add(new)
  if target.exists() and not p.samefile(target):raise FileExistsError(str(target))
  items.append({'old':old,'new':new,'contentId':vid,'previousContentId':migration_id,'slot':slot,'sha256':digest,'size':p.stat().st_size,'modifiedNs':str(p.stat().st_mtime_ns),'originalName':p.name,'needsMove':old!=new,'title':v.get('title') if v else p.stem})
 return cat,reg,items
def replacements(root,items):
 pairs={}
 for item in items:
  if not item['needsMove']:continue
  a=item['old'];b=item['new']
  for prefix in ['',root.as_posix()+'/',str(root)+'\\']:
   for slash in ['/','\\']:
    aa=prefix+a.replace('/',slash);bb=prefix+b.replace('/',slash)
    pairs[aa]=bb;pairs[aa.replace('\\','\\\\')]=bb.replace('\\','\\\\')
    pairs[quote(aa)]=quote(bb);pairs[quote(aa,safe='')]=quote(bb,safe='')
  for ensure in [True,False]:
   pairs[json.dumps(a,ensure_ascii=ensure)[1:-1]]=json.dumps(b,ensure_ascii=ensure)[1:-1]
  if item.get('previousContentId'):pairs[item['previousContentId']]=item['contentId']
 return sorted(pairs.items(),key=lambda x:-len(x[0]))
def apply(root,cat,reg,items):
 stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f');archive=root/'整理记录/原片接收'/stamp;archive.mkdir(parents=True)
 save(archive/'执行前计划.json',items)
 pairs=replacements(root,items);changes=[];skipped=[];excluded={'_tools','node_modules','.git','__pycache__','素材库','整理记录'}
 frozen=('备份','快照','验收','输入分析','短窗复核','参考分析','中间稿','音尾时钟','登记前','原片接收')
 allowed={'.py','.json','.md','.txt','.html','.js','.mjs','.cmd','.ps1','.csv','.yaml','.yml','.ass'}
 # Migrate working references; retain old evidence snapshots as recorded.
 for folder,dirs,names in os.walk(root):
  dirs[:]=[d for d in dirs if d not in excluded and not any(k in d for k in frozen)]
  for name in names:
   p=Path(folder)/name
   if p.suffix.lower() not in allowed or p.resolve()==Path(__file__).resolve() or any(k in name for k in ['验收','来源信息','完整转写','发布记录','原片登记']):continue
   if p.stat().st_size>18_000_000:continue
   raw=p.read_bytes()
   try:s=raw.decode('utf-8-sig')
   except UnicodeDecodeError:continue
   t=s
   for a,b in pairs:t=t.replace(a,b)
   if p.suffix.lower() in {'.py','.ps1','.cmd','.js','.mjs'}:
    for item in items:
     if not item['needsMove']:continue
     for q in ["'",'"']:
      t=t.replace(q+item['originalName']+q,q+Path(item['new']).name+q)
   if t!=s:
    if p.suffix=='.json':json.loads(t)
    backup=archive/'工作引用修改前'/p.relative_to(root);backup.parent.mkdir(parents=True,exist_ok=True);backup.write_bytes(raw)
    changes.append((p,t,raw.startswith(b'\xef\xbb\xbf')))
 moved=[]
 try:
  for item in items:
   old=root/item['old'];new=root/item['new']
   assert old.resolve().is_relative_to((root/'待剪素材').resolve()) and new.resolve().parent==(root/'待剪素材').resolve()
   if item['needsMove']:old.rename(new);moved.append(item)
   assert new.stat().st_size==item['size'] and sha(new)==item['sha256'],str(new)
  for p,t,bom in changes:p.write_bytes((b'\xef\xbb\xbf' if bom else b'')+t.encode('utf-8'))
 except Exception:
  for item in reversed(moved):(root/item['new']).rename(root/item['old'])
  for p,_,_ in changes:
   b=archive/'工作引用修改前'/p.relative_to(root)
   if b.exists():p.write_bytes(b.read_bytes())
  raise
 # Explicitly update canonical catalog; provisional scan IDs become assigned V IDs once only.
 cat=read(root/'发布管理/内容登记.json',cat)
 for item in items:
  v=next((v for v in cat['videos'] if v['id']==item['contentId']),None)
  if v is None:
   v={'id':item['contentId'],'title':item['title'] or '新口播（待识别主题）','sources':[item['new']],'series':'待定主题','projectDirs':[],'deliveryDirs':[],'primaryVideo':None,'needsEditing':True,'productionStatus':'已规范原片命名，待剪辑','registeredAt':now()};cat['videos'].append(v)
  if item['old'] in v.get('sources',[]):v['sources']=[item['new'] if x==item['old'] else x for x in v['sources']]
  if item['new'] not in v.get('sources',[]):v.setdefault('sources',[]).append(item['new'])
  v.setdefault('sourceIdentity',{})[item['new']]={'sha256':item['sha256'],'originalName':item['originalName'],'renamedAt':now()}
  if item.get('previousContentId'):v.setdefault('historicalIds',[]).append(item['previousContentId'])
  existing=next((s for s in reg['sources'] if s['sha256']==item['sha256']),None)
  if existing:
   if item['old']!=item['new']:existing.setdefault('previousPaths',[]).append(item['old'])
   existing['path']=item['new']
  else:reg['sources'].append({'contentId':item['contentId'],'slot':item['slot'],'path':item['new'],'originalName':item['originalName'],'previousPaths':[item['old']] if item['old']!=item['new'] else [],'sha256':item['sha256'],'size':item['size'],'modifiedNs':item['modifiedNs'],'recordedAt':now()})
 save(root/'发布管理/内容登记.json',cat)
 inbox=(root/'待剪素材').resolve();removed=[]
 for d in sorted([p for p in inbox.rglob('*') if p.is_dir()],key=lambda p:len(p.parts),reverse=True):
  assert d.resolve().is_relative_to(inbox) and d.resolve()!=inbox
  if not any(d.iterdir()):d.rmdir();removed.append(str(d))
 assert not any(p.is_dir() for p in inbox.iterdir()),'尚有非空子目录，未强制删除'
 report={'at':now(),'files':len(items),'moved':len(moved),'referencesUpdated':len(changes),'emptyDirectoriesRemoved':removed,'sourceHashesVerified':True,'allFlat':True,'items':items,'changedFiles':[rel(p,root) for p,_,_ in changes],'archive':rel(archive,root)}
 save(archive/'执行验收.json',report);reg['runs'].append({k:report[k] for k in ['at','files','moved','referencesUpdated','archive']});save(root/'发布管理/原片登记.json',reg)
 save(root/'.agents/source-intake.json',{'schema':'flat-source-intake/1','directory':'待剪素材','flat':True,'filenamePattern':'{内容编号}_原片_{两位序号}{原扩展名小写}','example':'V-022_原片_01.mp4','assignId':'复用已有V编号；未登记素材取下一个顺序编号，扫描临时ID保留映射','sourceRegistry':'发布管理/原片登记.json','entry':str(Path(__file__).resolve())+' --root '+str(root)+' --apply','beforeEditing':True,'backgroundWatch':False,'preserveBytes':True,'titleInLedger':True})
 print(json.dumps({k:report[k] for k in ['files','moved','referencesUpdated','allFlat','archive']},ensure_ascii=False),flush=True)
def main():
 sys.stdout.reconfigure(encoding='utf-8');p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--apply',action='store_true');p.add_argument('--plan',type=Path);a=p.parse_args();root=a.root.resolve();cat,reg,items=plan(root)
 if a.plan:save(a.plan,items)
 if not a.apply:print(json.dumps(items,ensure_ascii=False,indent=2));return
 if not any(i['needsMove'] or i['sha256'] not in {x['sha256'] for x in reg['sources']} for i in items):print(json.dumps({'unchanged':True,'files':len(items)},ensure_ascii=False));return
 apply(root,cat,reg,items)
if __name__=='__main__':main()
