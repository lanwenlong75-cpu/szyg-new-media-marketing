#!/usr/bin/env python3
"""Portable local workspace and read-only data tools. Publishing stays in official yxer."""
import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import uuid
import webbrowser
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import urlopen
from xml.sax.saxutils import escape

SKILL = Path(__file__).resolve().parents[1]
TZ = timezone(timedelta(hours=8))
def now(): return datetime.now(TZ).isoformat(timespec='seconds')
def read(path, default=None):
    if not Path(path).is_file(): return default
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def write(path, data, only_new=False):
    path = Path(path)
    if only_new and path.exists(): return
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex[:8] + '.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)
def digest(path):
    with Path(path).open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest() if hasattr(hashlib, 'file_digest') else hashlib.sha256(f.read()).hexdigest()
def config(root): return read(root / '数字员工配置.json', {})
def environment(root):
    env = os.environ.copy(); dirs = []
    for name, value in config(root).get('tools', {}).items():
        if value and Path(value).is_file():
            dirs.append(str(Path(value).parent))
            if name == 'chrome': env['CHROME'] = value
    tools = root / '_tools'
    if tools.is_dir(): dirs.extend(str(p) for p in tools.glob('ffmpeg*/bin') if p.is_dir())
    runtime = Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies'
    if (runtime / 'node/bin').is_dir(): dirs.append(str(runtime / 'node/bin'))
    env['PATH'] = os.pathsep.join([*dirs, env.get('PATH', '')])
    env.update(PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
    return env
def activate(root): os.environ.update(environment(root))
def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result); return result
def ledger(): return module(SKILL / 'scripts/publication_ledger.py', 'media_ledger')
def desk(root): return module(root / '运营工作台/app.py', 'media_desk')
def init(root, name='我的内容团队', port=8790):
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    for folder in ['待剪素材', '剪辑项目', '成片交付', '内容策划', '发布管理', '素材库/管理', '运营工作台/数据']:
        (root / folder).mkdir(parents=True, exist_ok=True)
    cfg = config(root)
    cfg.setdefault('schema', 'szyg-new-media-ops/1'); cfg.setdefault('name', name); cfg.setdefault('port', port)
    cfg.setdefault('publishingScope', 'unknown'); cfg.setdefault('tools', {})
    cfg['skillPath'] = str(SKILL); write(root / '数字员工配置.json', cfg)
    for source in (SKILL / 'assets/workbench').iterdir():
        target = root / '运营工作台' / source.name
        if source.is_file() and not target.exists(): shutil.copy2(source, target)
    for source in (SKILL / 'assets/workspace').rglob('*'):
        if source.is_file():
            target = root / source.relative_to(SKILL / 'assets/workspace')
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists(): shutil.copy2(source, target)
    write(root / '运营工作台/desk-settings.json', {'name': cfg['name'], 'opsScript': str(SKILL / 'scripts/ops.py'),
        'ideas': '内容策划/选题库.json', 'reviewData': '发布管理/剪辑复核.json',
        'shootingPage': '内容策划/拍摄主页.html'}, only_new=True)
    defaults = {
        '发布管理/内容登记.json': {'schema': 'video-catalog/1', 'publishingScope': cfg['publishingScope'], 'videos': []},
        '发布管理/任务来源.json': {}, '发布管理/发布记录.json': {'schema': 'publication-events/1', 'snapshots': []},
        '发布管理/人工补充.json': {'events': []}, '内容策划/选题库.json': {'items': []},
        '素材库/管理/素材登记.json': {'assets': []}, '运营工作台/数据/工作记录.json': {'tasks': [], 'reviews': [], 'leads': []},
        '运营工作台/数据/发布封面记录.json': {'covers': []}, '运营工作台/数据/作品关联.json': {'links': []},
        '运营工作台/数据/运营数据.json': {'schema': 'media-analytics/1', 'fetchedAt': None, 'accounts': [],
            'works': [], 'overviews': [], 'increments': {'summary': {}, 'accounts': [], 'trends': []},
            'range': {}, 'dm': {}, 'complete': False, 'source': '尚未连接账号；无示例指标'},
    }
    for path, data in defaults.items(): write(root / path, data, only_new=True)
    guide = root / '数字员工使用说明.txt'
    if not guide.exists(): guide.write_text('在支持本地文件和命令的AI助手中调用 $szyg-new-media-ops。\n给出原片或已有工程，即可接手剪辑、封面、发布准备和数据复盘。\n工作台任务保存到本机，交给AI执行后才更新为完成。\n接入自己的蚁小二账号后点同步；初始没有示例账号或假数据。\n', encoding='utf-8')
    activate(root)
    library = module(SKILL / 'scripts/materials.py', 'materials').Library(root / '素材库')
    library.save(library.read(), backup=False)
    view = index(root)
    return {'workspace': str(root), 'contents': len(view['videos']), 'preservedExistingFiles': True, 'port': cfg['port']}

