"""Read and validate the current director employee without external dependencies."""
from pathlib import Path
import argparse
import hashlib
import json
import sys


def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def write_if_changed(path,value):
    data=(json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
    if not path.is_file() or path.read_bytes()!=data:
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
def require(value,message):
    if not value:raise ValueError(message)
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'scripts'))
from module_runtime import local


def register_runtime_paths(root,config,objects):
    index=root/'_管理/IP分类清单.json'
    if not index.is_file():return
    rows=read(index);known={row['path'] for row in rows}
    generated=read(root/'_管理/生成清单.json')['generated']
    tracked=set(generated)
    ledger_path=local(root,config['skill_iteration_policy']['ledger'])
    if ledger_path.is_file():tracked.update(read(ledger_path).get('working_hashes',{}))
    tracked.update(item['folder']+'/对象档案.json' for item in objects)
    for relative in sorted(tracked):
        if relative in known or Path(relative).parts[0]=='_管理' or not local(root,relative).is_file():continue
        owner=next((item['entity_id'] for item in objects if Path(relative).is_relative_to(Path(item['folder']))),None)
        rows.append({'materialId':'MAT-'+hashlib.sha256(relative.encode()).hexdigest()[:12],
                     'path':relative,'classification':'数字员工运行与岗位skill','serviceIpId':owner,
                     'role':'员工配置、岗位方法、运行视图或本轮交付；业务身份仍取原IP档案',
                     'primaryWorkPath':relative,'isProvenanceCopy':False,
                     'authorAndSpeaker':'以原文署名、说话人与素材本人为准',
                     'firstPersonPermission':'需核对实际人物与依据，分类本身不授予第一人称表达'})
    write_if_changed(index,rows)


def sync(root):
    config_path=root/'00-岗位与协作/员工配置.json'
    config=read(config_path)
    source_name=config.get('object_registry_source')
    if not source_name:return config,read(local(root,config['object_registry']))
    source=read(local(root,source_name))
    objects=[]
    for item in source['ips']:
        folder=local(root,source['root_folder'])/item['folder'] if source.get('root_folder') else root/'20-IP档案'/item['folder']
        require(folder.resolve().is_relative_to(root),'IP目录越界')
        profile_path=root/'20-IP档案'/item['profile']
        require(profile_path.resolve().is_relative_to(root) and profile_path.is_file(),'IP档案缺失或越界')
        profile=read(profile_path)
        require(profile['ipId']==item['ipId'] and profile['name']==item['name'],'IP档案与原注册表不一致')
        accounts=[{**a,'account_id':a['accountId'],'entity_id':item['ipId']} for a in profile.get('accounts',[])]
        entity={'entity_id':item['ipId'],'name':item['name'],'kind':'IP',
                'folder':folder.relative_to(root).as_posix(),'profile':profile_path.relative_to(root).as_posix(),
                'facts':{'positioning':profile.get('positioning',[]),'audience':profile.get('audience'),
                         'persona':profile.get('persona'),'signature':profile.get('signature'),
                         'source_profile':profile_path.relative_to(root).as_posix()},'accounts':accounts,
                'derived_from':source_name}
        objects.append(entity)
        cache=folder/'对象档案.json'
        require(not cache.exists() or read(cache).get('derived_from')==source_name,'对象运行视图路径已被原资料占用，保留后增量整合')
        write_if_changed(cache,entity)
    ids=[item['entity_id'] for item in objects]
    require(len(ids)==len(set(ids)) and source['defaultIpId'] in ids,'IP注册表缺少有效默认对象或存在重复')
    registry={'schema':'employee-entities-v1','default_id':source['defaultIpId'],'objects':objects,
              'source_registry':source_name,'maintenance':'由原IP注册表与IP档案同步，不独立维护业务事实'}
    write_if_changed(local(root,config['object_registry']),registry)
    if config['default_service_object_id']!=registry['default_id']:
        config['default_service_object_id']=registry['default_id'];write_if_changed(config_path,config)
    register_runtime_paths(root,config,objects)
    return config,registry


