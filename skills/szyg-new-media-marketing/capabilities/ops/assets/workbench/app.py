"""Local media-operations desk. CLI reads; durable review/task records; no publishing API."""
import argparse
import base64
import hashlib
import html
import json
import mimetypes
import re
import shutil
import subprocess
import struct
import sys
import threading
import uuid
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent
try:
    SETTINGS = json.loads((BASE / 'desk-settings.json').read_text(encoding='utf-8-sig'))
except (OSError, ValueError):
    SETTINGS = {}
DATA = BASE / '数据'
TZ = timezone(timedelta(hours=8))
LOCK = threading.RLock()
JOB = {'status': 'idle', 'message': '数据快照已就绪'}
PORT = 8790
PUBLISHED_COVERS = {}

def refresh_published_covers():
    """CDN URLs are retained in memory, never in saved analytics or logs."""
    try:
        rows = pages(['query', 'content-overviews', '--platform', '抖音'])
        covers = {}
        for row in rows:
            c = row.get('contentData', {}); url = c.get('cover') or ''
            host = (urlsplit(url).hostname or '').lower()
            if url.startswith('https://') and any(host == h or host.endswith('.' + h) for h in ['douyinpic.com', 'douyincdn.com', 'byteimg.com', 'pstatp.com']):
                covers['抖音:' + str(c.get('id'))] = url
        with LOCK:
            PUBLISHED_COVERS.clear(); PUBLISHED_COVERS.update(covers)
    except Exception:
        pass

def cover_source(video_id):
    v = next((v for v in state()['videos'] if v['id'] == video_id), None)
    if not v or not v['media']: raise ValueError('没有可用的视频原文件')
    provenance = read(DATA / '封面素材/来源记录.json', {}).get(video_id, {})
    source_media = v['media']; at = min(2, max(0, float(v.get('duration') or 0) / 3))
    if provenance.get('binding') == v['media']:
        candidate = provenance.get('sourceMedia')
        if not isinstance(candidate, dict) or file_info(candidate.get('path')) != candidate:
            raise ValueError('已登记的封面来源文件发生变化，请重新核对无字幕画面')
        at = num(provenance.get('frameSeconds'))
        if at is None or at < 0: raise ValueError('封面取帧时间无效')
        source_media = candidate
    cache_stamp = v['media'] if source_media == v['media'] else {'binding': v['media'], 'sourceMedia': source_media, 'frameSeconds': at}
    cache = read(DATA / '封面素材/缓存.json', {})
    target = DATA / '封面素材' / (video_id + '.jpg')
    if not target.exists() or cache.get(video_id) != cache_stamp:
        ffmpeg = shutil.which('ffmpeg') or next((str(p) for p in (ROOT / '_tools').glob('ffmpeg*/bin/ffmpeg.exe')), None)
        if not ffmpeg: raise ValueError('封面截图工具暂不可用')
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_name(video_id + '.pending.jpg')
        proc = subprocess.run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-ss', str(at), '-i', str(ROOT / source_media['path']), '-frames:v', '1', '-vf', 'scale=1080:1920:force_original_aspect_ratio=decrease,setsar=1', '-q:v', '2', '-y', str(temp)], capture_output=True, timeout=45)
        if proc.returncode or not temp.exists() or temp.stat().st_size == 0: raise ValueError('视频截帧失败，已有封面保留')
        temp.replace(target); cache[video_id] = cache_stamp; write(DATA / '封面素材/缓存.json', cache)
    return {'source': file_info(target.relative_to(ROOT).as_posix()), 'media': v['media'], 'cover': v.get('coverDraft'), 'frameSource': {'media': source_media, 'seconds': at}}