def export_excel(root, view):
    """Dependency-free .xlsx, preserving an existing workbook with user edits."""
    dest = root / '发布管理'; path = dest / '视频发布台账.xlsx'; stamp_path = dest / 'Excel生成摘要.json'
    previous = read(stamp_path, {})
    if path.exists() and (not previous or digest(path) != previous.get('sha256')):
        return {'excel': '保留已有或人工修改的Excel；需先按编号回填登记', 'path': str(path)}
    headings = ['编号', '主题', '系列', '剪辑状态', '发布状态', '抖音', '视频号', '小红书', '时长秒', '原片', '当前成片', '备注']
    rows = [headings] + [[v['id'], v['title'], v.get('series'), v.get('productionStatus'), v.get('publishStatus'),
        *[v['platforms'][p]['status'] for p in ['抖音', '视频号', '小红书']], v.get('duration'),
        '\n'.join(v.get('sources', [])), v.get('primaryVideo'), v.get('notes')] for v in view['videos']]
    cells = []
    for index_row, row in enumerate(rows, 1):
        text = ''.join(f'<c r="{chr(65+i)}{index_row}" t="inlineStr"><is><t xml:space="preserve">{escape(str(x if x is not None else ""))}</t></is></c>' for i,x in enumerate(row))
        cells.append(f'<row r="{index_row}">{text}</row>')
    ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    content = f'<worksheet xmlns="{ns}"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols><col min="1" max="1" width="12" customWidth="1"/><col min="2" max="12" width="26" customWidth="1"/></cols><sheetData>{"".join(cells)}</sheetData><autoFilter ref="A1:L{len(rows)}"/></worksheet>'
    entries = {
        '[Content_Types].xml': '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>',
        '_rels/.rels': '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        'xl/workbook.xml': f'<workbook xmlns="{ns}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="视频发布台账" sheetId="1" r:id="rId1"/></sheets></workbook>',
        'xl/_rels/workbook.xml.rels': '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
        'xl/worksheets/sheet1.xml': content,
    }
    tmp = path.with_suffix('.pending.xlsx')
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as z:
        for key, text in entries.items(): z.writestr(key, '<?xml version="1.0" encoding="UTF-8"?>' + text)
    tmp.replace(path); write(stamp_path, {'sha256': digest(path), 'generatedAt': now()})
    return {'excel': '已生成', 'path': str(path)}
def index(root):
    root = root.resolve()
    transcript_result = module(SKILL / 'scripts/transcripts.py', 'media_transcripts').sync(root)
    activate(root); view = ledger().build(root, root / '发布管理')
    topics = read(root/'内容策划/选题库.json', {'items': []})
    (root/'内容策划/选题库.js').write_text('window.SHOOTING_TOPICS='+json.dumps(topics,ensure_ascii=False).replace('<','\\u003c')+';\n',encoding='utf-8')
    view['excelResult'] = export_excel(root, view); view['transcriptResult'] = transcript_result; return view

