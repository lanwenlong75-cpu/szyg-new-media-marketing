#!/usr/bin/env python3
"""Read live employee bindings; maintain team snapshots and evidence-linked tasks.

Standard library only. Never executes worker tools or writes employee workspaces.
"""
import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

CODE_EXTENSIONS = {'.md', '.json', '.py', '.js', '.cjs', '.mjs', '.html', '.yaml',
                   '.yml', '.ps1', '.css', '.svg', '.csv', '.toml', '.txt'}
STATUSES = {'planned', 'blocked', 'in_progress', 'delivered', 'verified', 'needs_changes'}
ACTIVE = {'in_progress', 'delivered', 'verified'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def within(root, relative):
    p = Path(relative)
    require(not p.is_absolute() and '..' not in p.parts, '工作区相对路径越界：' + str(relative))
    result = (root / p).resolve()
    require(result.is_relative_to(root), '路径不在指定工作区：' + str(relative))
    return result


def identifier(value):
    require(isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,80}', value), '编号格式无效')
    return value


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


def package_digest(entry):
    h = hashlib.sha256()
    for file in sorted(entry.parent.rglob('*')):
        rel = file.relative_to(entry.parent)
        if any(part in {'.git', '__pycache__', 'node_modules'} for part in rel.parts):
            continue
        if file.is_file() and file.suffix.lower() in CODE_EXTENSIONS:
            require(not file.is_symlink(), '岗位skill中有符号链接：' + str(file))
            h.update(rel.as_posix().encode('utf-8') + b'\0' + digest(file).encode('ascii'))
    return h.hexdigest()


def skill_info(path, working=False):
    entry = Path(path)
    result = {'entry': str(entry), 'exists': entry.is_file()}
    if result['exists']:
        text = entry.read_text(encoding='utf-8-sig')
        name = re.search(r'^name:\s*["\']?([^\r\n"\']+)', text, re.M)
        version = re.search(r'^\s+version:\s*["\']?([^\r\n"\']+)', text, re.M)
        revision = re.search(r'本地规则修订：\s*(\d+)', text)
        result.update(name=name.group(1).strip() if name else None,
                      version=version.group(1).strip() if version else None,
                      entry_sha256=digest(entry),
                      rule_revision=int(revision.group(1)) if revision else None)
        if working:
            result['code_sha256'] = package_digest(entry)
            result['fingerprint_scope'] = 'instructions_templates_scripts; media files tracked as task inputs'
    return result


def registry(root):
    data = read_json(within(root, '00-岗位与协作/员工注册表.json'))
    members = data['members']
    ids = [identifier(m['id']) for m in members]
    require(len(ids) == len(set(ids)), '团队成员ID重复')
    for m in members:
        require(Path(m['root']).is_absolute(), '成员根目录必须是绝对路径')
    return data


def scan_member(member):
    root = Path(member['root']).resolve()
    result = {k: member[k] for k in ('id', 'name', 'kind', 'root', 'purpose')}
    result.update(issues=[], skills=[], objects=[], default_object=None)
    if not root.is_dir():
        result['issues'].append('成员工作区缺失')
    if not (root / 'AGENTS.md').is_file():
        result['issues'].append('成员AGENTS入口缺失')
    config_relative = member.get('config')
    if config_relative:
        try:
            config = read_json(within(root, config_relative))
            result['employee_id'] = config.get('employee_id')
            result['declared_state'] = config.get('state')
            result['default_object'] = config.get('default_service_object_id')
            bindings = config.get('worker_skills', [])
            require(sum(bool(s.get('primary')) for s in bindings) <= 1, '多个主岗位skill')
            for binding in bindings:
                
                if config.get('capability_binding'):
                    import sys
                    sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'scripts'))
                    from module_runtime import local as module_local
                    actual = module_local(root, binding['entry'])
                else: actual = within(root, binding['entry'])
                info = skill_info(actual, working=True)
                info.update(primary=bool(binding.get('primary')),
                            reviewed_for_role=bool(binding.get('reviewed_for_role')),
                            prior_runtime_verified=bool(binding.get('runtime_verified')),
                            capability_notes=binding.get('capability_notes'))
                result['skills'].append(info)
                if not info['exists']:
                    result['issues'].append('已绑定岗位skill入口缺失')
            objects = read_json(within(root, config['object_registry']))
            result['objects'] = [{'id': item['entity_id'], 'name': item['name'],
                                  'folder': item.get('folder')} for item in objects['objects']]
            require(result['default_object'] is None or any(
                x['id'] == result['default_object'] for x in result['objects']), '默认服务对象未登记')
            ledger = root / '_管理/skill迭代记录.json'
            result['iteration_ledger_sha256'] = digest(ledger) if ledger.is_file() else None
            result['iteration_tool_exists'] = (root / '_管理/record_skill_iteration.py').is_file()
        except (OSError, ValueError, KeyError, TypeError) as error:
            result['issues'].append('配置/岗位接入异常：' + str(error))
    else:
        for entry in member.get('skill_entries', []):
            info = skill_info(entry, working=True)
            info['primary'] = True
            info['reviewed_for_role'] = bool(member.get('reviewed_for_role'))
            result['skills'].append(info)
            if not info['exists']:
                result['issues'].append('岗位skill入口缺失')
        result['workflow_entries'] = []
        for relative in member.get('workflow_entries', []):
            path = within(root, relative)
            result['workflow_entries'].append({'path': str(path), 'exists': path.is_file()})
            if not path.is_file():
                result['issues'].append('已登记流程入口缺失：' + relative)
    bound = any(s.get('primary') and s['exists'] for s in result['skills'])
    result['primary_skill_bound'] = bound
    result['status'] = ('接入异常' if result['issues'] else
                        '岗位skill已绑定' if bound else
                        '已接入项目流程' if member['kind'] == 'workflow' else '待绑定岗位skill')
    return result