def save_cover(payload):
    video_id = payload.get('videoId')
    v = next((v for v in state()['videos'] if v['id'] == video_id), None)
    if not v or payload.get('media') != v['media']: raise ValueError('视频版本已变化，请重新打开封面编辑')
    raw = payload.get('png', '')
    if not isinstance(raw, str) or not raw.startswith('data:image/png;base64,'): raise ValueError('封面格式必须是PNG')
    try: png = base64.b64decode(raw.split(',', 1)[1], validate=True)
    except ValueError: raise ValueError('封面文件无效')
    if len(png) > 12 * 1024 * 1024 or png[:8] != b'\x89PNG\r\n\x1a\n' or len(png) < 24 or struct.unpack('>II', png[16:24]) != (1080, 1440):
        raise ValueError('封面必须为1080×1440，且不超过12MB')
    profile = payload.get('profile') or {}
    title = str(profile.get('title') or '')[:80]
    y = num(profile.get('positionY')); text_y = num(profile.get('titleY'))
    if profile.get('fit') not in ['cover', 'contain'] or y is None or not 0 <= y <= 100 or text_y is None or not 30 <= text_y <= 85:
        raise ValueError('封面布局参数无效')
    ident = uuid.uuid4().hex[:12]; target = DATA / '发布封面' / video_id / (ident + '.png')
    target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(png)
    record = {'id': ident, 'videoId': video_id, 'createdAt': now(), 'media': v['media'], 'file': target.relative_to(ROOT).as_posix(), 'width': 1080, 'height': 1440,
        'status': '待确认发布封面', 'profile': {'title': title, 'enabled': bool(profile.get('enabled')), 'positionY': y, 'titleY': text_y, 'fit': profile['fit']}, 'source': '用户在工作台设计并导出；尚未上传或发布'}
    history = read(DATA / '发布封面记录.json', {'covers': []}); history['covers'].append(record); write(DATA / '发布封面记录.json', history)
    return record

def now(): return datetime.now(TZ).isoformat(timespec='seconds')
def read(path, default=None):
    try: return json.loads(Path(path).read_text(encoding='utf-8-sig'))
    except (OSError, ValueError): return default
def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)
def num(value):
    if value is None or value == '': return None
    try: return float(str(value).replace(',', '').replace('%', ''))
    except ValueError: return None
def cli(args):
    exe = shutil.which('yxer')
    if not exe: raise RuntimeError('未找到蚁小二 CLI，已保留原有快照')
    proc = subprocess.run([exe, *args, '--json'], capture_output=True, encoding='utf-8', errors='replace', timeout=60)
    try: obj = json.loads(proc.stdout)
    except ValueError: raise RuntimeError('蚁小二没有返回有效数据，已保留原有快照')
    if proc.returncode or not obj.get('ok'): raise RuntimeError('蚁小二查询失败，请在聊天中检查连接或授权')
    return obj['data']
def pages(args):
    result = []; total = None
    for page in range(1, 101):
        obj = cli([*args, '--page', str(page), '--size', '100'])
        rows = obj.get('data', []); result.extend(rows)
        total = obj.get('totalSize', len(result))
        if page >= obj.get('totalPage', 1):
            if len(result) < total: raise RuntimeError('蚁小二数据未完整返回，已保留原有快照')
            return result
        if not rows: break
    raise RuntimeError('数据分页未完成，已保留原有快照')
def safe_url(platform, ident):
    if platform == '抖音' and re.fullmatch(r'\d+', ident): return 'https://www.douyin.com/video/' + ident
    if platform == '小红书' and re.fullmatch(r'[a-f0-9]+', ident): return 'https://www.xiaohongshu.com/explore/' + ident
    return None