def register(root, path, title, kind, ident=None):
    root = root.resolve()
    path = path.resolve()
    if not path.is_file() or path.suffix.lower() not in {'.mp4', '.mov', '.mkv', '.webm', '.m4v', '.avi'}: raise ValueError('需要真实视频文件')
    cat_path = root / '发布管理/内容登记.json'; cat = read(cat_path)
    if cat is None: raise ValueError('先运行 init')
    if not ident:
        numbers = [int(v['id'][2:]) for v in cat['videos'] if re.fullmatch(r'V-\d+', v['id'])]
        ident = f'V-{max(numbers, default=0)+1:03d}'
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', ident): raise ValueError('内容编号只允许字母、数字、横线、下划线')
    row = next((v for v in cat['videos'] if v['id'] == ident), None)
    if row is None: row = {'id': ident, 'title': title or path.stem, 'series': '', 'sources': [], 'primaryVideo': None,
        'projectDirs': [], 'deliveryDirs': [], 'publishTitles': [], 'productionStatus': '待剪辑', 'notes': '', 'registeredAt': now()}; cat['videos'].append(row)
    if title: row['title'] = title
    if not path.is_relative_to(root):
        folder = root / ('待剪素材' if kind == 'source' else '成片交付') / ident; folder.mkdir(parents=True, exist_ok=True)
        target = folder / path.name
        if target.exists() and digest(target) != digest(path): target = folder / (path.stem + '_' + digest(path)[:8] + path.suffix)
        if not target.exists(): shutil.copy2(path, target)
        path = target
    rel = path.relative_to(root).as_posix()
    if kind == 'source':
        if rel not in row['sources']: row['sources'].append(rel)
    else: row['primaryVideo'] = rel; row['productionStatus'] = '成片待审'
    ledger().backup(cat_path); write(cat_path, cat); index(root)
    return {'id': ident, 'file': rel, 'kind': kind, 'sourcePreserved': True}

def task_binding(root, path):
    incoming = read(path, {})
    row = {k: incoming[k] for k in ['videoId', 'taskSetId', 'file', 'platform', 'account', 'accountId', 'plannedAt', 'sha256', 'source'] if k in incoming}
    required = ['videoId', 'taskSetId', 'file']
    if any(not row.get(k) for k in required): raise ValueError('发布来源需 videoId、taskSetId、file')
    if not any(v['id'] == row['videoId'] for v in read(root / '发布管理/内容登记.json', {'videos': []})['videos']): raise ValueError('内容编号不存在')
    media = (root / row['file']).resolve()
    if not media.is_relative_to(root) or not media.is_file(): raise ValueError('提交的视频文件不在工作区或已缺失')
    row['file'] = media.relative_to(root).as_posix(); actual = digest(media)
    if row.get('sha256') and row['sha256'] != actual: raise ValueError('提交视频已变化，请核对原提交版本')
    row['sha256'] = actual
    data = read(root / '发布管理/任务来源.json', {}); old = data.get(row['taskSetId'])
    if old and (old.get('videoId'), old.get('file')) != (row['videoId'], row['file']): raise ValueError('同一发布任务存在绑定冲突')
    data[row['taskSetId']] = row; write(root / '发布管理/任务来源.json', data)
    return {'registered': row['taskSetId'], 'status': '来源已登记；发布结果以查询回执为准'}

def doctor(root, online=False):
    activate(root)
    tools = {name: shutil.which(name) for name in ['node', 'npm', 'ffmpeg', 'ffprobe', 'yxer']}
    chrome_candidates = [os.environ.get('CHROME'), shutil.which('google-chrome'), shutil.which('chromium'),
        str(Path(os.environ.get('PROGRAMFILES', '')) / 'Google/Chrome/Application/chrome.exe'),
        '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome']
    browser = next((p for p in chrome_candidates if p and Path(p).is_file()), None)
    tools['chrome'] = browser
    editing = SKILL.parent / 'motion'
    ready = {'workbench': sys.version_info >= (3,10), 'covers': bool(tools['ffmpeg'] and tools['ffprobe']),
        'motionRuntime': bool(tools['node'] and browser and (editing/'node_modules/playwright-core').is_dir()),
        'publishingCLI': bool(tools['yxer'])}
    result = {'schema': 'ops-doctor/1', 'workspace': str(root), 'python': sys.version.split()[0],
        'tools': tools, 'ready': ready, 'accountConnection': '未执行在线自检',
        'next': ['缺少剪辑运行依赖时执行 bootstrap --editing', '缺少yxer时执行 bootstrap --publishing', 'API Key只配置到自己的蚁小二CLI，不写入本Skill或工作区']}
    if online:
        obj = desk(root).cli(['doctor'])
        result['accountConnection'] = '在线自检通过'
        result['officialSkillNotice'] = bool(obj.get('_notice'))
    return result