def scan(root, selected=None):
    data = registry(root)
    members = [m for m in data['members'] if selected is None or m['id'] == selected]
    require(members, '找不到团队成员')
    return {'schema': 'employee-team-snapshot-v1', 'scanned_at': now(),
            'project_id': data['project_id'], 'members': [scan_member(m) for m in members],
            'support_skills': [skill_info(s['entry']) | {'purpose': s['purpose']}
                               for s in data.get('support_skills', [])]}


def refresh(root):
    snapshot = scan(root)
    write_json(within(root, '00-岗位与协作/员工能力快照.json'), snapshot)
    rows = ['# 员工与技能总表', '', '来自当前配置的实时盘点；具体业务效果按任务验收。', '',
            '| 成员 | 接入状态 | 默认对象 | 实际岗位入口 |', '|---|---|---|---|']
    for m in snapshot['members']:
        names = ', '.join(s.get('name') or '缺失入口' for s in m['skills']) or '暂无岗位skill'
        obj = next((o['name'] for o in m['objects'] if o['id'] == m['default_object']), '按本次任务指定')
        rows.append(f"| {m['name']} | {m['status']} | {obj} | {names} |")
    rows += ['', '完整路径、能力范围、摘要与缺项见[能力快照](员工能力快照.json)。', '',
             '团队分工与服务对象分别读取。默认对象不自动带入其他项目任务。', '',
             '盘点UTC时间：' + snapshot['scanned_at']]
    within(root, '00-岗位与协作/员工与技能总表.md').write_text('\n'.join(rows) + '\n', encoding='utf-8')
    return snapshot


def evidence(items):
    require(isinstance(items, list), '证据必须是数组')
    out = []
    for item in items:
        require(isinstance(item, dict) and Path(item['path']).is_absolute(), '证据使用绝对文件路径')
        path = Path(item['path']).resolve()
        require(path.is_file(), '证据文件不存在：' + str(path))
        sha = digest(path)
        require(not item.get('sha256') or item['sha256'] == sha, '证据版本已变化：' + str(path))
        out.append(dict(item, path=str(path), sha256=sha, bytes=path.stat().st_size))
    return out


