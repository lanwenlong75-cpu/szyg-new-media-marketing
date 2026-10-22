#!/usr/bin/env python3
"""Version-bound full transcripts, reusing current subtitles before doing ASR."""
import argparse
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote


def read(path, default=None):
    return json.loads(path.read_text(encoding='utf-8-sig')) if path.is_file() else default


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.pending')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)


def info(root, path):
    path = path.resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError('文件不在工作区或不存在：' + str(path))
    st = path.stat()
    return {'path': path.relative_to(root).as_posix(), 'size': st.st_size,
            'modifiedNs': str(st.st_mtime_ns)}


def clock(t):
    ms = round(float(t) * 1000)
    return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02}.{ms%1000:03}'


def seconds(t):
    h, m, s = t.replace(',', '.').split(':')
    return int(h) * 3600 + int(m) * 60 + float(s)


def segments(path):
    if path.suffix.lower() == '.srt':
        rows = []
        for block in re.split(r'\n\s*\n', path.read_text(encoding='utf-8-sig').strip()):
            lines = block.strip().splitlines()
            timing = next((i for i, line in enumerate(lines) if '-->' in line), None)
            if timing is None: continue
            a, b = lines[timing].split('-->')
            rows.append({'start': seconds(a.strip()), 'end': seconds(b.strip().split()[0]),
                         'text': '\n'.join(lines[timing+1:])})
        return rows, {}
    data = read(path)
    if isinstance(data, list): return data, {}
    if isinstance(data, dict) and isinstance(data.get('segments'), list):
        if data.get('complete') is False: raise ValueError('转写尚未完成，不能导出为全文')
        return data['segments'], data
    raise ValueError('需要完整字幕列表、SRT或完整转写segments，不能使用提示词片段代替')


def duration(root, media, supplied=None):
    exe = shutil.which('ffprobe') or next((str(p) for p in (root / '_tools').glob('ffmpeg*/bin/ffprobe.exe')), None)
    if exe:
        result = subprocess.run([exe, '-v', 'error', '-show_entries', 'format=duration',
            '-of', 'default=nw=1:nk=1', str(media)], capture_output=True, text=True, timeout=30)
        if result.returncode == 0: return float(result.stdout.strip())
    if supplied is not None: return float(supplied)
    raise ValueError('未找到ffprobe，请先配置工具以核对逐字稿时间范围')


STYLE = '''body{margin:0;background:#f3f5f0;color:#17352b;font:16px/1.8 system-ui,sans-serif}main{max-width:1140px;margin:32px auto;padding:0 24px}h1{line-height:1.4;font-size:28px}a,button{color:#205f4b}a{margin-right:18px}button{cursor:pointer;border:1px solid #cdd8ce;background:white;border-radius:8px;padding:8px 14px;font:inherit}small,.note{color:#6b776c}nav{display:flex;gap:12px;flex-wrap:wrap;margin:20px 0}.layout{display:grid;grid-template-columns:minmax(240px,360px) minmax(0,1fr);gap:24px}.viewer{position:sticky;top:20px;align-self:start;background:#e5eadf;border-radius:14px;padding:16px}video{width:100%;max-height:450px;background:#10221a}article{background:white;padding:24px;border-radius:14px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit;line-height:2}details{margin:16px 0}summary{cursor:pointer;font-weight:600}.cue{display:flex;gap:12px;border-top:1px solid #e4eadf;padding:10px 0}.cue button{min-width:105px;align-self:start;font-size:13px}.cue span{white-space:pre-wrap}table{width:100%;border-collapse:collapse;background:white}td,th{text-align:left;padding:12px;border-bottom:1px solid #e0e7dc}input{box-sizing:border-box;width:100%;max-width:440px;padding:12px;border:1px solid #d4ded1;border-radius:8px;font:inherit}.badge{display:inline-block;background:#e5eee3;padding:3px 10px;border-radius:8px;font-size:13px}@media(max-width:700px){.layout{grid-template-columns:1fr}.viewer{position:static}article{padding:16px}table{font-size:13px}td,th{padding:8px}.cue{gap:8px}}'''


def link(path):
    return quote(path.replace('\\', '/'), safe='/')


def render_view(root, record, cues, plain, target):
    esc = html.escape
    video = link(os.path.relpath(root / record['media']['path'], target.parent))
    lines = ''.join(f'<div class="cue"><button data-seek="{c["start"]}">{clock(c["start"])[:-4]}</button><span>{esc(c["text"])}</span></div>' for c in cues)
    note = ' · '.join(record.get('uncertaintyNotes', []))
    doc = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(record['title'])} · 逐字稿</title><style>{STYLE}</style><main>