def analytics_sync():
    cli(['doctor'])
    day = datetime.now(TZ).date(); end = day - timedelta(days=1); start = end - timedelta(days=6)
    accounts = cli(['accounts', 'list', '--all'])
    platforms = list(dict.fromkeys(a['platformName'] for a in accounts))
    overview = []; works = []
    for platform in platforms:
        for row in pages(['query', 'account-overviews', '--platform', platform]):
            raw = read_string(row.get('overviewData'))
            overview.append({'id': row.get('platformAccountId'), 'name': row.get('platformAccountName'), 'platform': platform,
                'status': row.get('status'), 'worksCount': row.get('worksCount'), 'updatedAt': raw.get('updateTime'),
                'metrics': {x['key']: {'name': x['name'], 'value': num(x.get('value'))} for x in raw.get('value', {}).get('video', [])}})
        for row in pages(['query', 'content-overviews', '--platform', platform]):
            c = row.get('contentData', {}); ident = str(c.get('id') or '')
            if platform == '抖音' and c.get('cover'):
                host = (urlsplit(c['cover']).hostname or '').lower()
                if c['cover'].startswith('https://') and any(host == h or host.endswith('.' + h) for h in ['douyinpic.com', 'douyincdn.com', 'byteimg.com', 'pstatp.com']):
                    PUBLISHED_COVERS['抖音:' + ident] = c['cover']
            title = c.get('title') or (c.get('desc') or '').split('\n')[0]
            works.append({'key': platform + ':' + ident, 'id': ident, 'platform': platform, 'accountId': row.get('platformAccountId'),
                'title': title, 'publishedAt': c.get('date'), 'updatedAt': row.get('updatedAt'), 'url': safe_url(platform, ident),
                'views': num(c.get('play', c.get('read'))), 'viewLabel': '阅读' if 'read' in c and 'play' not in c else '播放',
                'likes': num(c.get('great')), 'comments': num(c.get('comment')), 'shares': num(c.get('share')),
                'saves': num(c.get('collect')), 'follows': num(c.get('addFans')), 'completion': num(c.get('finishPlay')),
                'watchSeconds': num(c.get('playTime')), 'recommendations': num(c.get('love'))})
    period = cli(['query', 'account-increments', '--start-date', str(start), '--end-date', str(end)])
    previous = read(DATA / '运营数据.json', {})
    snapshot = {'schema': 'media-analytics/1', 'fetchedAt': now(), 'range': {'start': str(start), 'end': str(end)},
        'accounts': [{'id': a['id'], 'name': a['platformAccountName'], 'platform': a['platformName'], 'fans': a.get('fansTotal'), 'status': a.get('status')} for a in accounts],
        'overviews': overview, 'works': works, 'increments': {'accounts': period.get('accounts', []), 'summary': period.get('summary', {}), 'trends': period.get('trends', [])},
        'dm': {'totals': period.get('dmMessageStats', {}).get('totals', {}), 'trend': period.get('dmMessageStats', {}).get('dailyTrend', [])},
        'complete': True, 'source': '蚁小二 CLI；作品为累计表现，增量按查询日期区间'}
    # Never store signed media URLs, authentication material, or unmanaged account fields.
    write(DATA / '快照' / (datetime.now(TZ).strftime('%Y%m%d_%H%M%S_%f') + '.json'), snapshot)
    write(DATA / '运营数据.json', snapshot)
    if previous:
        prev = {w['key']: w for w in previous.get('works', [])}
        snapshot['previousFetchedAt'] = previous.get('fetchedAt')
        for w in works:
            p = prev.get(w['key'])
            if p and w['views'] is not None and p.get('views') is not None: w['sincePreviousViews'] = w['views'] - p['views']
        write(DATA / '运营数据.json', snapshot)
    return {'accounts': len(accounts), 'works': len(works), 'fetchedAt': snapshot['fetchedAt']}
def read_string(value):
    try: return json.loads(value or '{}')
    except (TypeError, ValueError): return {}
def file_info(relative):
    if not relative: return None
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT.resolve()) or not path.is_file(): return None
    s = path.stat(); return {'path': path.relative_to(ROOT).as_posix(), 'size': s.st_size, 'modifiedNs': str(s.st_mtime_ns)}

def link_works(works, events, aliases):
    """Use exact publication IDs, or a previously verified and still matching alias."""
    for w in works:
        candidates = [e for e in events if e.get('platform') == w['platform'] and
                      str(e.get('publishId') or '') == w['id'] and e.get('status') == '已发布']
        method = '发布作品编号一致'
        if not candidates:
            caption_hash = hashlib.sha256(re.sub(r'\s+', '', html.unescape(w.get('title') or '')).encode()).hexdigest()
            for alias in aliases:
                if (alias.get('platform'), alias.get('workId'), alias.get('accountId'), alias.get('captionHash')) != (
                        w['platform'], w['id'], w.get('accountId'), caption_hash):
                    continue
                candidates.extend(e for e in events if e.get('videoId') == alias.get('videoId') and
                    e.get('platform') == w['platform'] and e.get('publishId') == alias.get('publishId') and
                    e.get('taskId') == alias.get('taskId') and e.get('status') == '已发布')
                method = alias['method']
        # A conflicting ID must not silently attach another video's metrics.
        event = candidates[0] if len({e.get('videoId') for e in candidates}) == 1 else None
        w.update(localId=event.get('videoId') if event else None,
                 publishedFile=event.get('file') if event else None,
                 publicationId=event.get('publishId') if event else None,
                 matchMethod=method if event else None)