def validate_graph(stages):
    ids = [identifier(s['id']) for s in stages]
    require(ids and len(ids) == len(set(ids)), '阶段编号为空或重复')
    graph = {s['id']: s.get('depends_on', []) for s in stages}
    require(all(isinstance(v, list) for v in graph.values()), '依赖必须是数组')
    require(all(dep in graph and dep != key for key, deps in graph.items() for dep in deps), '阶段依赖无效')
    visiting, visited = set(), set()
    def visit(key):
        require(key not in visiting, '任务阶段存在循环依赖')
        if key in visited:
            return
        visiting.add(key)
        for dep in graph[key]:
            visit(dep)
        visiting.remove(key)
        visited.add(key)
    for key in graph:
        visit(key)


def stage_capability(stage, member):
    mode = stage.get('mode', 'skill')
    require(mode in {'skill', 'workflow', 'knowledge_only'}, '阶段模式无效')
    if mode == 'skill':
        require(member['primary_skill_bound'] and not member['issues'], '员工未具备可接入的主岗位skill')
    elif mode == 'workflow':
        require(member['kind'] == 'workflow' and not member['issues'], '流程入口未接通')
    else:
        require(not member['issues'], '资料整理入口未接通')


def task_path(root, task_id):
    return within(root, '03-任务与交付/' + identifier(task_id) + '/任务.json')


def create_task(root, spec):
    path = task_path(root, spec['task_id'])
    require(not path.exists(), '任务已存在，先读取现有记录')
    require(spec.get('goal') and spec.get('scope', {}).get('object_name'), '缺目标或服务对象')
    require(spec.get('execution_mode', 'in_session') in {'in_session', 'delegated'}, '执行方式无效')
    live = scan(root)
    require(spec['scope'].get('project_id') == live['project_id'], '任务项目与团队注册表不一致')
    members = {m['id']: m for m in live['members']}
    validate_graph(spec['stages'])
    for s in spec['stages']:
        require(s['employee'] in members, '阶段负责人未注册')
        require(s.get('status', 'planned') in {'planned', 'blocked'}, '新任务阶段须从待执行或阻塞开始')
        require(s.get('goal') and s.get('acceptance'), '阶段缺目标或验收条件')
        if s.get('status') != 'blocked':
            stage_capability(s, members[s['employee']])
        else:
            require(s.get('blocker'), '阻塞阶段缺原因')
        s['status'] = s.get('status', 'planned')
        s['inputs'] = evidence(s.get('inputs', []))
        s['outputs'], s['verification'] = [], []
        s['skill_snapshot'] = members[s['employee']]['skills']
    spec.update(schema='employee-team-task-v1', created_at=now(), updated_at=now(), status='planned', events=[])
    write_json(path, spec)
    return {'task_file': str(path), 'sha256': digest(path), 'status': spec['status']}


