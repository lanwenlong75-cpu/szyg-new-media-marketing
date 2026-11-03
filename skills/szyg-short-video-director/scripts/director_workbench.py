"""Read a director task and persist explicit human choices for its HTML desk."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import tempfile
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import shutil
import threading
from urllib.parse import urlsplit


class Conflict(ValueError):
    pass


def read(path, default=None):
    return json.loads(path.read_text(encoding='utf-8-sig')) if path.is_file() else default


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.desk-', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            json.dump(data, out, ensure_ascii=False, indent=2)
            out.write('\n')
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def source(root):
    root = Path(root).resolve()
    data = read(root / '选题表.json')
    if not data or not isinstance(data.get('items'), list):
        raise ValueError('选题数据尚未就绪')
    return root, data


def state(root):
    root, data = source(root)
    journal = read(root / '工作台状态.json', {'schema': 'director-desk-state-v1', 'items': {}, 'events': []})
    items = []
    seen = set()
    for row in data['items']:
        ident = row.get('topic_id') or f"{data['content_id']}-{int(row['序号']):02d}"
        if not re.fullmatch(r'[\w-]+', ident) or ident in seen:
            raise ValueError('选题编号不唯一或含不支持的字符')
        seen.add(ident)
        script = ''
        script_path = row.get('script_path')
        if script_path:
            path = (root / script_path).resolve()
            if not path.is_relative_to(root):
                raise ValueError('文案路径越过当前任务')
            if path.is_file():
                script = path.read_text(encoding='utf-8-sig')
        digest = hashlib.sha256(script.encode('utf-8')).hexdigest() if script.strip() else None
        choice = journal['items'].get(ident, {})
        adopted = bool(digest and choice.get('adopted_hash') == digest)
        items.append({'id': ident, 'number': row['序号'], 'title': row['选题'], 'category': row['分类'],
                      'script': script, 'scriptHash': digest, 'chosen': bool(choice.get('chosen')),
                      'adopted': adopted, 'previouslyAdopted': bool(choice.get('adopted_hash')),
                      'shot': bool(choice.get('shot')), 'note': choice.get('note', ''),
                      'revision': choice.get('revision', 0), 'updatedAt': choice.get('updated_at')})
    return_url = data.get('return_url', '')
    if not isinstance(return_url, str) or not return_url.startswith('/') or return_url.startswith('//'):
        return_url = ''
    return {'title': data.get('workbench_title', '选题与文案工作台'), 'ip_id': data.get('ip_id'),
            'account_id': data.get('account_id'), 'content_id': data['content_id'], 'items': items,
            'return_url': return_url, 'return_label': data.get('return_label', '返回工作台')}


def act(root, payload):
    root = Path(root).resolve()
    current = state(root)
    item = next((x for x in current['items'] if x['id'] == payload.get('id')), None)
    if item is None:
        raise ValueError('选题不存在')
    if payload.get('revision') != item['revision']:
        raise Conflict('这条内容已有更新，请刷新后再操作')
    action = payload.get('action')
    journal = read(root / '工作台状态.json', {'schema': 'director-desk-state-v1', 'items': {}, 'events': []})
    choice = journal['items'].setdefault(item['id'], {})
    stamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
    if action in ('choose', 'shot'):
        if type(payload.get('value')) is not bool:
            raise ValueError('请选择明确状态')
        choice['chosen' if action == 'choose' else 'shot'] = payload['value']
        if action == 'shot':
            choice['shot_script_hash'] = item['scriptHash'] if payload['value'] else None
            choice['shot_basis'] = '用户在HTML工作台自行标记；不代替原片核验'
    elif action == 'adopt':
        if not item['scriptHash']:
            raise ValueError('这条文案还没有正文，暂时不能采纳')
        if payload.get('scriptHash') != item['scriptHash']:
            raise Conflict('文案已改版，请读完当前正文再采纳')
        if type(payload.get('value')) is not bool:
            raise ValueError('请选择明确状态')
        choice['adopted_hash'] = item['scriptHash'] if payload['value'] else None
        if payload['value']:
            snapshot = root / '文案采纳快照' / item['id'] / (item['scriptHash'] + '.txt')
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            if not snapshot.exists():
                snapshot.write_text(item['script'], encoding='utf-8')
            choice['adopted_snapshot'] = snapshot.relative_to(root).as_posix()
    elif action == 'note':
        note = payload.get('value')
        if not isinstance(note, str) or len(note) > 4000:
            raise ValueError('备注请保持在4000字以内')
        choice['note'] = note
    else:
        raise ValueError('不支持的工作台操作')
    choice.update(revision=item['revision'] + 1, updated_at=stamp)
    event = {'id': item['id'], 'action': action, 'value': payload.get('value'),
             'script_hash': item['scriptHash'], 'source': 'human_ui', 'at': stamp}
    journal['events'].append(event)
    save(root / '工作台状态.json', journal)
    return state(root)


def prepare(root):
    root, _ = source(root)
    state(root)
    template = Path(__file__).resolve().parents[1] / 'assets/director-workbench.html'
    target = root / '选题文案工作台.html'
    content = template.read_bytes()
    if target.is_file() and target.read_bytes() != content:
        old = target.read_bytes()
        backup = root / '工作台历史' / (hashlib.sha256(old).hexdigest()[:16] + '.html')
        backup.parent.mkdir(parents=True, exist_ok=True)
        if not backup.exists():
            shutil.copyfile(target, backup)
    if not target.is_file() or target.read_bytes() != content:
        target.write_bytes(content)
    return target


def make_server(root, port=0):
    root = Path(root).resolve()
    page = prepare(root)
    lock = threading.RLock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def local_request(self):
            allowed = {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
            if self.headers.get('Host') not in allowed:
                self.respond({'error': '请从本机工作台访问'}, 403)
                return False
            return True

        def respond(self, data, status=200, kind='application/json; charset=utf-8'):
            if not isinstance(data, bytes):
                data = json.dumps(data, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(data)

        def do_HEAD(self):
            self.do_GET()

        def do_GET(self):
            if not self.local_request():
                return
            route = urlsplit(self.path).path
            try:
                with lock:
                    if route in ('/', '/director', '/director/'):
                        self.respond(page.read_bytes(), kind='text/html; charset=utf-8')
                    elif route == '/api/director/state':
                        self.respond(state(root))
                    elif route == '/health':
                        self.respond({'app': 'director-workbench', 'content_id': state(root)['content_id']})
                    else:
                        self.respond({'error': '没有这个入口'}, 404)
            except (ValueError, TypeError, KeyError, OSError) as error:
                self.respond({'error': str(error)}, 400)

        def do_POST(self):
            if not self.local_request():
                return
            allowed_origins = {f'http://127.0.0.1:{self.server.server_port}',
                               f'http://localhost:{self.server.server_port}'}
            if (self.headers.get('X-Workbench') != '1' or
                    self.headers.get('Origin') not in allowed_origins | {None}):
                self.respond({'error': '请从工作台按钮保存'}, 403)
                return
            if urlsplit(self.path).path != '/api/director/action':
                self.respond({'error': '没有这个入口'}, 404)
                return
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if size <= 0 or size > 24000:
                    raise ValueError('请求大小无效')
                payload = json.loads(self.rfile.read(size))
                if not isinstance(payload, dict):
                    raise ValueError('操作格式无效')
                with lock:
                    self.respond(act(root, payload))
            except Conflict as error:
                self.respond({'error': str(error)}, 409)
            except (ValueError, TypeError, KeyError, OSError) as error:
                self.respond({'error': str(error)}, 400)

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'serve', 'inspect'])
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--port', type=int, default=0)
    args = parser.parse_args()
    try:
        if args.command == 'inspect':
            print(json.dumps(state(args.root), ensure_ascii=False))
        elif args.command == 'prepare':
            print(json.dumps({'html': str(prepare(args.root))}, ensure_ascii=False))
        else:
            server = make_server(args.root, args.port)
            print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}/director',
                              'root': str(args.root.resolve())}, ensure_ascii=False), flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                server.server_close()
    except (ValueError, OSError, KeyError) as error:
        parser.exit(2, str(error) + '\n')


if __name__ == '__main__':
    main()
