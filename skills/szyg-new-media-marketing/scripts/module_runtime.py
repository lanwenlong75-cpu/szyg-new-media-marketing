"""Resolve only the live module bound to an employee; validate retained evidence."""
from pathlib import Path
import hashlib, json, sys

HUB = Path(__file__).resolve().parents[1]

def require(value, message):
    if not value: raise ValueError(message)

def read(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def binding(root):
    root = Path(root).resolve()
    config = read(root/'00-岗位与协作/员工配置.json')
    value = config['capability_binding']
    require(value['owner'] == 'szyg-new-media-marketing', '能力所属入口无效')
    module = (HUB/'capabilities'/value['id'].lower()).resolve()
    require(Path(value['entry']).resolve() == module/'GUIDE.md', '能力入口与统一模块不一致')
    require(Path(value['maintenance_root']).resolve() == root, '当前员工无权维护其他员工模块')
    require((module/'GUIDE.md').is_file(), '当前能力模块缺失')
    return module

def local(root, relative):
    root = Path(root).resolve()
    value = str(relative)
    path = Path(value)
    require('..' not in path.parts, '工作路径包含上级跳转')
    if value.startswith('@capability/'):
        target = binding(root)/value[len('@capability/'):]
    else:
        target = path if path.is_absolute() else root/path
    require(not any(p.is_symlink() or getattr(p, 'is_junction', lambda:False)()
                    for p in [target, *target.parents]), '工作路径经过链接')
    target = target.resolve()
    if not target.is_relative_to(root):
        require(target.is_relative_to(binding(root)), '工作路径越过当前员工及其绑定模块')
    return target

def key(root, target):
    root, target = Path(root).resolve(), Path(target).resolve()
    if target.is_relative_to(root): return target.relative_to(root).as_posix()
    return '@capability/' + target.relative_to(binding(root)).as_posix()

def check(root, markdown_paths=None):
    root = Path(root).resolve()
    config = read(root/'00-岗位与协作/员工配置.json')
    errors = []
    module = binding(root)
    objects = read(local(root, config['object_registry']))
    ids = [x['entity_id'] for x in objects['objects']]
    if len(ids) != len(set(ids)): errors.append('服务对象编号重复')
    if objects.get('default_id') != config.get('default_service_object_id'): errors.append('默认对象不一致')
    if objects.get('default_id') is not None and objects['default_id'] not in ids: errors.append('默认对象未登记')
    for obj in objects['objects']:
        p = local(root, obj['folder']+'/对象档案.json')
        if not p.is_file(): errors.append('对象档案缺失：'+str(p)); continue
        actual = read(p)
        if actual['entity_id'] != obj['entity_id'] or actual['name'] != obj['name']: errors.append('对象身份不一致')
    policy = config['skill_iteration_policy']
    ledger = read(local(root, policy['ledger']))
    if ledger['revision'] != len(ledger['events']): errors.append('反馈版本与事件数量不一致')
    for event in ledger['events']:
        if not (event.get('confirmed') is True and event.get('feedback_source') == 'human_user'
                and event.get('scope',{}).get('employee_id') == config['employee_id']): errors.append('反馈来源或员工范围无效')
        p = local(root, event['accepted_output_snapshot'])
        if not p.is_file() or sha(p) != event['accepted_output_sha256']: errors.append('历史认可版本缺失或变化')
        for change in event.get('changes', []):
            if change['before'] is not None:
                p = local(root, change['backup_file'])
                if not p.is_file() or sha(p) != change['before']: errors.append('历史迭代备份变化')
        for test in event.get('verification', []):
            p = local(root, test['snapshot'])
            if not p.is_file() or sha(p) != test['sha256']: errors.append('历史验证证据变化')
    migration = read(local(root, config['capability_binding']['migration_record']))
    # Frozen old ledger remains auditable; migration establishes the current module baseline.
    old = Path(migration['prior_ledger'])
    if not old.is_file() or sha(old) != migration['prior_ledger_sha256']: errors.append('迁移前反馈台账变化')
    else:
        frozen=read(old);base_revision=migration['preserved_revision']
        if ledger['events'][:base_revision] != frozen['events']: errors.append('迁移前反馈事件发生变化')
        expected=dict(migration['module_baseline'])
        for revision,event in enumerate(ledger['events'][base_revision:],base_revision+1):
            if event['revision'] != revision: errors.append('新反馈事件版本次序无效')
            for change in event['changes']:
                name=change['file']
                if not name.startswith('@capability/') or expected.get(name)!=change['before']:
                    errors.append('能力更新摘要链不一致：'+name)
                expected[name]=change['after']
        if expected!=ledger['working_hashes']: errors.append('能力当前摘要与迁移基线及反馈链不一致')
    for relative, expected in ledger['working_hashes'].items():
        p = local(root, relative)
        if not p.is_file() or sha(p) != expected: errors.append('能力模块有未登记修改：'+relative)
    for item in read(root/'_管理/来源复制清单.json'):
        p = local(root, item['destination'])
        if not p.is_file() or sha(p) != item['sha256']: errors.append('来源档案变化：'+item['destination'])
    generated = read(root/'_管理/生成清单.json')['generated']
    for name in generated:
        if not (root/name).is_file(): errors.append('缺少运行文件：'+name)
    dependency = read(root/'_管理/知识依赖检查.json')
    report = {'structure_ok':not errors,'primary_skill_bound':True,'capability_entry':str(module/'GUIDE.md'),
              'registered_objects':len(ids),'knowledge_dependencies_complete':not errors and not dependency['unresolved'],
              'errors':errors,'unresolved_knowledge_dependencies':dependency['unresolved'],'external_references':[],
              'skill_iteration_enabled':policy.get('enabled',False),'skill_iteration_revision':ledger['revision'],
              'active_confirmed_skill_rules':sum(x['active'] for x in ledger['rules']),
              'ready_for_workflow_trial':not errors and bool(ids),'live_task_validated':config.get('live_task_validated',False),
              'validation_scope':'当前模块摘要、历史反馈及备份、对象身份、来源档案和生成文件；业务质量按真实任务验收'}
    (root/'_管理/搭建验收.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return report

if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',required=True)
    args=parser.parse_args()
    try:
        result=check(args.root);print(json.dumps(result,ensure_ascii=False,indent=2));sys.exit(0 if result['structure_ok'] else 2)
    except (ValueError, OSError, KeyError) as error: parser.exit(2,str(error)+'\n')
