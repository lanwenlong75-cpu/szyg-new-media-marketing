#!/usr/bin/env python3
"""Local content registry, read-only publication sync, and deterministic table views."""
import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

TZ = timezone(timedelta(hours=8))
MEDIA = {'.mp4', '.mov', '.mkv', '.webm', '.m4v', '.avi'}
PLATFORMS = ['抖音', '小红书', '视频号']

def now(): return datetime.now(TZ).isoformat(timespec='seconds')
def read(p, default=None):
    if not p.exists(): return default
    return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    temp = p.with_suffix(p.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(p)
def backup(p):
    if p.exists():
        out=p.parent/'历史快照'/f'{datetime.now(TZ):%Y%m%d_%H%M%S_%f}_{p.name}'
        out.parent.mkdir(exist_ok=True)
        shutil.copy2(p,out)
def absolute(root, value):
    if not value: return None
    p=Path(value)
    return p if p.is_absolute() else root/p
def relative(root, value):
    if not value: return None
    p=absolute(root,value)
    try: return p.relative_to(root).as_posix()
    except ValueError: return str(p)
def time_value(value):
    if not value or isinstance(value, bool): return None
    if isinstance(value, (int,float)):
        return datetime.fromtimestamp(value/(1000 if value>1e11 else 1), TZ).isoformat(timespec='seconds')
    return str(value)
def time_dt(value):
    try:
        d=datetime.fromisoformat(value)
        return d if d.tzinfo else d.replace(tzinfo=TZ)
    except (TypeError, ValueError): return None
def clean_message(value):
    return re.sub(r'https?://\S+', '[资源地址]', str(value or ''))[:700]
def public_url(platform, pid, url=None):
    # Export only canonical public URLs, never signed media URLs or access tokens.
    if platform=='抖音' and pid and str(pid).isdigit(): return f'https://www.douyin.com/video/{pid}'
    if platform=='小红书' and pid: return f'https://www.xiaohongshu.com/explore/{pid}'
    if url:
        parsed=urlsplit(url)
        if parsed.scheme in ('http','https') and parsed.hostname in ('www.douyin.com','www.xiaohongshu.com'):
            return urlunsplit((parsed.scheme,parsed.netloc,parsed.path,'',''))
    return None
def resolve_status(stage, result, scheduled, checked, confirmed=False):
    if stage=='scheduled':
        due=time_dt(scheduled)
        return '到点待核验' if due and due<=time_dt(checked) else '定时发布'
    if stage=='success' and result=='success': return '已发布'
    if result in ('fail','failed','error'): return '发布失败'
    if stage in ('review','审核'):
        return '已发布（历史确认，回执冲突）' if confirmed else '审核中'
    if confirmed: return '已发布（历史确认）'
    return '发布中' if result=='doing' else '待确认'

def cli_json(args):
    exe=shutil.which('yxer')
    if not exe: raise RuntimeError('未找到 yxer；保留已有快照，只能离线刷新')
    run=subprocess.run([exe,*args],capture_output=True,encoding='utf-8',errors='replace',timeout=60)
    try: data=json.loads(run.stdout)
    except ValueError: raise RuntimeError('yxer 未返回有效 JSON；未改写既有记录')
    if run.returncode or not data.get('ok'):
        raise RuntimeError(f'yxer 查询失败：{clean_message(data.get("error") or "请查看查询证据")}')
    return data

def import_local(root, dest):
    """Import the existing state files as metadata/evidence, never infer publish from a payload."""
    catalog=read(dest/'内容登记.json',{'videos':[]})
    by_title={t:v['id'] for v in catalog['videos'] for t in v.get('publishTitles',[])}
    meta=read(dest/'任务来源.json',{})
    state_files={absolute(root,p) for p in catalog.get('publicationStateFiles',[])}
    for video in catalog['videos']:
        for folder in video.get('deliveryDirs',[]):
            p=absolute(root,folder)
            if p and p.is_dir():
                state_files.update(p.rglob('发布状态.json'))
                state_files.update(p.rglob('发布记录摘要.json'))
    for path in state_files:
        obj=read(path)
        if not obj: continue
        rows=list(obj.get('platforms',{}).values())+obj.get('results',[])
        for row in rows:
            tid=row.get('taskSetId')
            if not tid: continue
            existing=meta.get(tid,{})
            platform=row.get('platform') or next((k for k,v in obj.get('platforms',{}).items() if v is row),None)
            f=row.get('file') or obj.get('video') or existing.get('file')
            existing.update(dict(videoId=by_title.get(row.get('title')) or existing.get('videoId'), platform=platform, account=row.get('account'),
                file=relative(root,f),sha256=row.get('sha256') or existing.get('sha256'),plannedAt=row.get('time'),
                source=relative(root,path),sourceCheckedAt=obj.get('checkedAt') or row.get('checkedAt'),
                originalStatus=row.get('status'),publishId=row.get('publishId')))
            if obj.get('douyinUserConfirmed') and platform=='抖音':
                existing['confirmedPublished']=True
                existing['confirmation']=obj['douyinUserConfirmed']
            meta[tid]=existing
    write(dest/'任务来源.json',meta)

def public_evidence(value):
    if isinstance(value, dict):
        return {k: public_evidence(v) for k,v in value.items() if not re.search(r'(?i)(token|password|api.?key|authorization|cookie|secret|coverurl|avatar|videourl|pageurl)', k)}
    if isinstance(value, list): return [public_evidence(v) for v in value]
    if isinstance(value, str) and re.search(r'https?://', value): return clean_message(value)
    return value

def sync(root,dest, imported=None):
    checked=now()
    data=read(imported) if imported else cli_json(['query','records','--limit','1000','--json'])
    if not data or not data.get('ok'): raise RuntimeError('发布记录查询失败；保留已有快照')
    obj=data['data']; rows=obj.get('data',[])
    complete=obj.get('totalPage',1)<=1 and len(rows)>=obj.get('totalSize',len(rows))
    evidence=dest/'证据'/f'回读_{datetime.now(TZ):%Y%m%d_%H%M%S_%f}'
    evidence.mkdir(parents=True,exist_ok=True)
    write(evidence/'发布任务列表.json', public_evidence(data))
    catalog=read(dest/'内容登记.json',{'videos':[]})
    by_title={t:v['id'] for v in catalog['videos'] for t in v.get('publishTitles',[])}
    meta=read(dest/'任务来源.json',{})
    history=read(dest/'发布记录.json',{'schema':'publication-events/1','snapshots':[]})
    events=[]; failures=[]
    for row in rows:
        tid=row['id']; m=meta.get(tid,{})
        try:
            if imported:
                detail=read(imported.parent/f'任务_{tid}.json')
                if not detail or not detail.get('ok'): raise RuntimeError('缺少完整任务详情')
            else: detail=cli_json(['query','details',tid,'--json'])
            write(evidence/f'任务_{tid}.json',public_evidence(detail))
            payload=detail['data']
            if payload.get('totalPage',1)>1: raise RuntimeError('任务详情有多页，尚未完整读取')
            for task in payload.get('tasks',[]):
                platform=task.get('platformName') or m.get('platform') or ','.join(row.get('platforms',[]))
                scheduled=time_value(task.get('plannedPublishTime')) or m.get('plannedAt')
                if not scheduled and not isinstance(task.get('isTimed'), bool):
                    scheduled=time_value(task.get('isTimed'))
                event=dict(taskSetId=tid,taskId=task.get('id'),videoId=m.get('videoId') or by_title.get(row.get('title')),
                    title=row.get('title'),platform=platform,account=task.get('platformAccountName') or m.get('account'),
                    accountId=task.get('platformAccountId'),submittedAt=time_value(row.get('createdAt')),
                    plannedAt=scheduled,actualPublishedAt=None,checkedAt=checked,
                    status=resolve_status(task.get('stages'),task.get('stageStatus'),scheduled,checked,m.get('confirmedPublished')),
                    confirmedPublished=m.get('confirmedPublished',False),stage=task.get('stages'),result=task.get('stageStatus'),
                    taskSetStatus=row.get('taskSetStatus'),publishId=task.get('publishId') or m.get('publishId'),
                    file=m.get('file'),sha256=m.get('sha256'),error=clean_message(task.get('errorMessage')),
                    source=relative(root,evidence/f'任务_{tid}.json'),metadataSource=m.get('source'),
                    url=public_url(platform,task.get('publishId'),task.get('openUrl')),
                    notes='实际发布时间接口未提供；提交时间不等于发布时间。')
                if m.get('confirmedPublished') and task.get('stages')=='review':
                    event['notes']='历史记录含用户已发布确认；本轮详情仍显示审核中，存在冲突，需核对作品公开状态。'
                events.append(event)
        except Exception as error:
            failures.append({'taskSetId':tid,'error':clean_message(error)})
    snap=dict(checkedAt=checked,complete=complete and not failures,totalTasks=obj.get('totalSize'),
              fetchedTasks=len(rows),failures=failures,events=events)
    history['snapshots'].append(snap)
    write(dest/'发布记录.json',history)
    print(json.dumps({'queried':len(rows),'events':len(events),'complete':snap['complete'],'failures':len(failures)},ensure_ascii=False))

def role(path):
    s=str(path).lower()
    if any(x in s for x in ('入口修改前备份','修改前备份','历史快照')): return '备份'
    if '素材库' in s: return '可复用素材/参考片'
    if '待剪素材' in s: return '原片'
    if '口播审稿台' in s: return '历史审稿/工具复核'
    if any(x in s for x in ('/源片段/','/chunks/','/segments/','/片段/','/切片/','_pcm.mkv','/源切片/','/中间片段/')): return '工程切片/中间媒体'
    if any(x in s for x in ('sample','preview','qa_','验收片段','前12秒','二十秒','试听','检查片段','抽查','声画','对照','retake','listen')): return '复核片段/样片'
    if any(x in s for x in ('母版','无字','master')): return '无字幕母版'
    if '试剪' in s: return '试剪版本'
    if '成片交付' in s: return '交付视频'
    if '剪辑项目' in s: return '工程视频/历史版本'
    return '其他视频文件'

def inventory(root,catalog):
    files=[]
    excluded={'_tools','adu-motion-video','szyg-duli-motion-video','szyg-duli-motion-video-legacy','发布管理','整理记录','.git','node_modules','__pycache__'}
    for directory, dirs, names in os.walk(root):
        dirs[:]=[d for d in dirs if d not in excluded]
        for name in names:
            p=Path(directory)/name
            if p.suffix.lower() not in MEDIA: continue
            rel=p.relative_to(root).as_posix()
            ids=[]
            for v in catalog['videos']:
                paths=v.get('sources',[])+[v.get('primaryVideo')]
                owned=v.get('projectDirs',[])+v.get('deliveryDirs',[])
                if rel in paths or any(rel.startswith(d.rstrip('/')+'/') for d in owned): ids.append(v['id'])
            stat=p.stat()
            files.append(dict(path=rel,name=name,size=stat.st_size,role=role(rel),videoIds=ids,modifiedAt=time_value(stat.st_mtime)))
    return sorted(files,key=lambda f:f['path'])

def discover(root,dest,catalog,files):
    new=[]
    for f in files:
        if f['role']!='原片' or f['videoIds']: continue
        id='V-'+hashlib.sha256(f['path'].encode()).hexdigest()[:10]
        v=dict(id=id,title=f['name']+'（主题待确认）',series='待定主题',sources=[f['path']],
               primaryVideo=None,preview=None,projectDirs=[],deliveryDirs=[],productionStatus='未查到剪辑工程',
               notes='扫描发现的新原片，尚未确认主题与工程归属。',publishTitles=[],registeredAt=now())
        catalog['videos'].append(v); f['videoIds']=[id]; new.append(id)
    # For new delivery leaves, create a review entry. Do not select a latest version by filename.
    groups={}
    for f in files:
        if f['role']=='交付视频' and not f['videoIds']:
            groups.setdefault(str(Path(f['path']).parent).replace('\\','/'),[]).append(f)
    for folder, fs in groups.items():
        id='V-'+hashlib.sha256(folder.encode()).hexdigest()[:10]
        if any(v['id']==id for v in catalog['videos']): continue
        v=dict(id=id,title=Path(folder).name+'（交付归属待确认）',series='待定主题',sources=[],
               primaryVideo=None,preview=None,projectDirs=[],deliveryDirs=[folder],productionStatus='发现交付，待确认版本',
               notes='扫描发现交付目录；主版本、原片与主题须按工程证据补齐。',publishTitles=[],registeredAt=now())
        catalog['videos'].append(v)
        for f in fs: f['videoIds']=[id]
        new.append(id)
    if new:
        backup(dest/'内容登记.json'); write(dest/'内容登记.json',catalog)
    return new

def metadata(root, dest, path):
    p=absolute(root,path)
    if not p or not p.exists(): return {}
    cache=read(dest/'媒体参数缓存.json',{})
    key=str(p); stat=p.stat(); stamp=[stat.st_size,stat.st_mtime_ns]
    if cache.get(key,{}).get('stamp')==stamp: return cache[key]['metadata']
    probe=shutil.which('ffprobe')
    if not probe:
        probe=next((str(p) for p in (root/'_tools').glob('ffmpeg*/bin/ffprobe.exe')),None)
    if not probe: return {}
    result=subprocess.run([probe,'-v','error','-show_entries','format=duration:stream=codec_type,width,height',
                           '-of','json',str(p)],capture_output=True,encoding='utf-8',timeout=30)
    if result.returncode: return {}
    data=json.loads(result.stdout); stream=next((s for s in data.get('streams',[]) if s.get('codec_type')=='video'),{})
    out={'duration':round(float(data.get('format',{}).get('duration',0)),3),'width':stream.get('width'),'height':stream.get('height')}
    cache[key]={'stamp':stamp,'metadata':out}; write(dest/'媒体参数缓存.json',cache)
    return out

def watch_view(root,dest,view):
    """Generate current-version posters for all content; keep the unpublished playlist scoped."""
    template=Path(__file__).resolve().parent.parent/'assets/unpublished-watch.html'
    if not template.exists(): template=dest/'unpublished-watch.html'
    if not template.exists(): return
    ffmpeg=shutil.which('ffmpeg') or next((str(p) for p in (root/'_tools').glob('ffmpeg*/bin/ffmpeg.exe')),None)
    cache=read(dest/'观看封面/封面缓存.json',{})
    watch=[]
    for v in view['videos']:
        row=dict(v)
        candidates=[v.get('primaryVideo')]+v.get('sources',[])
        chosen=next((p for p in candidates if p and absolute(root,p).is_file()),None)
        row['watchFile']=chosen
        row['watchKind']='成片' if chosen and chosen==v.get('primaryVideo') else '原片'
        row['watchPoster']=None
        if chosen and ffmpeg:
            p=absolute(root,chosen);stat=p.stat();stamp=[str(p),stat.st_size,stat.st_mtime_ns]
            poster=dest/'观看封面'/f'{v["id"]}.jpg'
            if not poster.exists() or cache.get(v['id'])!=stamp:
                poster.parent.mkdir(exist_ok=True)
                at=min(2,max(0,float(v.get('duration') or 0)/3))
                pending=poster.with_name(poster.stem+'.pending.jpg')
                command=[ffmpeg,'-hide_banner','-loglevel','error','-ss',str(at),'-i',str(p),
                         '-frames:v','1','-vf','scale=360:360:force_original_aspect_ratio=decrease,setsar=1','-q:v','3','-y',str(pending)]
                try:
                    result=subprocess.run(command,capture_output=True,timeout=40)
                    if result.returncode==0 and pending.exists() and pending.stat().st_size>0:
                        pending.replace(poster); cache[v['id']]=stamp
                except subprocess.TimeoutExpired: pass
            if poster.exists() and cache.get(v['id'])==stamp: row['watchPoster']=relative(root,poster)
        if v['publishStatus']=='未发布': watch.append(row)
    if cache: write(dest/'观看封面/封面缓存.json',cache)
    data={key:view.get(key) for key in ['root','generatedAt','publicationCheckedAt','publicationComplete']}
    data['videos']=watch
    html=template.read_text(encoding='utf-8').replace('/*__WATCH_DATA__*/',json.dumps(data,ensure_ascii=False).replace('<','\\u003c'))
    (dest/'未发布观看.html').write_text(html,encoding='utf-8')
    write(dest/'未发布观看数据.json',data)

def build(root,dest):
    catalog=read(dest/'内容登记.json',{'schema':'video-catalog/1','publishingScope':'unknown','videos':[]})
    files=inventory(root,catalog); new=discover(root,dest,catalog,files)
    history=read(dest/'发布记录.json',{'snapshots':[]})
    snaps=history.get('snapshots',[]); latest=snaps[-1] if snaps else {'complete':False,'events':[]}
    # Retain confirmed results from earlier reads if a subsequent read fails.
    event_map={}
    for snap in snaps:
        for e in snap['events']: event_map[(e['taskSetId'],e.get('taskId'))]=dict(e)
    for e in read(dest/'人工补充.json',{'events':[]}).get('events',[]): event_map[(e['taskSetId'],e.get('taskId'))]=dict(e)
    events=list(event_map.values())
    checked=now()
    for e in events:
        if e['status']=='定时发布' and time_dt(e.get('plannedAt')) and time_dt(e['plannedAt'])<=time_dt(checked):
            e['status']='到点待核验'
    scope_complete=latest.get('complete') and catalog.get('publishingScope')=='all-via-yixiaoer'
    videos=[]
    for source in catalog['videos']:
        v=dict(source); ev=[e for e in events if e.get('videoId')==v['id']]
        v['platforms']={}
        channels=sorted(set(PLATFORMS+[e['platform'] for e in ev]))
        for platform in channels:
            pe=[e for e in ev if e['platform']==platform]
            successes=[e for e in pe if e['status'].startswith('已发布')]
            chosen=max(successes or pe,key=lambda e:e.get('submittedAt') or e.get('checkedAt') or '',default=None)
            v['platforms'][platform]=chosen or {'status':'未发布' if scope_complete else '未查到发布记录','platform':platform}
        states=[e['status'] for e in v['platforms'].values()]
        published=sum(s.startswith('已发布') for s in states)
        if published: v['publishStatus']='三平台已发布' if all(v['platforms'][p]['status'].startswith('已发布') for p in PLATFORMS) else '部分平台已发布'
        elif any(s=='定时发布' for s in states): v['publishStatus']='定时发布'
        elif any(s=='到点待核验' for s in states): v['publishStatus']='到点待核验'
        elif any(s=='审核中' for s in states): v['publishStatus']='审核中'
        elif any(s=='发布失败' for s in states): v['publishStatus']='发布失败'
        else: v['publishStatus']='未发布' if scope_complete else '未查到发布记录'
        v['missingSources']=[s for s in v.get('sources',[]) if not absolute(root,s).is_file()]
        v['sourceStatus']='原片缺失' if v['missingSources'] else '原片在库' if v.get('sources') else '来源待确认'
        media=metadata(root,dest,v.get('primaryVideo') or next(iter(v.get('sources',[])),None))
        v.update(media)
        v['versionCount']=len({(f['name'],f['size']) for f in files if v['id'] in f['videoIds'] and f['role'] in ('交付视频','无字幕母版','试剪版本','工程视频/历史版本')})
        v['publishedFileMismatch']=any(e.get('file') and v.get('primaryVideo') and e['file']!=v['primaryVideo'] for e in ev if e['status'].startswith('已发布'))
        videos.append(v)
    unassigned=[e for e in events if not e.get('videoId')]
    summary=dict(contents=len(videos),published=sum('已发布' in v['publishStatus'] for v in videos),
                 scheduled=sum(v['publishStatus']=='定时发布' for v in videos),due=sum(v['publishStatus']=='到点待核验' for v in videos),
                 unpublished=sum(v['publishStatus']=='未发布' for v in videos),missingSources=sum(bool(v['missingSources']) for v in videos),
                 mediaFiles=len(files),failedAttempts=sum(e['status']=='发布失败' for e in events),unassignedTasks=len(unassigned))
    view=dict(schema='video-ledger/1',root=str(root),generatedAt=checked,publicationCheckedAt=latest.get('checkedAt'),watchUrl=catalog.get('watchUrl'),
              publicationComplete=scope_complete,summary=summary,videos=videos,events=events,files=files,unassignedEvents=unassigned)
    write(dest/'视频台账.json',view)
    with (dest/'视频总表.csv').open('w',encoding='utf-8-sig',newline='') as out:
        w=csv.writer(out);w.writerow(['编号','视频主题','系列','剪辑状态','发布状态','抖音','小红书','视频号','时长秒','原片','当前成片','备注'])
        for v in videos: w.writerow([v['id'],v['title'],v.get('series'),v.get('productionStatus'),v['publishStatus'],*[v['platforms'][p]['status'] for p in PLATFORMS],v.get('duration'),'; '.join(v.get('sources',[])),v.get('primaryVideo'),v.get('notes')])
    template=Path(__file__).resolve().parent.parent/'assets/publication-ledger.html'
    if not template.exists(): template=dest/'publication-ledger.html'
    html=template.read_text(encoding='utf-8')
    html=html.replace('/*__LEDGER_DATA__*/',json.dumps(view,ensure_ascii=False).replace('<','\\u003c'))
    (dest/'index.html').write_text(html,encoding='utf-8')
    watch_view(root,dest,view)
    print(json.dumps({'summary':summary,'discovered':new,'complete':scope_complete},ensure_ascii=False))
    return view

def main():
    parser=argparse.ArgumentParser(description='视频内容与发布台账；只读查询发布状态')
    parser.add_argument('--root',required=True,type=Path)
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('refresh',help='离线扫描，保留发布证据并生成网页和CSV')
    syncp=sub.add_parser('sync-yxer',help='只读查询蚁小二后刷新')
    syncp.add_argument('--import-records',type=Path,help='导入现有查询结果及同目录任务详情')
    sub.add_parser('import-local',help='导入现有本地发布状态文件作为来源映射')
    reg=sub.add_parser('register',help='新增/更新一条逻辑内容，JSON按稳定编号合并')
    reg.add_argument('--file',required=True,type=Path)
    record=sub.add_parser('record',help='登记有证据的人工补充，不触发发布')
    record.add_argument('--file',required=True,type=Path)
    args=parser.parse_args(); root=args.root.resolve(); dest=root/'发布管理'; dest.mkdir(exist_ok=True)
    if args.command=='import-local': import_local(root,dest)
    elif args.command=='sync-yxer':
        import_local(root,dest); sync(root,dest,args.import_records); build(root,dest)
    elif args.command=='refresh': build(root,dest)
    elif args.command=='register':
        row=read(args.file)
        if not row or not row.get('id') or not row.get('title'): raise ValueError('内容登记需 id 与 title')
        cat=read(dest/'内容登记.json',{'schema':'video-catalog/1','publishingScope':'unknown','videos':[]})
        old=next((v for v in cat['videos'] if v['id']==row['id']),None)
        if old: old.update(row)
        else: cat['videos'].append(row)
        backup(dest/'内容登记.json');write(dest/'内容登记.json',cat);build(root,dest)
    elif args.command=='record':
        e=read(args.file)
        required=['videoId','platform','account','status','source','checkedAt']
        if any(not e.get(k) for k in required): raise ValueError('补充记录缺少：'+', '.join(required))
        if e['status'] not in ('已发布','定时发布','发布失败','审核中','未发布','待确认'): raise ValueError('不支持该发布状态')
        if e['status']=='定时发布' and not time_dt(e.get('plannedAt')): raise ValueError('定时发布需有效 plannedAt')
        if e['status']=='已发布' and not (e.get('publishId') or e.get('url') or e.get('confirmation')): raise ValueError('已发布需作品ID、公开链接或用户确认依据')
        if not any(v['id']==e['videoId'] for v in read(dest/'内容登记.json',{'videos':[]})['videos']): raise ValueError('videoId 不在内容登记中')
        e.setdefault('taskSetId','manual-'+hashlib.sha256(json.dumps(e,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:16])
        data=read(dest/'人工补充.json',{'events':[]})
        if not any(x['taskSetId']==e['taskSetId'] for x in data['events']): data['events'].append(e)
        write(dest/'人工补充.json',data);build(root,dest)

if __name__=='__main__':
    try: main()
    except Exception as error:
        print(clean_message(error),file=sys.stderr);sys.exit(1)