def update_stage(root, task_id, stage_id, change):
    path = task_path(root, task_id)
    require(not change.get('expected_task_sha256') or change['expected_task_sha256'] == digest(path), '任务被更新，请重新读取')
    task = read_json(path)
    stages = {s['id']: s for s in task['stages']}
    require(stage_id in stages, '阶段不存在')
    stage = stages[stage_id]
    status = change['status']
    require(status in STATUSES, '阶段状态无效')
    if status in ACTIVE:
        current = scan(root, stage['employee'])['members'][0]
        stage_capability(stage, current)
        for dep in stage.get('depends_on', []):
            require(stages[dep]['status'] == 'verified', '前置阶段尚未通过验收：' + dep)
            evidence(stages[dep]['outputs'])
        evidence(change.get('inputs', stage.get('inputs', [])))
        stage['skill_snapshot'] = current['skills']
    outputs = evidence(change.get('outputs', stage.get('outputs', [])))
    verification = evidence(change.get('verification', stage.get('verification', [])))
    if status in {'delivered', 'verified'}:
        require(outputs, '交付/通过状态必须有实际产物')
    if status == 'verified':
        require(verification and all(v.get('summary') for v in verification), '通过状态必须有验收依据')
    if status == 'blocked':
        require(change.get('blocker') or change.get('note'), '缺阻塞原因')
    changed = outputs != stage.get('outputs', []) or (stage['status'] == 'verified' and status != 'verified')
    if changed:
        affected = {stage_id}
        for _ in task['stages']:
            for s in task['stages']:
                if s['id'] not in affected and any(d in affected for d in s.get('depends_on', [])):
                    affected.add(s['id'])
                    if s['status'] in ACTIVE:
                        s['status'] = 'needs_changes'
                        s['note'] = '上游版本/验收发生变化，重新核对交接'
    stage.update(status=status, outputs=outputs, verification=verification,
                 note=change.get('note', ''), updated_at=now())
    if 'inputs' in change:
        stage['inputs'] = evidence(change['inputs'])
    stage.pop('blocker', None)
    if status == 'blocked':
        stage['blocker'] = change.get('blocker') or change['note']
    task['updated_at'] = now()
    task['status'] = ('verified' if all(s['status'] == 'verified' for s in task['stages']) else
                      'needs_changes' if any(s['status'] == 'needs_changes' for s in task['stages']) else
                      'blocked' if any(s['status'] == 'blocked' for s in task['stages']) else 'in_progress')
    task['events'].append({'at': now(), 'stage': stage_id, 'status': status, 'note': stage['note']})
    write_json(path, task)
    return {'task_file': str(path), 'sha256': digest(path), 'task_status': task['status'], 'stage_status': status}


def check(root):
    live = scan(root)
    errors = [m['name'] + '：' + issue for m in live['members'] for issue in m['issues']]
    warnings = [m['name'] + '：待绑定岗位skill' for m in live['members']
                if not m['primary_skill_bound'] and m['kind'] != 'workflow']
    errors += [s['purpose'] + '：支持skill入口缺失' for s in live['support_skills'] if not s['exists']]
    task_count = 0
    for path in within(root, '03-任务与交付').glob('*/任务.json'):
        task_count += 1
        try:
            task = read_json(path)
            validate_graph(task['stages'])
            members = {m['id']: m for m in live['members']}
            require(task['scope']['project_id'] == live['project_id'], '任务项目不匹配')
            for s in task['stages']:
                require(s['employee'] in members and s['status'] in STATUSES, '负责人/状态无效')
                if s['status'] in ACTIVE:
                    stage_capability(s, members[s['employee']])
                    evidence(s.get('inputs', []))
                if s['status'] == 'verified':
                    require(s.get('outputs') and s.get('verification'), '通过阶段缺产物或验收证据')
                    evidence(s['outputs'])
                    evidence(s['verification'])
        except (OSError, ValueError, KeyError, TypeError) as error:
            errors.append(str(path) + '：' + str(error))
    return {'ok': not errors, 'errors': errors, 'warnings': warnings,
            'members': len(live['members']), 'tasks': task_count,
            'validation_scope': 'bindings, task graph, evidence file integrity; business quality assessed separately'}


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['inspect', 'refresh', 'check', 'create-task', 'update-stage'])
    parser.add_argument('--root', required=True)
    parser.add_argument('--employee')
    parser.add_argument('--spec')
    parser.add_argument('--task')
    parser.add_argument('--stage')
    args = parser.parse_args()
    try:
        require(Path(args.root).is_absolute(), '--root须为绝对路径')
        root = Path(args.root).resolve()
        require(root.is_dir(), '统筹工作区不存在')
        if args.command == 'inspect':
            result = scan(root, args.employee)
        elif args.command == 'refresh':
            result = refresh(root)
        elif args.command == 'check':
            result = check(root)
        else:
            require(args.spec, '缺少--spec')
            spec = read_json(args.spec)
            if args.command == 'create-task':
                result = create_task(root, spec)
            else:
                require(args.task and args.stage, '缺少任务或阶段编号')
                result = update_stage(root, args.task, args.stage, spec)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result.get('ok') is False else 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({'ok': False, 'error': str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