<a href="../../index.html">← 全部视频逐字稿</a><h1>{esc(record['title'])}</h1><p>{esc(record['videoId'])} · {record['kind']} · {clock(record['duration'])[:-4]} · {record['characterCount']}字 <span class="badge">{'已人工听校' if record['humanListeningChecked'] else '待人工逐字听校'}</span></p>
<p class="note">{esc(record['method'])}。{esc(note)}</p><nav><button id="copy">复制全文</button><a href="逐字稿.txt" download>下载全文 TXT</a><a href="逐字稿_带时间码.txt" download>下载带时间码 TXT</a><a href="逐字稿.srt" download>下载 SRT</a><span id="status" role="status"></span></nav>
<div class="layout"><aside class="viewer"><video id="player" src="{video}" controls preload="metadata"></video><p class="note">点击时间码，定位到对应口播。原片中的重复和未说完的话按转写保留。</p><details><summary>对应视频版本</summary><small>{esc(record['media']['path'])}</small></details></aside><article><details open><summary>全文</summary><pre id="full">{esc(plain)}</pre></details><details><summary>按时间定位 · {len(cues)}句</summary>{lines}</details></article></div></main>
<script>document.addEventListener('click',e=>{{const b=e.target.closest('[data-seek]');if(b){{const v=document.getElementById('player');v.currentTime=Number(b.dataset.seek);}}}});document.getElementById('copy').onclick=async()=>{{const text=document.getElementById('full').textContent;try{{await navigator.clipboard.writeText(text);document.getElementById('status').textContent='全文已复制'}}catch{{const r=document.createRange();r.selectNodeContents(document.getElementById('full'));window.getSelection().removeAllRanges();window.getSelection().addRange(r);document.getElementById('status').textContent='全文已选中，可按 Ctrl+C 复制'}}}};</script></html>'''
    target.write_text(doc, encoding='utf-8')


def export(root, row, source, method=None):
    root = root.resolve()
    media = root / (row.get('primaryVideo') or next(iter(row.get('sources', [])), ''))
    binding = info(root, media)
    original, evidence = segments(source)
    if evidence.get('media') and evidence['media'] != binding:
        raise ValueError('转写绑定的视频版本与当前视频不一致')
    if evidence.get('source') and Path(evidence['source']).resolve() != media.resolve():
        raise ValueError('转写source并非当前播放文件，先完成时间与版本映射')
    length = duration(root, media, evidence.get('duration'))
    cues = []
    for c in original:
        text = str(c.get('text', '')).strip().replace('\r', '')
        if not text: continue
        start, end = float(c['start']), float(c['end'])
        if start < 0 or end < start or end > length + .5:
            raise ValueError('逐字稿时间范围超出当前视频')
        if cues and start < cues[-1]['start']: raise ValueError('逐字稿时间顺序错误')
        cues.append({'id': len(cues)+1, 'start': start, 'end': end, 'text': text,
                     'needsListeningCheck': bool(c.get('needsListeningCheck'))})
    if not cues: raise ValueError('没有识别到文字；需人工检查是否为无口播视频')
    source_stamp = info(root, source)
    source_stamp['sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
    kind = '成片' if row.get('primaryVideo') else '原片'
    mode = method or ('依据当前成片字幕整理' if kind == '成片' else '原片完整自动转写')
    signature = hashlib.sha256(json.dumps([binding, source_stamp, mode], sort_keys=True).encode()).hexdigest()[:16]
    out = root / '逐字稿' / row['id'] / signature
    manifest = read(root / '逐字稿/登记.json', {'schema': 'video-transcripts/1', 'records': []})
    previous = next((r for r in reversed(manifest['records']) if r['videoId'] == row['id']
                     and r['media']['path'] == binding['path']), None)
    if previous and previous['media'] != binding and previous['source']['sha256'] == source_stamp['sha256']:
        raise ValueError('同名视频已变化而字幕未更新，请先核对并重新映射全文')
    existing = next((r for r in manifest['records'] if r['recordId'] == signature and r['videoId'] == row['id']), None)
    if existing and all((root / f).is_file() for f in existing['files'].values()):
        return existing
    out.mkdir(parents=True, exist_ok=True)
    notes = ['由现有字幕整理，可能含字幕用语整理；未重新逐字听校。'] if kind == '成片' else ['自动转写，可能有识别误差；保留识别出的重复和未完成句。']
    if row.get('notes'): notes.append(row['notes'])
    plain = '\n'.join(re.sub(r'\s*\n\s*', '', c['text']) for c in cues)
    full = row['title'] + '\n' + f"{row['id']} · {kind}逐字稿\n" + mode + '\n' + '\n'.join(notes) + '\n\n' + plain + '\n'
    timed = '\n'.join(f'[{clock(c["start"])} – {clock(c["end"])}] {c["text"].replace(chr(10), "")}' for c in cues)
    srt = '\n\n'.join(f'{c["id"]}\n{clock(c["start"]).replace(".",",")} --> {clock(c["end"]).replace(".",",")}\n{c["text"]}' for c in cues) + '\n'
    record = {'recordId': signature, 'videoId': row['id'], 'title': row['title'], 'kind': kind,
              'media': binding, 'source': source_stamp, 'method': mode,
              'createdAt': datetime.now(timezone.utc).isoformat(), 'duration': length,
              'humanListeningChecked': bool(row.get('humanListeningChecked')),
              'segmentCount': len(cues), 'characterCount': len(re.sub(r'\s', '', plain)),
              'needsReviewCount': sum(c['needsListeningCheck'] for c in cues),
              'uncertaintyNotes': notes,
              'files': {k: (out / name).relative_to(root).as_posix() for k, name in
                        [('plain','逐字稿.txt'),('timed','逐字稿_带时间码.txt'),('srt','逐字稿.srt'),('json','逐字稿.json'),('view','查看逐字稿.html')]}}
    (out / '逐字稿.txt').write_text(full, encoding='utf-8-sig')
    (out / '逐字稿_带时间码.txt').write_text(full.split('\n\n', 1)[0] + '\n\n' + timed + '\n', encoding='utf-8-sig')
    (out / '逐字稿.srt').write_text(srt, encoding='utf-8-sig')
    write(out / '逐字稿.json', {**record, 'segments': cues})
    render_view(root, record, cues, plain, out / '查看逐字稿.html')
    manifest['records'].append(record)
    manifest['updatedAt'] = record['createdAt']
    write(root / '逐字稿/登记.json', manifest)
    return record


def current_record(root, row, records):
    media = root / (row.get('primaryVideo') or next(iter(row.get('sources', [])), ''))
    try: binding = info(root, media)
    except ValueError: return None
    for record in reversed(records):
        if record['videoId'] != row['id'] or record['media'] != binding: continue
        try: source = info(root, root / record['source']['path'])
        except ValueError: continue
        if source != {k: record['source'][k] for k in ['path','size','modifiedNs']}: continue
        if all((root/f).is_file() for f in record['files'].values()): return record
    return None


def candidate(root, row):
    if not row.get('primaryVideo'): return None
    folder = (root / row['primaryVideo']).parent
    if (folder / '字幕映射.json').is_file(): return folder / '字幕映射.json'
    cues = list(folder.glob('字幕映射_*.json'))
    if len(cues) == 1: return cues[0]
    if (folder / '字幕可编辑.srt').is_file(): return folder / '字幕可编辑.srt'
    return None


def index(root, catalog):
    records = read(root / '逐字稿/登记.json', {'records': []})['records']
    rows, count = [], 0
    for v in catalog['videos']:
        r = current_record(root, v, records)
        if r:
            count += 1
            links = f'<a href="{link(str(Path(r["files"]["view"]).relative_to("逐字稿")))}">查看全文</a><a href="{link(str(Path(r["files"]["plain"]).relative_to("逐字稿")))}" download>下载</a>'
            detail = f'{r["kind"]} · {clock(r["duration"])[:-4]} · {r["characterCount"]}字'
        else: links, detail = '待补齐', '未找到与当前视频一致的逐字稿'
        rows.append(f'<tr><td>{html.escape(v["id"])}</td><td>{html.escape(v["title"])}</td><td>{detail}</td><td>{links}</td></tr>')
    page = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>视频逐字稿</title><style>{STYLE}</style><main><h1>每条视频，留一份逐字稿</h1><p>当前视频 {count}/{len(catalog['videos'])} 份已保存。成片依据对应字幕整理，原片按实际音频转写；每份同时提供全文、时间码与SRT。</p><p class="note">人工逐字听校状态以每份记录为准。新版视频另存对应逐字稿，历史版本保留。</p><input id="search" type="search" placeholder="搜索编号或标题" aria-label="搜索逐字稿"><p></p><table><thead><tr><th>编号</th><th>视频</th><th>对应版本</th><th>逐字稿</th></tr></thead><tbody>{''.join(rows)}</tbody></table></main><script>document.getElementById('search').oninput=e=>{{const q=e.target.value.toLowerCase();document.querySelectorAll('tbody tr').forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q))}};</script></html>'''
    folder = root / '逐字稿'; folder.mkdir(exist_ok=True)
    (folder / 'index.html').write_text(page, encoding='utf-8')
    return count


