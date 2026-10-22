"""本机素材库：保留原文件、SHA256 去重、可检索登记和剪辑使用记录。"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse
import uuid

ROOT = Path(__file__).resolve().parent
CATEGORIES = {
    '图片与截图': '01-图片截图', '视频与录屏': '02-视频录屏',
    '音频与配乐': '03-音频配乐', '品牌与人物': '04-品牌人物',
    '参考资料': '05-参考资料', '文案与字幕': '06-文案字幕',
    '工程与模板': '07-工程模板',
}
IMAGE_EXT = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp', '.tif', '.tiff', '.avif', '.heic', '.svg'}
VIDEO_EXT = {'.mp4', '.mov', '.m4v', '.mkv', '.webm', '.avi', '.mts', '.m2ts'}
AUDIO_EXT = {'.mp3', '.wav', '.m4a', '.aac', '.flac', '.ogg', '.opus', '.aif', '.aiff'}
TEXT_EXT = {'.txt', '.md', '.srt', '.ass', '.vtt', '.json', '.csv'}
EDITABLE = {'title', 'category', 'tags', 'purpose', 'note', 'rights', 'source', 'status', 'favorite', 'extractedText'}
STATUSES = {'已整理', '待补充', '暂不使用'}
RIGHTS = {'待确认', '自有素材', '已获授权', '仅供参考'}
MAX_UPLOAD = 20 * 1024**3


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')


def atomic_json(path, value):
    atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def atomic_text(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with tmp.open('w', encoding='utf-8', newline='\n') as f:
            f.write(value)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def safe_name(name):
    name = re.split(r'[/\\]', str(name))[-1]
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name).strip(' .')
    if not name:
        raise ValueError('文件名为空')
    if name.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL', *['COM' + str(i) for i in range(10)], *['LPT' + str(i) for i in range(10)]}:
        name = '_' + name
    stem, ext = os.path.splitext(name)
    return stem[:100] + ext[:15]


def media_type(ext):
    if ext in IMAGE_EXT: return 'image'
    if ext in VIDEO_EXT: return 'video'
    if ext in AUDIO_EXT: return 'audio'
    if ext in TEXT_EXT: return 'text'
    return 'file'


def default_category(ext):
    if ext in IMAGE_EXT: return '图片与截图'
    if ext in VIDEO_EXT: return '视频与录屏'
    if ext in AUDIO_EXT: return '音频与配乐'
    if ext in TEXT_EXT: return '文案与字幕'
    if ext in {'.zip', '.prproj', '.aep', '.drp', '.blend'}: return '工程与模板'
    return '参考资料'


class Library:
    def __init__(self, root=ROOT):
        self.root = Path(root).resolve()
        self.admin = self.root / '管理'
        self.catalog_path = self.admin / '素材登记.json'
        self.thread_lock = threading.RLock()
        self.config = {'python': sys.executable, 'ffmpeg': shutil.which('ffmpeg'), 'ffprobe': shutil.which('ffprobe')}
        config_file = self.root / 'runtime.json'
        if config_file.is_file(): self.config.update(json.loads(config_file.read_text(encoding='utf-8-sig')))
        for p in ['00-待入库', '管理/素材卡', '管理/登记备份', '管理/运行日志', '管理/上传临时', '预览']:
            (self.root / p).mkdir(parents=True, exist_ok=True)
        for folder in CATEGORIES.values():
            (self.root / '原始素材' / folder).mkdir(parents=True, exist_ok=True)
        with self.lock():
            if not self.catalog_path.exists():
                self.save({'schemaVersion': 1, 'libraryRoot': str(self.root), 'updatedAt': now(), 'categories': list(CATEGORIES), 'assets': []}, backup=False)
            if not (self.admin / '使用记录.json').exists():
                atomic_json(self.admin / '使用记录.json', [])

    @contextlib.contextmanager
    def lock(self):
        with self.thread_lock:
            f = (self.admin / '.登记锁').open('a+b')
            try:
                f.seek(0, os.SEEK_END)
                if f.tell() == 0:
                    f.write(b'0'); f.flush()
                end = time.monotonic() + 90
                while True:
                    try:
                        f.seek(0)
                        if os.name == 'nt':
                            import msvcrt
                            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                        else:
                            import fcntl
                            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except OSError:
                        if time.monotonic() > end: raise TimeoutError('素材登记正在更新，请稍后重试')
                        time.sleep(.05)
                yield
            finally:
                f.seek(0)
                try:
                    if os.name == 'nt':
                        import msvcrt
                        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                except OSError: pass
                f.close()

    def read(self):
        return json.loads(self.catalog_path.read_text(encoding='utf-8'))

    def save(self, data, backup=True):
        if backup and self.catalog_path.exists():
            backup_path = self.admin / '登记备份' / (datetime.now().strftime('%Y%m%d_%H%M%S_') + uuid.uuid4().hex[:8] + '.json')
            shutil.copy2(self.catalog_path, backup_path)
        data['updatedAt'] = now()
        atomic_json(self.catalog_path, data)
        atomic_text(self.root / 'catalog.js', 'window.ASSET_LIBRARY=' + json.dumps(data, ensure_ascii=False).replace('<', '\\u003c') + ';\n')
        lines = ['素材库索引', '更新时间：' + data['updatedAt'], '素材数：' + str(len(data['assets'])), '']
        for a in data['assets']:
            atomic_json(self.admin / '素材卡' / (a['id'] + '.json'), a)
            lines += [a['id'] + ' | ' + a['title'], '分类：' + a['category'] + '；标签：' + '、'.join(a['tags']), '用途：' + a['purpose'], '文件：' + a['absolutePath'], '']
        atomic_text(self.root / '素材索引.txt', '\n'.join(lines))

    def file(self, relative):
        path = (self.root / relative).resolve()
        if not path.is_relative_to(self.root): raise ValueError('路径超出素材库')
        return path

    def asset(self, asset_id):
        return next((a for a in self.read()['assets'] if a['id'] == asset_id), None)

    def probe(self, path, kind, asset_id):
        details, warnings, preview, extracted = {}, [], '', ''
        if kind == 'image' and path.suffix.lower() != '.svg':
            try:
                from PIL import Image, ImageOps
                with Image.open(path) as im:
                    details = {'width': im.width, 'height': im.height, 'format': im.format}
                    ratio = im.width / im.height
                    details['orientation'] = '横向' if ratio > 1.05 else ('竖向' if ratio < .95 else '方形')
                    thumb = ImageOps.exif_transpose(im).convert('RGBA')
                    thumb.thumbnail((600, 600))
                    bg = Image.new('RGB', thumb.size, 'white')
                    bg.paste(thumb, mask=thumb.getchannel('A'))
                    target = self.root / '预览' / (asset_id + '.jpg')
                    bg.save(target, quality=87)
                    preview = target.relative_to(self.root).as_posix()
            except Exception as e:
                warnings.append('图片信息未完整读取：' + str(e)[:160])
        elif kind in {'video', 'audio'}:
            try:
                result = subprocess.run([self.config['ffprobe'], '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(path)], capture_output=True, timeout=60, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                if result.returncode: raise ValueError(result.stderr.decode('utf-8', errors='replace')[:160])
                info = json.loads(result.stdout)
                details['duration'] = float(info.get('format', {}).get('duration', 0))
                streams = info.get('streams', [])
                video = next((s for s in streams if s.get('codec_type') == 'video'), None)
                audio = next((s for s in streams if s.get('codec_type') == 'audio'), None)
                if video:
                    details.update({k: video[k] for k in ['width', 'height', 'avg_frame_rate', 'sample_aspect_ratio', 'display_aspect_ratio'] if k in video})
                    details['videoCodec'] = video.get('codec_name', '')
                    details['orientation'] = '横向' if video.get('width', 0) > video.get('height', 0) else '竖向'
                    details['color'] = {k: video[k] for k in ['color_space', 'color_transfer', 'color_primaries'] if k in video}
                if audio:
                    details.update({'audioCodec': audio.get('codec_name', ''), 'sampleRate': audio.get('sample_rate', ''), 'channels': audio.get('channels', 0)})
                if kind == 'video' and video:
                    target = self.root / '预览' / (asset_id + '.jpg')
                    result = subprocess.run([self.config['ffmpeg'], '-hide_banner', '-loglevel', 'error', '-y', '-ss', str(min(1, details['duration'] / 3)), '-i', str(path), '-frames:v', '1', '-vf', 'scale=600:600:force_original_aspect_ratio=decrease', str(target)], capture_output=True, timeout=60, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                    if result.returncode == 0 and target.exists(): preview = target.relative_to(self.root).as_posix()
                    else: warnings.append('缩略图未生成；原文件已保留')
            except Exception as e:
                warnings.append('音视频参数未完整读取：' + str(e)[:160])
        elif kind == 'text':
            try:
                raw = path.open('rb')
                with raw: text_bytes = raw.read(256 * 1024)
                try: extracted = text_bytes.decode('utf-8-sig')
                except UnicodeDecodeError: extracted = text_bytes.decode('gb18030', errors='replace')
                if path.stat().st_size > 256 * 1024: warnings.append('检索文字仅保存文件前 256 KiB，完整原文件已保留')
            except Exception as e: warnings.append('文本未提取：' + str(e)[:160])
        return details, warnings, preview, extracted

    def validate_metadata(self, metadata):
        result = {}
        for key, value in metadata.items():
            if key not in EDITABLE: raise ValueError('不支持修改字段：' + key)
            if key == 'tags':
                if not isinstance(value, list) or not all(isinstance(x, str) for x in value): raise ValueError('tags 必须是文字数组')
                result[key] = list(dict.fromkeys(x.strip()[:80] for x in value if x.strip()))[:50]
            elif key == 'favorite':
                if not isinstance(value, bool): raise ValueError('favorite 必须是布尔值')
                result[key] = value
            else:
                if not isinstance(value, str): raise ValueError(key + ' 必须是文字')
                result[key] = value.strip()[:250000 if key == 'extractedText' else 10000]
        if 'title' in result and not result['title']: raise ValueError('素材名称不能为空')
        if 'category' in result and result['category'] not in CATEGORIES: raise ValueError('分类无效')
        if 'status' in result and result['status'] not in STATUSES: raise ValueError('状态无效')
        if 'rights' in result and result['rights'] not in RIGHTS: raise ValueError('使用边界无效')
        return result

    def import_file(self, source_path, metadata=None, original_name=None, source_label=None):
        source_path = Path(source_path).resolve()
        if not source_path.is_file(): raise ValueError('文件不存在：' + str(source_path))
        if source_path.stat().st_size == 0: raise ValueError('空文件不入库：' + source_path.name)
        metadata = self.validate_metadata(metadata or {})
        digest = sha256(source_path)
        filename = safe_name(original_name or source_path.name)
        kind = media_type(Path(filename).suffix.lower())
        imported = {'at': now(), 'filename': filename, 'source': source_label or str(source_path)}
        with self.lock():
            data = self.read()
            existing = next((a for a in data['assets'] if a['sha256'] == digest), None)
            if existing:
                if not self.file(existing['relativePath']).exists(): raise ValueError('相同素材已登记但库内原文件缺失，请运行 verify 核查')
                if sha256(self.file(existing['relativePath'])) != digest: raise ValueError('相同素材的库内原文件已发生变化，请核查后恢复，停止去重入库')
                if not any(x['source'] == imported['source'] and x['filename'] == filename for x in existing['imports']):
                    existing['imports'].append(imported)
                    self.save(data)
                return {'duplicate': True, 'asset': existing}
            asset_id = 'M-' + digest[:16]
            if any(a['id'] == asset_id for a in data['assets']): asset_id = 'M-' + digest
            category = metadata.get('category', default_category(Path(filename).suffix.lower()))
            folder = self.root / '原始素材' / CATEGORIES[category] / asset_id
            folder.mkdir(parents=True, exist_ok=True)
            target = folder / filename
            if target.exists():
                if sha256(target) != digest: raise ValueError('库内目标文件存在且摘要不同，已停止避免覆盖')
            else:
                tmp = folder / ('.' + uuid.uuid4().hex + '.tmp')
                try:
                    shutil.copy2(source_path, tmp)
                    if sha256(tmp) != digest: raise ValueError('复制校验失败：来源可能正在被改动')
                    os.replace(tmp, target)
                finally: tmp.unlink(missing_ok=True)
            details, warnings, preview, extracted = self.probe(target, kind, asset_id)
            asset = {
                'id': asset_id, 'title': Path(filename).stem, 'originalName': filename,
                'category': category, 'mediaType': kind, 'tags': [], 'purpose': '', 'note': '',
                'source': '用户提供', 'rights': '待确认', 'status': '待补充', 'favorite': False,
                'relativePath': target.relative_to(self.root).as_posix(), 'absolutePath': str(target),
                'previewPath': preview, 'sha256': digest, 'size': target.stat().st_size,
                'metadata': details, 'warnings': warnings, 'extractedText': extracted,
                'createdAt': now(), 'updatedAt': now(), 'imports': [imported], 'usageCount': 0,
            }
            asset.update(metadata)
            data['assets'].insert(0, asset)
            self.save(data)
            return {'duplicate': False, 'asset': asset}

    def update(self, asset_id, changes):
        changes = self.validate_metadata(changes)
        with self.lock():
            data = self.read()
            asset = next((a for a in data['assets'] if a['id'] == asset_id), None)
            if not asset: raise ValueError('素材不存在')
            asset.update(changes)
            asset['updatedAt'] = now()
            self.save(data)
            return asset

    def use(self, asset_id, project, purpose='', time_range='', output=''):
        if not isinstance(project, str) or not project.strip(): raise ValueError('请填写项目名称或工程路径')
        if not all(isinstance(x, str) for x in [purpose, time_range, output]): raise ValueError('使用记录字段必须是文字')
        with self.lock():
            data = self.read()
            asset = next((a for a in data['assets'] if a['id'] == asset_id), None)
            if not asset: raise ValueError('素材不存在')
            path = self.admin / '使用记录.json'
            uses = json.loads(path.read_text(encoding='utf-8'))
            event = {'id': 'U-' + uuid.uuid4().hex[:16], 'assetId': asset_id, 'project': project.strip()[:10000], 'purpose': purpose[:10000], 'timeRange': time_range[:200], 'output': output[:10000], 'at': now()}
            uses.append(event)
            atomic_json(path, uses)
            asset['usageCount'] = sum(x['assetId'] == asset_id for x in uses)
            asset['updatedAt'] = now()
            self.save(data)
            return event

    def usage(self, asset_id=''):
        uses = json.loads((self.admin / '使用记录.json').read_text(encoding='utf-8'))
        return [x for x in uses if not asset_id or x['assetId'] == asset_id]

    def verify(self):
        data = self.read()
        results = []
        for asset in data['assets']:
            p = self.file(asset['relativePath'])
            exists = p.is_file()
            actual = sha256(p) if exists else None
            results.append({'id': asset['id'], 'exists': exists, 'sha256Matches': actual == asset['sha256'], 'previewExists': not asset['previewPath'] or self.file(asset['previewPath']).is_file()})
        return {'at': now(), 'count': len(results), 'ok': all(x['exists'] and x['sha256Matches'] and x['previewExists'] for x in results), 'results': results}


def serve(library, port):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            print(now(), fmt % args, flush=True)

        def json_response(self, value, code=200):
            content = json.dumps(value, ensure_ascii=False).encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(content)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(content)

        def local_request(self, mutation=False):
            hosts = {f'127.0.0.1:{port}', f'localhost:{port}'}
            if self.headers.get('Host') not in hosts:
                self.json_response({'error': '仅支持本机访问'}, 403); return False
            origin = self.headers.get('Origin')
            if origin and origin not in {f'http://{host}' for host in hosts}:
                self.json_response({'error': '请求来源不匹配'}, 403); return False
            if mutation and self.headers.get('X-Library-Request') != 'asset-library':
                self.json_response({'error': '请求标识缺失'}, 403); return False
            return True

        def send_file(self, path, mime=None, download=False):
            if not path.is_file():
                self.json_response({'error': '文件不存在'}, 404); return
            size = path.stat().st_size
            start, end, status = 0, size - 1, 200
            range_header = self.headers.get('Range')
            if range_header:
                m = re.fullmatch(r'bytes=(\d*)-(\d*)', range_header)
                try:
                    if not m or (not m[1] and not m[2]): raise ValueError()
                    if m[1]:
                        start = int(m[1]); end = min(int(m[2]), size - 1) if m[2] else size - 1
                    else:
                        start = max(0, size - int(m[2])); end = size - 1
                    if start > end or start >= size: raise ValueError()
                    status = 206
                except ValueError:
                    self.send_response(416); self.send_header('Content-Range', f'bytes */{size}'); self.send_header('Content-Length', '0'); self.end_headers(); return
            self.send_response(status)
            self.send_header('Content-Type', mime or mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
            self.send_header('Content-Length', str(max(0, end - start + 1)))
            self.send_header('Accept-Ranges', 'bytes')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; media-src 'self'; object-src 'none'; frame-ancestors 'none'")
            if status == 206: self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
            if download:
                from urllib.parse import quote
                self.send_header('Content-Disposition', "attachment; filename*=UTF-8''" + quote(path.name))
            self.end_headers()
            if self.command == 'HEAD': return
            with path.open('rb') as f:
                f.seek(start)
                remaining = end - start + 1
                while remaining > 0:
                    block = f.read(min(1024 * 1024, remaining))
                    if not block: break
                    self.wfile.write(block); remaining -= len(block)

        def do_HEAD(self): self.do_GET()

        def do_GET(self):
            if not self.local_request(): return
            uri = urlparse(self.path)
            path = unquote(uri.path)
            query = parse_qs(uri.query)
            try:
                if path == '/api/status':
                    self.json_response({'libraryRoot': str(library.root), 'assets': len(library.read()['assets']), 'service': 'asset-library', 'port': port})
                elif path == '/api/assets': self.json_response(library.read())
                elif path == '/api/usage': self.json_response(library.usage(query.get('id', [''])[0]))
                elif path.startswith('/api/file/'):
                    asset = library.asset(path.rsplit('/', 1)[-1])
                    if not asset: self.json_response({'error': '素材不存在'}, 404); return
                    original = library.file(asset['relativePath'])
                    download = query.get('download', [''])[0] == '1' or asset['mediaType'] not in {'image', 'video', 'audio'} or original.suffix.lower() == '.svg'
                    mime = 'text/plain; charset=utf-8' if asset['mediaType'] == 'text' else None
                    self.send_file(original, mime=mime, download=download)
                elif path.startswith('/预览/'):
                    original = library.file(path.lstrip('/'))
                    if not original.is_relative_to(library.root / '预览'): raise ValueError('预览路径无效')
                    self.send_file(original)
                elif path in {'/', '/index.html', '/app.js', '/style.css', '/preview-fix.css', '/catalog.js'}:
                    self.send_file(library.root / ('index.html' if path == '/' else path[1:]))
                else: self.json_response({'error': '页面不存在'}, 404)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError): pass
            except Exception as e: self.json_response({'error': str(e)}, 400)

        def read_json(self):
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 2 * 1024 * 1024: raise ValueError('请求大小无效')
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict): raise ValueError('请求必须是 JSON 对象')
            return payload

        def do_POST(self):
            if not self.local_request(mutation=True): return
            uri = urlparse(self.path)
            query = parse_qs(uri.query)
            tmp = None
            try:
                if uri.path == '/api/import':
                    filename = safe_name(query.get('filename', [''])[0])
                    length = int(self.headers.get('Content-Length', '0'))
                    if not 0 < length <= MAX_UPLOAD: raise ValueError('文件为空或超过单文件 20 GiB；大文件请使用批量入库.ps1')
                    tmp = library.admin / '上传临时' / (uuid.uuid4().hex + Path(filename).suffix.lower())
                    remaining = length
                    with tmp.open('xb') as f:
                        while remaining:
                            block = self.rfile.read(min(1024 * 1024, remaining))
                            if not block: raise ValueError('文件传输未完成')
                            f.write(block); remaining -= len(block)
                    result = library.import_file(tmp, original_name=filename, source_label='网页上传：' + filename)
                    self.json_response(result)
                elif uri.path == '/api/inbox':
                    results = []
                    inbox = library.root / '00-待入库'
                    for file in sorted(inbox.rglob('*')):
                        if file.is_file() and not file.is_symlink():
                            try:
                                r = library.import_file(file)
                                results.append({'filename': file.name, 'duplicate': r['duplicate'], 'id': r['asset']['id']})
                            except Exception as e: results.append({'filename': file.name, 'error': str(e)})
                    self.json_response({'results': results})
                elif uri.path.startswith('/api/assets/'):
                    self.json_response(library.update(uri.path.rsplit('/', 1)[-1], self.read_json()))
                elif uri.path == '/api/usage':
                    payload = self.read_json()
                    self.json_response(library.use(payload.get('assetId', ''), payload.get('project', ''), payload.get('purpose', ''), payload.get('timeRange', ''), payload.get('output', '')))
                else: self.json_response({'error': '操作不存在'}, 404)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError): pass
            except Exception as e: self.json_response({'error': str(e)}, 400)
            finally:
                if tmp: tmp.unlink(missing_ok=True)

    httpd = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    print(f'素材库：http://127.0.0.1:{port}', flush=True)
    try: httpd.serve_forever()
    except KeyboardInterrupt: pass
    finally: httpd.server_close()


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description='本机剪辑素材库')
    parser.add_argument('--root', default=str(ROOT), help='用于独立验收的库目录；默认本库')
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('serve'); p.add_argument('--port', type=int, default=8771)
    p = sub.add_parser('import'); p.add_argument('paths', nargs='+'); p.add_argument('--metadata', help='UTF-8 JSON 元数据文件')
    p = sub.add_parser('find'); p.add_argument('query', nargs='?', default=''); p.add_argument('--category', default='')
    p = sub.add_parser('update'); p.add_argument('id'); p.add_argument('--metadata', required=True)
    p = sub.add_parser('use'); p.add_argument('id'); p.add_argument('--project', required=True); p.add_argument('--purpose', default=''); p.add_argument('--time-range', default=''); p.add_argument('--output', default='')
    sub.add_parser('verify')
    args = parser.parse_args()
    library = Library(args.root)
    if args.command == 'serve': serve(library, args.port); return
    if args.command == 'import':
        metadata = json.loads(Path(args.metadata).read_text(encoding='utf-8-sig')) if args.metadata else {}
        result = []
        for source in args.paths:
            source = Path(source).resolve()
            if source.is_dir():
                if (source.is_relative_to(library.root) and not source.is_relative_to(library.root / '00-待入库')) or library.root.is_relative_to(source):
                    raise ValueError('请指定素材文件夹或 00-待入库，避免把素材库本身再次入库')
                files = sorted(p for p in source.rglob('*') if p.is_file() and not p.is_symlink())
            else: files = [source]
            for file in files:
                try:
                    r = library.import_file(file, metadata)
                    result.append({'file': str(file), 'id': r['asset']['id'], 'duplicate': r['duplicate']})
                except Exception as e: result.append({'file': str(file), 'error': str(e)})
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if any('error' in x for x in result): sys.exit(1)
    elif args.command == 'find':
        words = args.query.lower().split()
        assets = library.read()['assets']
        result = [a for a in assets if (not args.category or a['category'] == args.category) and all(w in ' '.join(str(a.get(k, '')) for k in ['title', 'originalName', 'tags', 'purpose', 'note', 'extractedText']).lower() for w in words)]
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == 'update': print(json.dumps(library.update(args.id, json.loads(Path(args.metadata).read_text(encoding='utf-8-sig'))), ensure_ascii=False, indent=2))
    elif args.command == 'use': print(json.dumps(library.use(args.id, args.project, args.purpose, args.time_range, args.output), ensure_ascii=False, indent=2))
    elif args.command == 'verify':
        report = library.verify()
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if not report['ok']: sys.exit(1)


if __name__ == '__main__':
    main()
