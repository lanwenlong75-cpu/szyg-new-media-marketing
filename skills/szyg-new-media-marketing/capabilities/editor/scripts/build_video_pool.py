"""Read published-video evidence and metrics; write an editorial pool only."""
from pathlib import Path
import argparse
import hashlib
import html
import json
import re
from datetime import datetime, timezone, timedelta

PUBLIC_PLATFORMS = {'抖音', '视频号', '小红书'}
METRICS = ['views', 'likes', 'comments', 'shares', 'saves', 'follows', 'completion', 'watchSeconds', 'recommendations']


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def inside(root, value):
    path = (root / value).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('来源路径越界：' + str(value))
    return path


def caption_hash(value):
    return hashlib.sha256(re.sub(r'\s+', '', html.unescape(value or '')).encode()).hexdigest()


def link_work(work, events, aliases):
    matched = [e for e in events if e.get('platform') == work['platform']
               and str(e.get('publishId') or '') == work['id']]
    method = '平台作品编号与发布编号一致'
    if not matched:
        for alias in aliases:
            identity = (alias.get('platform'), alias.get('workId'), alias.get('accountId'), alias.get('captionHash'))
            expected = (work['platform'], work['id'], work.get('accountId'), caption_hash(work.get('title')))
            if identity != expected:
                continue
            matched.extend(e for e in events if e.get('videoId') == alias.get('videoId')
                           and e.get('platform') == alias.get('platform')
                           and e.get('publishId') == alias.get('publishId')
                           and e.get('taskId') == alias.get('taskId'))
        method = '已核验别名，账号、摘要与成功任务再次一致'
    if len({e.get('videoId') for e in matched}) != 1:
        return None, None
    return matched[0], method


def receipt_metric(root, event):
    if not event.get('source'):
        return None
    path = inside(root, event['source'])
    if not path.is_file():
        return None
    tasks = read(path).get('data', {}).get('tasks', [])
    task = next((t for t in tasks if t.get('id') == event.get('taskId')
                 and t.get('publishId') == event.get('publishId')
                 and t.get('platformName') == event.get('platform')), None)
    stats = task.get('statistic') if task else None
    if not isinstance(stats, dict):
        return None
    values = {key: stats.get(field) for key, field in {
        'views': 'viewCount', 'likes': 'greatCount', 'comments': 'commentCount',
        'shares': 'shareCount', 'saves': 'collectCount'}.items()}
    if all(value is None for value in values.values()):
        return None
    return {'id': event.get('publishId'), 'platform': event['platform'], 'publishedAt': event.get('actualPublishedAt'),
            **values, 'source': event['source'], 'fetchedAt': event.get('checkedAt'),
            'matchMethod': '成功发布任务回执直接统计'}