def sync(root):
    root = root.resolve()
    catalog_path = root / '发布管理/内容登记.json'
    catalog = read(catalog_path, {'videos': []})
    pending, failed = [], []
    for row in catalog['videos']:
        source = candidate(root, row)
        if not source: continue
        try: export(root, row, source)
        except (ValueError, OSError, KeyError) as e: failed.append({'id': row['id'], 'error': str(e)})
    records = read(root / '逐字稿/登记.json', {'records': []})['records']
    changed = False
    for row in catalog['videos']:
        record = current_record(root, row, records)
        value = {'recordId': record['recordId'], 'media': record['media'], 'files': record['files']} if record else None
        if value is None: pending.append(row['id'])
        if row.get('transcript') != value:
            if value: row['transcript'] = value
            else: row.pop('transcript', None)
            changed = True
    if changed: write(catalog_path, catalog)
    count = index(root, catalog)
    return {'saved': count, 'total': len(catalog['videos']), 'pending': pending, 'failed': failed}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--id')
    parser.add_argument('--input', type=Path)
    parser.add_argument('--method')
    args = parser.parse_args()
    root = args.root.resolve()
    if args.input:
        if not args.id: parser.error('--input需指定--id')
        cat = read(root / '发布管理/内容登记.json', {'videos': []})
        row = next(v for v in cat['videos'] if v['id'] == args.id)
        export(root, row, args.input.resolve(), args.method)
    print(json.dumps(sync(root), ensure_ascii=False))


if __name__ == '__main__': main()
