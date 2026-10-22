"""Scan registered skill sources/copies and record verified local synchronization.

Never modifies employee skills or releases. The supervisor performs authorized edits
with each employee's iteration tool, then this helper checks and records evidence.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse,hashlib,json,re,sys,uuid

EXTENSIONS={'.md','.json','.yaml','.yml','.py','.js','.cjs','.mjs','.html','.css','.svg','.ps1','.sh','.cmd','.txt','.toml','.ttf','.otf','.woff','.woff2'}
SKIP={'.git','__pycache__','node_modules','.venv','venv','validation'}

def require(condition,message):
    if not condition:raise ValueError(message)
def now():return datetime.now(timezone.utc).isoformat()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def save(path,data):
    path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_name(path.name+'.tmp')
    temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');temp.replace(path)
def artifact(root,relative):
    path=Path(relative);require(not path.is_absolute(),'证据使用主管工作区相对路径')
    target=(root/path).resolve();require(target.is_relative_to(root.resolve()),'证据路径超出主管工作区');return target

def fingerprint(entry):
    entry=Path(entry).resolve()
    result={'entry':str(entry),'exists':entry.is_file(),'version':None,'package_sha256':None}
    if not entry.is_file():return result
    text=entry.read_text(encoding='utf-8-sig')
    match=re.search(r'^\s+version:\s*["\']?([^"\'\r\n]+)',text,re.M)
    result['version']=match[1].strip() if match else None
    h=hashlib.sha256();count=0
    for p in sorted(entry.parent.rglob('*')):
        rel=p.relative_to(entry.parent)
        if any(part in SKIP for part in rel.parts) or not p.is_file() or p.suffix.lower() not in EXTENSIONS:continue
        require(not p.is_symlink(),'skill含符号链接，需人工核对：'+str(p))
        h.update(rel.as_posix().encode('utf-8')+b'\0'+sha(p).encode('ascii'));count+=1
    result.update(entry_sha256=sha(entry),package_sha256=h.hexdigest(),files=count,
        fingerprint_scope='methods_scripts_templates_fonts; private media and caches excluded')
    return result

def resolve_source(role):
    source=role['source']
    if 'entry' in source:return Path(source['entry'])
    root=Path(source['root']).resolve();config=read(root/source['config'])
    bindings=[s for s in config['worker_skills'] if s.get('primary')]
    require(len(bindings)==1,'岗位主skill未唯一绑定：'+role['id'])
    path=(root/bindings[0]['entry']).resolve()
    require(path.is_relative_to(root),'岗位绑定超出其工作区：'+role['id'])
    return path

def snapshot(root,persist=True):
    registry=read(root/'00-岗位与协作/skill同步注册表.json')
    ledger_path=root/'00-岗位与协作/skill同步记录.json'
    ledger=read(ledger_path) if ledger_path.exists() else {'records':[]}
    rows=[]
    ids=set()
    for role in registry['roles']:
        require(role['id'] not in ids,'岗位编号重复');ids.add(role['id'])
        source=fingerprint(resolve_source(role));copies=[];copy_ids=set()
        for item in role.get('copies',[]):
            require(item['id'] not in copy_ids,'副本编号重复');copy_ids.add(item['id'])
            current=fingerprint(item['entry'])
            previous=next((r for r in reversed(ledger['records']) if r['role']==role['id'] and r['copy']==item['id']),None)
            if item['policy']=='historical_reference':state='历史参考，保持原样'
            elif not source['exists']:state='权威工作版入口缺失'
            elif not current['exists']:state='副本入口缺失，待接入'
            elif previous:
                source_changed=previous['source_after_sha256']!=source['package_sha256']
                target_changed=previous['target_after_sha256']!=current['package_sha256']
                state=('两侧变化，待合并' if source_changed and target_changed else
                       '源版变化，待同步' if source_changed else '副本变化，待合并核对' if target_changed else
                       '分享工程已核验，接收电脑回执另记' if item['policy']=='sanitized_release' else '本地同步已核验')
            else:state='内容一致，待适用性核对' if source['package_sha256']==current['package_sha256'] else '存在差异，待判定范围'
            copies.append({**item,**current,'state':state,'last_record_id':previous['record_id'] if previous else None})
        rows.append({'id':role['id'],'name':role['name'],'source':source,'copies':copies})
    result={'schema':'skill-sync-scan-v1','scan_id':uuid.uuid4().hex,'scanned_at_utc':now(),'roles':rows,
            'note':'扫描表示当前状态；差异不等于应当覆盖。实际同步在修改目标和验证后另行登记。'}
    if persist:
        save(root/'_管理/skill同步扫描.json',result)
        save(root/'00-岗位与协作/skill同步台账.json',result)
        lines=['# 员工skill同步台账','','按当前实际绑定扫描；原始快照与归档保持原样。','','| 岗位 | 源版本 | 副本 | 副本版本 | 状态 |','|---|---|---|---|---|']
        for role in rows:
            for item in role['copies']:
                lines.append('| '+ ' | '.join([role['name'],str(role['source']['version'] or '未声明'),item['id'],str(item['version'] or '未声明'),item['state']])+' |')
        lines+=['','远端安装、实际调用及成片效果见[跨电脑回执](跨电脑同步回执.json)。','', 'UTC扫描时间：'+result['scanned_at_utc']]
        (root/'00-岗位与协作/skill同步台账.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return result

def record(root,spec):
    prior=read(root/'_管理/skill同步扫描.json')
    require(spec['scan_id']==prior['scan_id'],'扫描已变化，重新读取基线')
    role=next((r for r in prior['roles'] if r['id']==spec['role']),None);require(role is not None,'岗位未注册')
    copy=next((c for c in role['copies'] if c['id']==spec['copy']),None);require(copy is not None,'副本未注册')
    require(copy['policy']!='historical_reference','不能把历史参考登记成同步目标')
    require(role['source']['package_sha256']==spec['expected_source_sha256'],'源基线不匹配')
    require(copy['package_sha256']==spec['expected_before_target_sha256'],'目标原基线不匹配')
    current=snapshot(root,persist=False)
    live_role=next(r for r in current['roles'] if r['id']==spec['role'])
    live_copy=next(c for c in live_role['copies'] if c['id']==spec['copy'])
    require(live_role['source']['package_sha256']==spec['expected_source_sha256'],'同步过程中源版变化，停止登记')
    require(live_copy['exists'] and live_copy['package_sha256']==spec['expected_after_target_sha256'],'实际目标与声明的新版本不符')
    proof=artifact(root,spec['verification_evidence']);require(proof.is_file(),'缺少验证证据')
    evidence=read(proof);require(evidence.get('passed') is True,'验证未通过')
    if copy['policy']=='sanitized_release':require(evidence.get('standards_preserved') is True and evidence.get('privacy_checked') is True,'分享版缺源标准保留与隐私验证')
    require(spec.get('reason') and spec.get('method'),'缺同步理由与处理方法')
    path=root/'00-岗位与协作/skill同步记录.json';ledger=read(path) if path.exists() else {'schema':'skill-sync-ledger-v1','records':[]}
    item={'record_id':uuid.uuid4().hex,'recorded_at_utc':now(),'role':spec['role'],'copy':spec['copy'],'scan_id':spec['scan_id'],
          'source_after_sha256':spec['expected_source_sha256'],'target_before_sha256':spec['expected_before_target_sha256'],
          'target_after_sha256':spec['expected_after_target_sha256'],'reason':spec['reason'],'method':spec['method'],
          'verification':{'path':spec['verification_evidence'],'sha256':sha(proof)},
          'scope':'sharing_artifact_prepared' if copy['policy']=='sanitized_release' else 'local_copy_verified'}
    ledger['records'].append(item);save(path,ledger)
    snapshot(root)
    return item

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['scan','record']);p.add_argument('--root',type=Path,required=True);p.add_argument('--spec',type=Path)
    args=p.parse_args();root=args.root.resolve()
    try:
        result=snapshot(root) if args.command=='scan' else record(root,read(args.spec))
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0
    except (OSError,ValueError,KeyError,TypeError) as error:
        print(json.dumps({'ok':False,'error':str(error)},ensure_ascii=False),file=sys.stderr);return 2
if __name__=='__main__':sys.exit(main())