def build(root, publisher, binding_path):
    ledger = read(root / '发布管理/视频台账.json')
    analytics = read(root / '运营工作台/数据/运营数据.json')
    aliases = read(root / '运营工作台/数据/作品关联.json').get('links', [])
    transcripts = read(root / '逐字稿/登记.json').get('records', [])
    bindings = read(binding_path).get('bindings', [])
    accounts = {a['id'] for a in analytics.get('accounts', []) if a.get('name') == publisher}
    events = [e for e in ledger.get('events', []) if e.get('status') == '已发布'
              and e.get('platform') in PUBLIC_PLATFORMS and e.get('account') == publisher]
    linked, unmatched = [], []
    for work in analytics.get('works', []):
        if work.get('accountId') not in accounts or work.get('platform') not in PUBLIC_PLATFORMS:
            continue
        event, method = link_work(work, events, aliases)
        item = {key: work.get(key) for key in ['id', 'platform', 'accountId', 'title', 'publishedAt', 'url', *METRICS]}
        item.update(metric_basis='作品累计表现', fetchedAt=analytics.get('fetchedAt'))
        if event:
            item.update(video_id=event['videoId'], publication_id=event.get('publishId'), matchMethod=method)
            linked.append(item)
        else:
            item.update(status='有已发布作品数据，待关联本地全文文案')
            unmatched.append(item)
    pool, excluded = [], []
    for video in ledger.get('videos', []):
        published = [e for e in events if e.get('videoId') == video['id']]
        if not published:
            excluded.append({'video_id': video['id'], 'title': video['title'],
                             'reason': '未取得当前IP公开短视频平台成功发布记录；课程与未发素材不进默认池'})
            continue
        sources, gaps = [], []
        for media in dict.fromkeys(e.get('file') for e in published if e.get('file')):
            match = next((b for b in bindings if b.get('video_id') == video['id']
                          and b.get('published_media') == media), None)
            if match:
                relative, fmt, basis = match['transcript'], match['format'], match['basis']
                human = match.get('human_listening_checked', False)
            else:
                record = next((r for r in reversed(transcripts) if r.get('videoId') == video['id']
                               and r.get('media', {}).get('path') == media), None)
                if not record:
                    gaps.append('缺已发版本全文：' + media)
                    continue
                relative = record['files']['plain']; fmt = 'plain'; basis = '逐字稿登记与发布媒体路径一致'
                human = record.get('humanListeningChecked', False)
            path = inside(root, relative)
            if not path.is_file() or not inside(root, media).is_file():
                gaps.append('文案或已发媒体文件缺失：' + relative)
                continue
            sources.append({'published_media': media, 'transcript': relative, 'format': fmt,
                            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'binding_basis': basis,
                            'human_listening_checked': human})
        stats = []
        for event in published:
            candidates = [w for w in linked if w['video_id'] == video['id'] and w['platform'] == event['platform']
                          and w['publication_id'] == event.get('publishId')]
            metric = candidates[0] if len(candidates) == 1 else receipt_metric(root, event)
            if metric:
                stats.append(metric)
            else:
                stats.append({'platform': event['platform'], 'id': event.get('publishId'),
                              'metric_basis': '未取得作品指标', **{key: None for key in METRICS}})
        pool.append({'video_id': video['id'], 'title': video['title'], 'series': video.get('series'),
                     'published_platforms': [{key: e.get(key) for key in ['platform', 'publishId', 'taskId', 'taskSetId',
                                                  'file', 'source', 'checkedAt', 'url']} for e in published],
                     'current_media_differs_from_published': video.get('publishedFileMismatch', False),
                     'sources': sources, 'source_gaps': gaps, 'metrics': stats,
                     'status': '可进入改编选题' if sources and not gaps else '待补已发版本文案'})
    return {'schema': 'video-to-wechat-pool/1', 'publisher': publisher,
            'builtAt': datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
            'video_root': str(root), 'publication_checked_at': ledger.get('publicationCheckedAt'),
            'metrics_fetched_at': analytics.get('fetchedAt'),
            'source_completeness': {'publication_query_complete': ledger.get('publicationComplete'),
                                    'analytics_query_complete': analytics.get('complete')},
            'source_scope': '本地已登记公开短视频与当前账号接口可见作品；不代表全部历史作品',
            'metric_basis': '作品累计，不能用账号区间增量代替作品表现；缺失留空，0保持0',
            'summary': {'local_catalog': len(ledger.get('videos', [])), 'published_public_videos': len(pool),
                        'ready_with_published_transcript': sum(p['status'] == '可进入改编选题' for p in pool),
                        'visible_platform_works': len(linked) + len(unmatched),
                        'linked_platform_works': len(linked), 'unlinked_platform_works': len(unmatched)},
            'videos': pool, 'unlinked_published_works': unmatched, 'excluded_local_videos': excluded}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video-root', type=Path, required=True)
    parser.add_argument('--publisher-name', required=True)
    parser.add_argument('--bindings', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = args.video_root.resolve()
    output = args.output.resolve()
    if output.is_relative_to(root):
        parser.error('输出必须在员工项目，不能写入只读视频库')
    result = build(root, args.publisher_name, args.bindings)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + '.tmp')
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(output)
    print(json.dumps({'output': str(output), **result['summary']}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
