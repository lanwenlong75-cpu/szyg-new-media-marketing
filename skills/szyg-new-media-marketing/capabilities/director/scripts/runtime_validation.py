from pathlib import Path
from urllib.parse import unquote
import hashlib, json, re

def hash_bytes(data):
    return hashlib.sha256(data).hexdigest()

def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def json_bytes(data):
    return (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8')

def require(condition, reason):
    if not condition:
        raise ValueError(reason)

def absolute(value):
    path = Path(value).expanduser()
    require(path.is_absolute(), '必须使用绝对路径：' + str(path))
    require(not path.is_symlink(), '不处理符号链接：' + str(path))
    return path.resolve()

def markdown_urls(text):
    text = re.sub(r'```[\s\S]*?```|`[^`\n]*`', lambda match: ' ' * len(match[0]), text)
    for match in re.finditer(r'!?\[[^\]\n]*\]\(', text):
        start = pos = match.end()
        depth, angle = 1, False
        while pos < len(text) and depth:
            char = text[pos]
            if char == '<': angle = True
            elif char == '>': angle = False
            elif not angle and char == '(': depth += 1
            elif not angle and char == ')': depth -= 1
            pos += 1
        if not depth:
            raw = text[start:pos - 1].strip()
            value = raw[1:raw.index('>')] if raw.startswith('<') and '>' in raw else re.sub(r'\s+["\'][^"\'\r\n]*["\']$', '', raw)
            yield start, pos - 1, raw, value

def local_ref(value, source):
    if not value or value.startswith(('#', 'http:', 'https:', 'mailto:', 'data:', 'blob:', 'javascript:')):
        return None
    clean = unquote(re.split(r'[?#]', value, maxsplit=1)[0])
    if not clean or '${' in clean:
        return None
    path = source.parent / clean
    require(not path.is_symlink(), '文档引用是符号链接：' + str(path))
    return path.resolve()

def check(root, markdown_paths=None):
    root = absolute(root)
    if read_json(root/'00-岗位与协作/员工配置.json').get('capability_binding'):
        import sys
        sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'scripts'))
        from module_runtime import check as module_check
        return module_check(root)
    config = read_json(root/'00-岗位与协作/员工配置.json')
    registry = read_json(root/config['object_registry'])
    sources = read_json(root/'_管理/来源复制清单.json')
    generated = read_json(root/'_管理/生成清单.json')['generated']
    dependency_report = read_json(root/'_管理/知识依赖检查.json')
    errors, external_links = [], []
    for key in generated:
        if not (root/key).is_file(): errors.append('缺少生成文件：'+key)
    ids = [item['entity_id'] for item in registry['objects']]
    if len(ids)!=len(set(ids)): errors.append('服务对象编号重复')
    if registry['default_id'] is not None and registry['default_id'] not in ids: errors.append('默认对象未登记')
    if config['default_service_object_id'] != registry['default_id']: errors.append('员工默认对象与注册表不一致')
    for item in registry['objects']:
        p = root/item['folder']/'对象档案.json'
        if not p.resolve().is_relative_to(root) or not p.is_file():
            errors.append('对象档案缺失或越界'); continue
        data=read_json(p)
        if data['entity_id']!=item['entity_id'] or data['name']!=item['name']: errors.append('对象身份不一致')
    primary = [item for item in config['worker_skills'] if item['primary']]
    if primary:
        if len(primary)!=1 or not (root/primary[0]['entry']).is_file(): errors.append('主岗位skill入口不完整')
    iteration_policy = config.get('skill_iteration_policy', {})
    approved_working = {}
    iteration_revision = 0
    confirmed_rules = 0
    if iteration_policy.get('enabled'):
        try:
            ledger_path = root/iteration_policy['ledger']
            require(ledger_path.resolve().is_relative_to(root), '迭代记录越界')
            ledger = read_json(ledger_path)
            tracked = [primary[0]['entry'], iteration_policy['rules_file']] if primary else []
            if primary and (iteration_policy.get('tracking') == 'primary-skill-files-v2' or ledger.get('tracking') == 'primary-skill-files-v2'):
                prefix = Path(primary[0]['entry']).parent
                tracked = [relative for relative in generated if Path(relative).is_relative_to(prefix)
                           and '__pycache__' not in Path(relative).parts and Path(relative).suffix not in {'.pyc','.pyo'}]
            approved_working = {relative:generated[relative] for relative in tracked}
            require(ledger['revision']==len(ledger['events']), '迭代版本与事件数量不一致')
            for revision, event in enumerate(ledger['events'], 1):
                require(event['revision']==revision and event['confirmed'] is True
                        and event['feedback_source']=='human_user' and event['feedback_quote'].strip(), '迭代缺少对应的用户确认记录')
                require(event['scope']['employee_id']==config['employee_id'], '迭代记录属于另一个员工')
                if event['scope']['level']=='entity': require(event['scope']['entity_id'] in ids, '迭代对象没有登记')
                accepted = root/event['accepted_output_snapshot']
                require(accepted.resolve().is_relative_to(root) and accepted.is_file()
                        and hash_bytes(accepted.read_bytes())==event['accepted_output_sha256'], '认可交付快照缺失或变化')
                for change in event['changes']:
                    relative=change['file']
                    require(primary and Path(relative).is_relative_to(Path(primary[0]['entry']).parent), '能力更新路径不属于当前主岗位skill')
                    require(approved_working.get(relative)==change['before'], '迭代摘要链不一致')
                    if change['before'] is not None:
                        previous=root/change.get('backup_file', str(Path(event['backup'])/relative))
                        require(previous.resolve().is_relative_to(root) and previous.is_file()
                                and hash_bytes(previous.read_bytes())==change['before'], '迭代旧版快照缺失或变化')
                    approved_working[relative]=change['after']
                for test in event.get('verification', []):
                    evidence = root/test['snapshot']
                    require(test['passed'] is True and evidence.resolve().is_relative_to(root) and evidence.is_file()
                            and hash_bytes(evidence.read_bytes())==test['sha256'], '能力更新验证快照缺失或变化')
            require(approved_working==ledger['working_hashes'], '当前岗位skill摘要与迭代记录不一致')
            for relative, expected in approved_working.items():
                p=root/relative
                require(p.resolve().is_relative_to(root) and p.is_file() and hash_bytes(p.read_bytes())==expected, '岗位skill有未记录修改：'+relative)
            iteration_revision=ledger['revision']
            confirmed_rules=sum(rule['active'] for rule in ledger['rules'])
        except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
            errors.append('岗位skill迭代检查：'+str(error))
    for item in sources:
        p = root/item['destination']
        if not p.resolve().is_relative_to(root) or not p.is_file() or hash_bytes(p.read_bytes())!=item['sha256']:
            errors.append('来源副本或skill资源变化：'+item['destination'])
        if item['kind']=='worker-skill' and item.get('working'):
            if '__pycache__' in Path(item['working']).parts or Path(item['working']).suffix in {'.pyc','.pyo'}: continue
            working=root/item['working']
            expected=approved_working.get(item['working'], item.get('working_sha256',item['sha256']))
            if not working.resolve().is_relative_to(root) or not working.is_file() or hash_bytes(working.read_bytes())!=expected:
                errors.append('本地岗位skill有未记录修改：'+item['working'])
    local_links = 0
    for p in (markdown_paths if markdown_paths is not None else root.rglob('*.md')):
        parts=p.relative_to(root).parts
        if any(part in {'90-来源档案','岗位skill原始快照','skill迭代备份'} for part in parts): continue
        for _,_,_,value in markdown_urls(p.read_text(encoding='utf-8-sig')):
            target=local_ref(value,p)
            if target is None: continue
            local_links+=1
            if not target.is_relative_to(root): external_links.append({'file':p.relative_to(root).as_posix(),'reference':value})
            elif not target.exists(): errors.append('本地引用缺失：'+p.relative_to(root).as_posix()+' → '+value)
    workflow_ready=bool(primary and ids and not errors and not dependency_report['unresolved'] and not external_links)
    simulation=config.get('usage_mode')=='simulation'
    reviewed=bool(primary and primary[0].get('reviewed_for_role'))
    report={'structure_ok':not errors,'primary_skill_bound':bool(primary),'registered_objects':len(ids),
            'knowledge_dependencies_complete':not dependency_report['unresolved'] and not external_links and not errors,
            'source_and_skill_files':len(sources),'local_links_checked':local_links,'errors':errors,
            'unresolved_knowledge_dependencies':dependency_report['unresolved'],'external_references':external_links,
            'usage_mode':config.get('usage_mode','workspace'),'capability_reviewed_for_role':reviewed,
            'skill_iteration_enabled':iteration_policy.get('enabled',False), 'skill_iteration_revision':iteration_revision,
            'active_confirmed_skill_rules':confirmed_rules,
            'ready_for_workflow_trial':workflow_ready,'ready_for_real_task_test':workflow_ready and reviewed and not simulation,
            'live_task_validated':config.get('live_task_validated',False),'application_project_changed':False}
    (root/'_管理/搭建验收.json').write_bytes(json_bytes(report))
    return report