def receipt_metrics(event):
    """Read the canonical query-details evidence without adding duplicate account works."""
    if event.get('status') != '已发布' or not event.get('source'): return None
    path = (ROOT / event['source']).resolve()
    if not path.is_relative_to(ROOT.resolve()): return None
    obj = read(path, {})
    tasks = obj.get('data', {}).get('tasks', [])
    task = next((t for t in tasks if t.get('id') == event.get('taskId') and
        t.get('publishId') == event.get('publishId') and t.get('platformName') == event.get('platform')), None)
    statistic = task.get('statistic') if task else None
    if not isinstance(statistic, dict): return None
    fields = {'views': 'viewCount', 'likes': 'greatCount', 'comments': 'commentCount',
              'shares': 'shareCount', 'saves': 'collectCount'}
    values = {k: num(statistic.get(source)) for k, source in fields.items()}
    if all(x is None for x in values.values()): return None
    return {**values, 'follows': None, 'completion': None, 'watchSeconds': None, 'recommendations': None,
        'key': event['platform'] + ':receipt:' + str(event.get('publishId')), 'id': event.get('publishId'),
        'publicationId': event.get('publishId'), 'platform': event['platform'], 'localId': event['videoId'],
        'title': event.get('title'), 'publishedFile': event.get('file'), 'url': event.get('url'),
        'viewLabel': '阅读' if event['platform'] == '小红书' else '播放',
        'updatedAt': event.get('checkedAt'), 'source': event['source'], 'matchMethod': '发布任务回执直接返回'}
def current_transcript(video_id, media, records):
    if not media: return None
    record = next((r for r in reversed(records) if r.get('videoId') == video_id and r.get('media') == media), None)
    if not record: return None
    source = record.get('source', {})
    stamp = {k: source.get(k) for k in ['path', 'size', 'modifiedNs']}
    if file_info(source.get('path')) != stamp:
        return {'status': '字幕或转写已更新，请刷新对应逐字稿'}
    if any(not file_info(p) for p in record.get('files', {}).values()):
        return {'status': '逐字稿文件缺失，请重新导出'}
    data = read(ROOT / record['files']['json'], {})
    if data.get('media') != media or data.get('recordId') != record['recordId']: return None
    return {**record, 'segments': data.get('segments', []), 'status': 'available'}

def state():
    ledger = read(ROOT / '发布管理/视频台账.json', {})
    catalog = read(ROOT / '发布管理/内容登记.json', {})
    analytics = read(DATA / '运营数据.json', {})
    journal = read(DATA / '工作记录.json', {'tasks': [], 'reviews': [], 'leads': []})
    review_data = read(ROOT / SETTINGS.get('reviewData', '发布管理/剪辑复核.json'), {})
    scripts = {v['id']: v for v in review_data.get('items', [])}
    poster_cache = read(ROOT / '发布管理/观看封面/封面缓存.json', {})
    cover_history = read(DATA / '发布封面记录.json', {'covers': []})
    transcript_records = read(ROOT / '逐字稿/登记.json', {'records': []}).get('records', [])
    persistent = {v['id']: v for v in catalog.get('videos', [])}
    events = ledger.get('events', [])
    link_works(analytics.get('works', []), events, read(DATA / '作品关联.json', {}).get('links', []))
    for w in analytics.get('works', []):
        w['coverUrl'] = PUBLISHED_COVERS.get(w['key'])
    videos = []
    for old in ledger.get('videos', []):
        v = {**old, **persistent.get(old['id'], {})}
        media = file_info(v.get('primaryVideo')) or next((f for p in v.get('sources', []) if (f := file_info(p))), None)
        v['media'] = media; v['kind'] = '成片' if file_info(v.get('primaryVideo')) else '原片'
        v['transcript'] = current_transcript(v['id'], media, transcript_records)
        stamp = [str((ROOT / media['path']).resolve()), media['size'], int(media['modifiedNs'])] if media else None
        v['poster'] = file_info('发布管理/观看封面/' + v['id'] + '.jpg') if stamp and poster_cache.get(v['id']) == stamp else None
        accepted = [r for r in journal.get('reviews', []) if r['videoId'] == v['id'] and r.get('media') == media and r['status'] == 'approved']
        v['reviewed'] = bool(accepted)
        v['events'] = [e for e in events if e.get('videoId') == v['id']]
        v['metrics'] = [w for w in analytics.get('works', []) if w.get('localId') == v['id']]
        v['platformPerformance'] = []
        for platform in ['抖音', '视频号', '小红书']:
            event = v.get('platforms', {}).get(platform, {'status': '未查到发布记录'})
            matching = [w for w in v['metrics'] if w['platform'] == platform and
                        w.get('publicationId') == event.get('publishId')]
            metric = matching[0] if len(matching) == 1 else receipt_metrics(event)
            if metric and not matching: v['metrics'].append(metric)
            v['platformPerformance'].append({'platform': platform, 'status': event['status'], 'metric': metric,
                'plannedAt': event.get('plannedAt'), 'checkedAt': event.get('checkedAt'),
                'publishedFile': event.get('file'), 'error': event.get('error')})
        own_covers = [c for c in cover_history['covers'] if c['videoId'] == v['id'] and c['media'] == media and file_info(c['file'])]
        v['coverDraft'] = own_covers[-1] if own_covers else None
        v['publishedCover'] = next(({'url': w['coverUrl'], 'id': w['id'], 'views': w['views'], 'title': w['title']} for w in v['metrics'] if w['platform'] == '抖音' and w.get('coverUrl')), None)
        v['cues'] = scripts.get(v['id'], {}).get('cues', [])
        v['cards'] = scripts.get(v['id'], {}).get('cards', [])
        if v['kind'] == '原片': v['stage'] = '原片待确认'
        elif '三平台已发布' in v.get('publishStatus', ''): v['stage'] = '已发布'
        elif '已发布' in v.get('publishStatus', '') or any(x in v.get('publishStatus', '') for x in ['审核', '定时', '核验', '发布中']): v['stage'] = '发布跟进'
        elif v['reviewed']: v['stage'] = '待排期'
        else: v['stage'] = '成片待审'
        videos.append(v)
    ideas = read(ROOT / SETTINGS.get('ideas', '内容策划/选题库.json'), {})
    assets = read(ROOT / '素材库/管理/素材登记.json', {})
    return {'now': now(), 'ledger': {k: ledger.get(k) for k in ['generatedAt', 'publicationCheckedAt', 'publicationComplete', 'summary']},
        'settings': {'name': SETTINGS.get('name', '我的内容团队'), 'shootingPage': SETTINGS.get('shootingPage', '内容策划/拍摄主页.html')}, 'videos': videos, 'analytics': analytics, 'journal': journal, 'job': JOB.copy(), 'ideas': ideas.get('items', []),
        'assets': [{k: a.get(k) for k in ['id', 'title', 'category', 'tags', 'purpose', 'rights', 'usageCount']} for a in assets.get('assets', [])]}