def inspect(root,identity=None,content_type=None,account_id=None):
    config,registry=sync(root)
    identity=identity or registry['default_id']
    entity=next((item for item in registry['objects'] if item['entity_id']==identity),None)
    require(entity is not None,'本次IP尚未登记，先按现有IP流程建档')
    if account_id:require(account_id in {a['account_id'] for a in entity['accounts']},'实际账号未登记在本IP下')
    primary=next(skill for skill in config['worker_skills'] if skill['primary'])
    require(local(root,primary['entry']).is_file(),'主岗位skill缺失')
    profile=read(local(root,entity.get('profile',entity['folder']+'/对象档案.json')))
    expression_suffix=config.get('context',{}).get('knowledge_layout',{}).get('expression_suffix')
    expression=local(root,entity['folder']+'/'+expression_suffix) if expression_suffix else None
    ledger=read(local(root,config['skill_iteration_policy']['ledger']))
    matched=[];excluded=[]
    for rule in ledger['rules']:
        if not rule['active']:continue
        scope=rule['scope']
        applicable=scope['employee_id']==config['employee_id'] and (scope['level']=='role' or scope['entity_id']==identity)
        if scope.get('account_id'):applicable=applicable and scope['account_id']==account_id
        if scope.get('content_type'):applicable=applicable and scope['content_type']==content_type
        (matched if applicable else excluded).append({'id':rule['id'],'instruction':rule['instruction'],'condition':rule['condition'],'scope':scope})
    return {'employee_name':config['employee_name'],'employee_id':config['employee_id'],'workspace':str(root),
            'ip_id':identity,'ip_name':entity['name'],'account_id':account_id,'profile':profile,
            'expression_file':expression.relative_to(root).as_posix() if expression and expression.is_file() else None,
            'expression_rules':expression.read_text(encoding='utf-8-sig') if expression and expression.is_file() else None,
            'primary_skill':primary,'revision':ledger['revision'],'matched_rules':matched,'excluded_rules':excluded,
            'knowledge_layout':config.get('context',{}).get('knowledge_layout',{}),
            'judgement_required':'按实际任务阅读来源和采用条件，未登记账号不补造，内容效果另按实际交付验收'}


def validate(root):
    config,registry=sync(root)
    from runtime_validation import check
    generated=read(root/'_管理/生成清单.json')['generated']
    primary=next(skill for skill in config['worker_skills'] if skill['primary'])
    paths={root/name for name in generated if Path(name).suffix=='.md'}
    paths.update((root/Path(primary['entry']).parent).rglob('*.md'))
    paths.update(local(root,p) for p in config.get('context',{}).get('runtime_reading_entries',[]) if Path(p).suffix=='.md')
    report=check(root,sorted(paths, key=str))
    report['validation_scope']='新增员工运行层、主岗位skill与现有IP工作入口；全库引用及原资料完整性由既有IP架构验收核对'
    report['canonical_ip_registry']=config.get('object_registry_source',config['object_registry'])
    report['registered_objects']=len(registry['objects'])
    write_if_changed(root/'_管理/搭建验收.json',report)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['inspect','sync','validate'])
    parser.add_argument('--root',type=Path)
    parser.add_argument('--ip')
    parser.add_argument('--account')
    parser.add_argument('--content-type')
    args=parser.parse_args()
    candidates=[Path.cwd(),*Path(__file__).resolve().parents]
    root=args.root.resolve() if args.root else next((p for p in candidates if (p/'00-岗位与协作/员工配置.json').is_file()),None)
    try:
        require(root is not None and root.is_dir(),'请指定本次项目实际员工工作区--root')
        if args.command=='validate':result=validate(root)
        elif args.command=='sync':
            config,registry=sync(root);result={'workspace':str(root),'canonical_registry':config.get('object_registry_source'),
                                            'default_id':registry['default_id'],'registered_objects':len(registry['objects'])}
        else:result=inspect(root,args.ip,args.content_type,args.account)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        if args.command=='validate' and not result['structure_ok']:sys.exit(2)
    except (ValueError,OSError,KeyError,StopIteration) as error:parser.exit(2,str(error)+'\n')


if __name__=='__main__':main()