def npm_args():
    npm = shutil.which('npm'); node = shutil.which('node')
    if not npm or not node: raise ValueError('请安装Node.js 18+（含npm），再重试')
    if os.name != 'nt': return [npm]
    folder = Path(npm).parent
    cli = next((p for p in [folder/'node_modules/npm/bin/npm-cli.js', folder.parent/'lib/node_modules/npm/bin/npm-cli.js'] if p.is_file()), None)
    if not cli: raise ValueError('找不到npm JS入口，请使用标准Node.js安装')
    return [node, str(cli)]
def bootstrap(root, editing=False, publishing=False):
    activate(root); commands = []
    if editing: commands.append([sys.executable, '-X', 'utf8', str(SKILL.parent/'motion/scripts/pipeline.py'), 'setup'])
    if publishing:
        if not shutil.which('yxer'): commands.append([*npm_args(), 'install', '-g', '@yixiaoermail/cli@3.2.26'])
    for command in commands:
        result = subprocess.run(command, env=environment(root))
        if result.returncode: raise RuntimeError('依赖安装未完成；保留当前工作区，按错误修复后继续')
    if publishing:
        exe = shutil.which('yxer')
        if not exe: raise ValueError('CLI已安装，但当前PATH未找到yxer；刷新终端后执行 yxer skill sync --global')
        proc = subprocess.run([exe, 'skill', 'sync', '--global', '--json'], capture_output=True, timeout=120, env=environment(root))
        if proc.returncode: raise RuntimeError('官方Skill同步未完成，请运行 yxer skill sync --global')
    return {'dependencySetupFinished': True, 'credentials': '请在自己的CLI中完成账号配置；未在技能包保存凭据'}

def sync(root):
    activate(root); d = desk(root); d.cli(['doctor'])
    l = ledger(); l.import_local(root, root / '发布管理'); l.sync(root, root / '发布管理')
    index(root); return d.analytics_sync()

def start(root, port=None, open_browser=False):
    root = root.resolve()
    cfg = config(root)
    if not cfg or not (root/'运营工作台/app.py').is_file(): raise ValueError('请先运行 init')
    port = port or cfg.get('port', 8790); url = f'http://127.0.0.1:{port}/'
    try:
        health = json.load(urlopen(url+'health', timeout=1))
        if health.get('app') != 'media-operations-workbench' or health.get('workspace') != str(root):
            raise ValueError('端口已有其他工作台，请用 --port 指定空闲端口；未停止现有服务')
        if open_browser: webbrowser.open(url)
        return {'url': url, 'reused': True}
    except (OSError, TimeoutError): pass
    with socket.socket() as sock:
        if sock.connect_ex(('127.0.0.1', port)) == 0: raise ValueError('端口已占用，请指定其他端口')
    logs = root / '运营工作台/data-logs'; logs.mkdir(exist_ok=True)
    options = {'env': environment(root), 'cwd': str(root), 'stdin': subprocess.DEVNULL}
    if os.name == 'nt': options['creationflags'] = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
    else: options['start_new_session'] = True
    with (logs/'server.stdout.log').open('ab') as out, (logs/'server.stderr.log').open('ab') as err:
        proc = subprocess.Popen([sys.executable, '-X', 'utf8', str(root/'运营工作台/app.py'), '--port', str(port)], stdout=out, stderr=err, **options)
    write(root/'运营工作台/进程.json', {'pid': proc.pid, 'workspace': str(root), 'port': port, 'startedAt': now()})
    for _ in range(40):
        if proc.poll() is not None: raise RuntimeError('工作台启动失败，请查看本机data-logs/server.stderr.log')
        try:
            health = json.load(urlopen(url+'health', timeout=1))
            if health.get('workspace') == str(root):
                if open_browser: webbrowser.open(url)
                return {'url': url, 'pid': proc.pid, 'reused': False}
        except OSError: pass
        time.sleep(.25)
    raise RuntimeError('工作台未就绪，检查本机日志后继续；没有重跑或终止其他服务')

