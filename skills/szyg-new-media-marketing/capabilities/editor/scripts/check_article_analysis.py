"""Check an article-deconstruction evidence pack; this does not judge prose quality."""
from pathlib import Path
from urllib.parse import urlsplit
import argparse
import json
import sys

DIMENSIONS = {'layout', 'images', 'language', 'structure'}


def check(folder):
    folder = Path(folder).resolve()
    errors = []

    def file(relative):
        if not isinstance(relative, str) or not relative.strip():
            errors.append('证据/交付缺少相对路径')
            return None
        path = Path(relative)
        if path.is_absolute() or '..' in path.parts:
            errors.append('文件路径必须位于当前拆解包内：' + relative)
            return None
        target = folder / path
        if not target.resolve().is_relative_to(folder) or any(p.is_symlink() or getattr(p, 'is_junction', lambda: False)() for p in [target, *target.parents] if p != folder.parent):
            errors.append('文件路径经过链接或超出拆解包：' + relative)
            return None
        if not target.is_file() or target.stat().st_size == 0:
            errors.append('文件缺失或为空：' + relative)
            return None
        return target

    try:
        data = json.loads((folder / '证据清单.json').read_text(encoding='utf-8-sig'))
    except (OSError, ValueError) as exc:
        return {'ok': False, 'errors': ['无法读取证据清单：' + str(exc)]}
    if not isinstance(data, dict):
        return {'ok': False, 'errors': ['证据清单须为JSON对象']}
    if data.get('schema') != 'article-analysis/1': errors.append('证据清单schema无效')
    status = data.get('status')
    if status not in {'complete', 'partial'}: errors.append('状态须为complete或partial')
    source = data.get('source') or {}
    if not isinstance(source, dict): source = {}; errors.append('source须为对象')
    url = urlsplit(str(source.get('url') or ''))
    if url.scheme not in {'http', 'https'} or not url.hostname: errors.append('缺少实际来源URL')
    if not source.get('accessed_at'): errors.append('缺少访问时间')
    if source.get('content_status') not in {'full','partial','unavailable'}: errors.append('正文获取状态无效')
    if source.get('visual_status') not in {'captured','unavailable'}: errors.append('视觉获取状态无效')
    evidence = data.get('evidence', [])
    if not isinstance(evidence, list): evidence = []; errors.append('evidence须为列表')
    by_id = {}
    for item in evidence:
        if not isinstance(item, dict): errors.append('证据项须为对象'); continue
        identity = item.get('id')
        if not isinstance(identity, str) or not identity or identity in by_id: errors.append('证据ID缺失或重复'); continue
        by_id[identity] = item
        if item.get('kind') not in {'screenshot','text','style','html'}: errors.append('证据类型无效：' + identity)
        evidence_path = file(item.get('path'))
        if item.get('kind') == 'screenshot' and evidence_path:
            signature = evidence_path.read_bytes()[:16]
            is_image = (signature.startswith(b'\x89PNG\r\n\x1a\n') or signature.startswith(b'\xff\xd8\xff')
                        or (signature.startswith(b'RIFF') and signature[8:12] == b'WEBP'))
            if not is_image: errors.append('截图文件不是PNG/JPEG/WebP像素图：' + identity)
        if not item.get('locator'): errors.append('证据缺少位置：' + identity)
    for item in evidence:
        if isinstance(item, dict) and item.get('original_id') and item['original_id'] not in by_id: errors.append('标注图缺少原图引用')

    def references(item, name, required):
        ids = item.get('evidence_ids', [])
        if not isinstance(ids, list): errors.append(name+'的evidence_ids须为列表'); return
        if required and not ids: errors.append(name+'没有证据引用')
        for identity in ids:
            if not isinstance(identity, str) or identity not in by_id: errors.append(name+'引用不存在的证据')

    dimensions = data.get('dimensions') or {}
    if not isinstance(dimensions, dict): dimensions = {}; errors.append('dimensions须为对象')
    for name in sorted(DIMENSIONS):
        value = dimensions.get(name)
        if not isinstance(value, dict): errors.append('缺少维度：'+name); continue
        dim_status = value.get('status')
        if dim_status not in {'analyzed','partial','unavailable'}: errors.append('维度状态无效：'+name)
        findings = value.get('findings', [])
        if not isinstance(findings, list): errors.append('findings须为列表：'+name); continue
        if dim_status=='analyzed' and not findings: errors.append('已分析维度没有发现：'+name)
        for finding in findings:
            if not isinstance(finding, dict): errors.append('发现须为对象：'+name); continue
            if not finding.get('observation') or not finding.get('interpretation'): errors.append('发现缺少观察或作用解释：'+name)
            references(finding,name,True)
        if status=='complete' and dim_status!='analyzed': errors.append('完整报告存在未分析维度：'+name)
    methods = data.get('methods', [])
    if not isinstance(methods, list): methods = []; errors.append('methods须为列表')
    for method in methods:
        if not isinstance(method, dict): errors.append('方法须为对象'); continue
        if method.get('dimension') not in DIMENSIONS: errors.append('方法维度无效')
        for field in ['action','conditions','example']:
            if not method.get(field): errors.append('复用方法缺少'+field)
        references(method,'复用方法',True)
    file(data.get('report')); file(data.get('style_card'))
    if data.get('adoption_status') not in {'optional_reference','requested_for_this_task','confirmed_scoped_rule'}: errors.append('采用状态无效')
    if status=='complete':
        if source.get('content_status')!='full' or source.get('visual_status')!='captured': errors.append('缺正文或视觉不能标完整')
        screenshots=[x for x in by_id.values() if x.get('kind')=='screenshot']
        if not screenshots: errors.append('完整排版拆解缺少截图')
        viewport=source.get('viewport') or {}
        if not isinstance(viewport,dict) or not viewport.get('width') or not viewport.get('height'): errors.append('缺少截图视窗')
        kinds={x.get('kind') for x in by_id.values()}
        if not kinds.intersection({'text','html','style'}): errors.append('完整拆解缺少正文来源证据')
        for name in ['layout','images']:
            dimension = dimensions.get(name)
            findings=dimension.get('findings',[]) if isinstance(dimension,dict) else []
            if not isinstance(findings,list): findings=[]
            referenced={identity for item in findings if isinstance(item,dict) for identity in item.get('evidence_ids',[]) if isinstance(identity,str)}
            if not any(by_id.get(identity,{}).get('kind')=='screenshot' for identity in referenced): errors.append(name+'没有引用视觉证据')
        if {m.get('dimension') for m in methods if isinstance(m,dict)}!=DIMENSIONS: errors.append('完整报告的四维可复用方法不全')
    elif status=='partial' and not source.get('limitations'): errors.append('部分报告须说明缺项')
    return {'ok':not errors,'status':status,'evidence_count':len(by_id),'method_count':len(methods),'errors':errors,'scope':'文件与证据引用一致性；不证明真实访问、分析质量或风格认可'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder',required=True,type=Path)
    args=parser.parse_args()
    result=check(args.folder)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['ok'] else 2


if __name__=='__main__':sys.exit(main())