def add_record(payload):
    journal = read(DATA / '工作记录.json', {'tasks': [], 'reviews': [], 'leads': []})
    action = payload.get('action'); valid = state(); ids = {v['id']: v for v in valid['videos']}
    ident = payload.get('videoId'); video = ids.get(ident)
    if ident and not video: raise ValueError('内容编号不存在')
    record = {'id': uuid.uuid4().hex[:12], 'createdAt': now()}
    if action in ['revision', 'approve']:
        if not video or not video['media']: raise ValueError('当前视频不可用')
        if payload.get('media') != video['media']: raise ValueError('视频版本已变化，请刷新后重新审阅')
        record.update(videoId=ident, media=video['media'], title=video['title'])
        if action == 'approve':
            record.update(status='approved', note='用户确认采用当前版本；逐字听校状态仍以工程记录为准')
            journal['reviews'].append(record)
        else:
            text = str(payload.get('text') or '').strip()[:4000]
            if not text: raise ValueError('请写下修改要求')
            seconds = num(payload.get('seconds'))
            if seconds is None or seconds < 0 or seconds > (video.get('duration') or 20000) + 1: raise ValueError('时间位置无效')
            record.update(type='修改视频', status='待执行', seconds=seconds, text=text, projectDirs=video.get('projectDirs', []))
            journal['tasks'].append(record)
    elif action == 'task':
        text = str(payload.get('text') or '').strip()[:6000]
        if not text: raise ValueError('请写下任务')
        record.update(type=str(payload.get('type') or '运营任务')[:40], status='待执行', text=text, videoId=ident)
        journal['tasks'].append(record)
    elif action == 'leads':
        count = num(payload.get('count'))
        if count is None or count < 0 or count != int(count) or count > 100000: raise ValueError('请填写有效咨询人数')
        record.update(videoId=ident, count=int(count), platform=payload.get('platform'), note=str(payload.get('text') or '')[:1000], source='用户人工登记')
        journal['leads'].append(record)
    elif action == 'cancel':
        target = next((t for t in journal['tasks'] if t['id'] == payload.get('id')), None)
        if not target or target['status'] != '待执行': raise ValueError('该任务不能撤回')
        target.update(status='已撤回', canceledAt=now()); record = target
    else: raise ValueError('不支持该操作')
    write(DATA / '工作记录.json', journal)
    return record