def update_task(root, ident, status, result, outputs):
    path = root/'运营工作台/数据/工作记录.json'; journal = read(path, {'tasks': [], 'reviews': [], 'leads': []})
    task = next((t for t in journal['tasks'] if t['id'] == ident), None)
    if task is None: raise ValueError('任务编号不存在')
    transitions = {'待执行': {'进行中','已撤回'}, '进行中': {'待审阅','已完成','待执行'}, '待审阅': {'进行中','已完成'}}
    if status not in transitions.get(task['status'], set()): raise ValueError('任务状态不能这样转换')
    if status in ['待审阅','已完成'] and (not result or not outputs): raise ValueError('交付需实际产物和结果说明')
    for value in outputs:
        file = (root/value).resolve()
        if not file.is_relative_to(root) or not file.is_file(): raise ValueError('产物路径无效或文件不存在')
    task.update(status=status, updatedAt=now())
    if result: task['result'] = result
    if outputs: task['outputs'] = outputs
    if status == '已完成': task['completedAt'] = now()
    write(path, journal); return task

def main():
    p = argparse.ArgumentParser(description='新媒体运营数字员工：初始化、登记、工作台、只读同步与交接')
    sub = p.add_subparsers(dest='command', required=True)
    parsers = {}
    for name in ['init','doctor','index','register','bind-publication','bootstrap','sync','start','task-status','materials']:
        x = sub.add_parser(name); x.add_argument('--root', type=Path, default=Path.cwd()); parsers[name]=x
    parsers['init'].add_argument('--name', default='我的内容团队'); parsers['init'].add_argument('--port', type=int, default=8790)
    parsers['doctor'].add_argument('--online', action='store_true')
    x=parsers['register']; x.add_argument('--media', required=True, type=Path); x.add_argument('--title'); x.add_argument('--id'); x.add_argument('--kind', choices=['source','master'], default='source')
    parsers['bind-publication'].add_argument('--file', required=True, type=Path)
    parsers['bootstrap'].add_argument('--editing', action='store_true'); parsers['bootstrap'].add_argument('--publishing', action='store_true')
    parsers['start'].add_argument('--port', type=int); parsers['start'].add_argument('--open', action='store_true')
    parsers['materials'].add_argument('args', nargs=argparse.REMAINDER)
    x=parsers['task-status']; x.add_argument('--id',required=True); x.add_argument('--status',required=True,choices=['进行中','待审阅','已完成','待执行','已撤回']); x.add_argument('--result',default=''); x.add_argument('--output',action='append',default=[])
    a=p.parse_args(); root=a.root.resolve()
    if a.command=='init': result=init(root,a.name,a.port)
    elif a.command=='doctor': result=doctor(root,a.online)
    elif a.command=='index': result=index(root)['summary']
    elif a.command=='register': result=register(root,a.media,a.title,a.kind,a.id)
    elif a.command=='bind-publication': result=task_binding(root,a.file)
    elif a.command=='bootstrap': result=bootstrap(root,a.editing,a.publishing)
    elif a.command=='sync': result=sync(root)
    elif a.command=='start': result=start(root,a.port,a.open)
    elif a.command=='task-status': result=update_task(root,a.id,a.status,a.result,a.output)
    elif a.command=='materials':
        activate(root)
        proc = subprocess.run([sys.executable, '-X', 'utf8', str(SKILL/'scripts/materials.py'), '--root', str(root/'素材库'), *a.args])
        raise SystemExit(proc.returncode)
    print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':
    try: main()
    except Exception as error:
        print(json.dumps({'ok':False,'error':re.sub(r'https?://\S+','[资源地址]',str(error))},ensure_ascii=False),file=sys.stderr);sys.exit(1)
