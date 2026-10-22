"""Local publication asset gate; never uploads, publishes, deletes or reschedules.

stage: --root ROOT --video-id ID --cover FILE
check: --root ROOT --manifest JSON --output JSON

Manifest schema publication-assets/1:
videoId, platform, accountId, plannedAt (ISO timezone or null),
payload:{file,sha256}, video:{file,sha256,upload,uploadSourceSha256},
cover:{file,sha256,upload,boundVideoSha256},
review:{videoSha256,coverSha256,summary,coverText,matchReason,
videoContentChecked,sceneMatches,titleMatches,remoteCoverChecked,
localProof:{file,sha256},remoteProof:{file,sha256},reviewedAt,reviewer}.
Human/assistant content and visual review must actually precede its declaration.
"""
from pathlib import Path
from datetime import datetime
import argparse, hashlib, json, re, shutil, sys

def require(value,message):
    if not value: raise ValueError(message)

def read(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''): h.update(block)
    return h.hexdigest()
def save(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def location(root,value):
    p=Path(value);return p.resolve() if p.is_absolute() else (root/p).resolve()
def bound_file(root,item,label):
    p=location(root,item['file'])
    require(p.is_file(),label+'文件不存在')
    require(re.fullmatch('[0-9a-f]{64}',item.get('sha256','')) and digest(p)==item['sha256'],label+'摘要不符，旧核验失效')
    return p
def stage(root,ident,cover):
    require(re.fullmatch('[A-Za-z0-9][A-Za-z0-9_-]{1,60}',ident),'内容编号须可用于独立ASCII资源名')
    cover=location(root,cover);h=digest(cover)
    require(cover.suffix.lower() in ['.png','.jpg','.jpeg','.webp'],'不支持的封面类型')
    target=root/'发布管理/发布资源'/f'{ident}_cover_{h[:16]}{cover.suffix.lower()}'
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists(): require(digest(target)==h,'已有上传副本被改动，不能覆盖')
    else: shutil.copy2(cover,target)
    return {'ok':True,'source':str(cover),'uploadSource':str(target),'sha256':h,'uploaded':False}
def check(root,m):
    require(m.get('schema')=='publication-assets/1','核验清单版本不符')
    ident=m['videoId'];platform=m['platform'];account=m['accountId']
    require(bool(ident and platform and account),'缺内容编号、平台或账号')
    video=bound_file(root,m['video'],'视频');cover=bound_file(root,m['cover'],'封面')
    payload_file=bound_file(root,m['payload'],'最终payload');p=read(payload_file)
    require(m['cover']['boundVideoSha256']==m['video']['sha256'],'封面绑定了另一条视频或旧版视频')
    require(m['video']['uploadSourceSha256']==m['video']['sha256'],'视频上传源记录与实际文件不符')
    review=m['review']
    require(review.get('videoSha256')==m['video']['sha256'] and review.get('coverSha256')==m['cover']['sha256'],'内容/视觉复核未绑定当前视频与封面')
    require(all(review.get(k) is True for k in ['videoContentChecked','sceneMatches','titleMatches','remoteCoverChecked']),'内容或视觉尚未核对，禁止提交')
    require(all(isinstance(review.get(k),str) and review[k].strip() for k in ['summary','coverText','matchReason','reviewedAt','reviewer']),'缺主题、封面文字、对应理由或复核记录')
    bound_file(root,review['localProof'],'本地对应复核截图');bound_file(root,review['remoteProof'],'远端封面截图')
    require(p.get('platforms')==[platform] and p.get('publishType')=='video','payload平台或类型不符')
    forms=p['publishArgs']['accountForms'];require(len(forms)==1,'逐条逐平台核验，不混用批量默认资源')
    form=forms[0];require(form['platformAccountId']==account,'payload目标账号不符')
    resources={}
    for name in ['video','cover']:
        uploaded=read(location(root,m[name]['upload']))
        require(uploaded.get('ok') is True and uploaded.get('action')=='upload',name+'不是有效官方上传回执')
        resource=uploaded['data'];require(form[name]==resource,name+'对象与真实上传响应不符')
        resources[name]=resource
    key=resources['cover']['key'];basename=key.rsplit('/',1)[-1]
    normalized=lambda s:re.sub('[^A-Za-z0-9]','',s).upper()
    require(re.fullmatch('[A-Za-z0-9_.-]+',basename) and normalized(ident) in normalized(basename) and m['cover']['sha256'][:16] in basename,'远端封面Key缺内容编号/摘要，可能发生同名资源碰撞')
    require(form['coverKey']==key,'coverKey与实际上传封面不符')
    cr=resources['cover'];vr=resources['video']
    require(vr['size']==video.stat().st_size,'视频上传大小与实际文件不符')
    expected_cover_size=cr.get('originalSize') if cr.get('compressed') else cr.get('size')
    if expected_cover_size is not None: require(expected_cover_size==cover.stat().st_size,'封面上传大小与源文件不符')
    if platform=='视频号': require(cr['size']<=512*1024,'视频号封面超过512KB')
    scheduled=form['contentPublishForm'].get('scheduledTime')
    if m.get('plannedAt'):
        planned=datetime.fromisoformat(m['plannedAt']);require(planned.tzinfo is not None,'计划时间缺时区')
        require(scheduled==int(planned.timestamp()*1000),'payload计划时间不符')
    else: require(scheduled in [None,0],'即时发布清单却含预约时间')
    registry=root/'发布管理/封面远端资源登记.json'
    if registry.exists():
        for row in read(registry).get('resources',[]):
            require(row.get('key')!=key or row.get('sourceSha256')==m['cover']['sha256'],'同一远端Key对应不同封面摘要，禁止提交')
    return {'ok':True,'videoId':ident,'platform':platform,'accountId':account,'plannedAt':m.get('plannedAt'),'videoSha256':m['video']['sha256'],'coverSha256':m['cover']['sha256'],'coverKey':key,'payloadSha256':m['payload']['sha256'],'reviewer':review['reviewer'],'scope':'字节与最终提交绑定通过；内容/视觉结论来自清单所记录的实际复核，不代表已发布或全片逐字听校'}
def main():
    parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('action',choices=['stage','check']);parser.add_argument('--root',required=True,type=Path)
    parser.add_argument('--video-id');parser.add_argument('--cover');parser.add_argument('--manifest',type=Path);parser.add_argument('--output',type=Path)
    a=parser.parse_args()
    try:
        root=a.root.resolve();require(root.is_dir(),'工作区不存在')
        if a.action=='stage':
            require(a.video_id and a.cover,'缺内容编号或封面');result=stage(root,a.video_id,a.cover)
        else:
            require(a.manifest and a.output,'缺核验清单或输出路径')
            result=check(root,read(a.manifest));result['manifestSha256']=digest(a.manifest)
            save(a.output,result)
        print(json.dumps(result,ensure_ascii=False));return 0
    except (ValueError,KeyError,OSError,TypeError) as e:
        if a.output: save(a.output,{'ok':False,'error':str(e),'scope':'未通过，禁止正式提交'})
        print(json.dumps({'ok':False,'error':str(e)},ensure_ascii=False),file=sys.stderr);return 2
if __name__=='__main__':sys.exit(main())