def refresh_worker():
    global JOB
    try:
        JOB.update(status='running', message='正在查询发布回执并刷新台账…', startedAt=now())
        # Existing entry protects Excel edits and keeps all canonical ledgers synchronized.
        ops_script = SETTINGS.get('opsScript')
        if not ops_script or not Path(ops_script).is_file(): raise RuntimeError('未找到本Skill的同步入口，请重新执行 init')
        result = subprocess.run([sys.executable, '-X', 'utf8', ops_script, 'sync', '--root', str(ROOT)], capture_output=True, timeout=600)
        if result.returncode: raise RuntimeError('同步未完成，请让AI助手检查CLI连接、授权或台账问题；已有数据保留。')
        JOB.update(message='正在读取接入账号的作品与近七天表现…')
        snapshot = read(DATA / '运营数据.json', {})
        summary = {'accounts': len(snapshot.get('accounts', [])), 'works': len(snapshot.get('works', []))}
        JOB.update(status='done', message=f"已同步 {summary['accounts']} 个账号、{summary['works']} 条平台作品", finishedAt=now())
    except Exception as error:
        JOB.update(status='error', message=str(error), finishedAt=now())
    with LOCK: write(DATA / '最近同步.json', JOB)
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def send_json(self, obj, status=200):
        data = json.dumps(obj, ensure_ascii=False).encode('utf-8'); self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8'); self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store'); self.end_headers(); self.wfile.write(data)
    def do_HEAD(self): self.serve(False)
    def do_GET(self): self.serve(True)
    def do_POST(self):
        # Loopback-only service, with same-origin protection for all durable writes.
        if self.headers.get('Host') not in [f'127.0.0.1:{PORT}', f'localhost:{PORT}']:
            self.send_json({'error': '来源无效'}, 403); return
        origin = self.headers.get('Origin')
        if origin and origin not in [f'http://127.0.0.1:{PORT}', f'http://localhost:{PORT}']:
            self.send_json({'error': '来源无效'}, 403); return
        if self.headers.get('X-Workbench') != '1': self.send_json({'error': '请从工作台操作'}, 403); return
        route = urlsplit(self.path).path
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if size < 0 or size > (18 * 1024 * 1024 if route == '/api/cover-save' else 24000): raise ValueError('请求过大')
            payload = json.loads(self.rfile.read(size) or '{}')
            with LOCK:
                if route == '/api/record': self.send_json({'ok': True, 'record': add_record(payload)})
                elif route == '/api/cover-source': self.send_json({'ok': True, **cover_source(payload.get('videoId'))})
                elif route == '/api/cover-save': self.send_json({'ok': True, 'record': save_cover(payload)})
                elif route == '/api/refresh':
                    if JOB['status'] != 'running':
                        JOB.update(status='running', message='开始同步…')
                        threading.Thread(target=refresh_worker, daemon=True).start()
                    self.send_json({'ok': True, 'job': JOB})
                else: self.send_json({'error': '没有这个接口'}, 404)
        except (ValueError, TypeError) as error: self.send_json({'error': str(error)}, 400)
    def serve(self, body):
        route = unquote(urlsplit(self.path).path)
        if self.headers.get('Host') not in [f'127.0.0.1:{PORT}', f'localhost:{PORT}']:
            self.send_json({'error': '来源无效'}, 403); return
        if route == '/health': self.send_json({'app': 'media-operations-workbench', 'publishingEnabled': False, 'workspace': str(ROOT)}); return
        if route == '/api/state':
            with LOCK: self.send_json(state())
            return
        if route == '/api/job': self.send_json(JOB); return
        if route == '/api/export':
            with LOCK: self.send_json(read(DATA / '工作记录.json', {'tasks': [], 'reviews': [], 'leads': []}))
            return
        if route in ['/', '/index.html', '/style.css', '/app.js', '/cover-editor.js']:
            path = BASE / ('index.html' if route == '/' else route.lstrip('/'))
        elif route.startswith('/files/'):
            path = (ROOT / route[7:]).resolve()
            if not path.is_relative_to(ROOT.resolve()): self.send_error(404); return
            model = state(); exact = set(); folders = set()
            exact.add((ROOT / '逐字稿/index.html').resolve())
            for transcript in read(ROOT / '逐字稿/登记.json', {'records': []}).get('records', []):
                for filename in transcript.get('files', {}).values():
                    exact.add((ROOT / filename).resolve())
            for cover in read(DATA / '发布封面记录.json', {'covers': []})['covers']:
                exact.add((ROOT / cover['file']).resolve())
            for asset in read(ROOT / '素材库/管理/素材登记.json', {'assets': []}).get('assets', []):
                if asset.get('relativePath'): exact.add((ROOT / '素材库' / asset['relativePath']).resolve())
            exact.add((ROOT / '素材库/catalog.js').resolve())
            exact.add((ROOT / '内容策划/选题库.js').resolve())
            for v in model['videos']:
                exact.add((DATA / '封面素材' / (v['id'] + '.jpg')).resolve())
            for p in ['00-视频库入口.html', '发布管理/index.html', '发布管理/未发布观看.html', '发布管理/视频发布台账.xlsx', '素材库/index.html', SETTINGS.get('shootingPage', '内容策划/拍摄主页.html')]:
                exact.add((ROOT / p).resolve())
            folders.add((ROOT / '素材库').resolve())
            # Only the configured shooting page and explicit preview folders are served.
            for asset in read(ROOT / '素材库/管理/素材登记.json', {'assets': []}).get('assets', []):
                if asset.get('relativePath'): exact.add((ROOT / '素材库' / asset['relativePath']).resolve())
            exact.add((ROOT / '素材库/catalog.js').resolve())
            exact.add((ROOT / '内容策划/选题库.js').resolve())
            for v in model['videos']:
                for p in [v.get('primaryVideo'), *v.get('sources', []), v.get('preview')]:
                    if p: exact.add((ROOT / p).resolve())
                exact.add((ROOT / '发布管理/观看封面' / (v['id'] + '.jpg')).resolve())
                if v.get('preview'): folders.add((ROOT / v['preview']).resolve().parent)
            suffixes = {'.html', '.css', '.js', '.jpg', '.jpeg', '.png', '.svg', '.srt', '.ass', '.vtt', '.txt', '.mp4', '.webm', '.mov', '.json', '.woff2'}
            if path not in exact and not (path.suffix.lower() in suffixes and any(path.is_relative_to(f) for f in folders)):
                self.send_error(404); return
        else: self.send_error(404); return
        if not path.is_file(): self.send_error(404); return
        size = path.stat().st_size; start = 0; end = size - 1; status = 200
        value = self.headers.get('Range')
        if value:
            match = re.fullmatch(r'bytes=(\d*)-(\d*)', value)
            if not match or not any(match.groups()): self.send_error(416); return
            a, b = match.groups()
            if a: start = int(a); end = min(int(b), size-1) if b else size-1
            else: start = max(0, size-int(b))
            if start >= size or start > end:
                self.send_response(416); self.send_header('Content-Range', f'bytes */{size}'); self.end_headers(); return
            status = 206
        length = end-start+1; self.send_response(status)
        mime = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
        if mime.startswith('text/') or mime == 'application/json': mime += '; charset=utf-8'
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(length)); self.send_header('Accept-Ranges', 'bytes'); self.send_header('Cache-Control', 'no-store')
        if status == 206: self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        self.end_headers()
        if body:
            try:
                with path.open('rb') as source:
                    source.seek(start); remaining = length
                    while remaining:
                        chunk = source.read(min(262144, remaining))
                        if not chunk: break
                        self.wfile.write(chunk); remaining -= len(chunk)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError): pass
if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--port', type=int, default=8790); parser.add_argument('--sync', action='store_true'); args = parser.parse_args()
    DATA.mkdir(exist_ok=True)
    if args.sync: print(json.dumps(analytics_sync(), ensure_ascii=False))
    else:
        PORT = args.port; JOB.update(read(DATA / '最近同步.json', {}))
        if JOB['status'] == 'running': JOB.update(status='idle', message='上次同步已中断，可重新同步')
        print(f'Local: http://127.0.0.1:{PORT}', flush=True)
        if read(DATA / '运营数据.json', {}).get('accounts'):
            threading.Thread(target=refresh_published_covers, daemon=True).start()
        ThreadingHTTPServer(('127.0.0.1', PORT), Handler).serve_forever()
