"""Record user-confirmed rules in an employee's local skill, with rollback."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import argparse
import hashlib
import json
import os
import re
import tempfile
import uuid


def require(value, message):
    if not value: raise ValueError(message)


def digest(data): return hashlib.sha256(data).hexdigest()
def read(path): return json.loads(path.read_text(encoding='utf-8-sig'))
def encoded(value): return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def local(root, relative):
    path = Path(relative)
    require(not path.is_absolute() and '..' not in path.parts, '只能使用当前工作区的相对路径')
    target = root / path
    require(not any(p.is_symlink() for p in [target, *target.parents] if p != root.parent), '路径经过符号链接')
    require(target.resolve().is_relative_to(root), '路径越过当前员工工作区')
    return target


def capability_payloads(root, entry, rules_path, ledger, specification):
    proposals = specification.get('skill_changes', [])
    require(isinstance(proposals, list), 'skill_changes须为相关岗位文件的修改列表')
    if not proposals: return {}, [], None
    diagnosis = specification.get('diagnosis', {})
    require(all(isinstance(diagnosis.get(key), str) and diagnosis[key].strip()
                for key in ['problem', 'cause', 'correction']), '能力更新缺少问题、原因或修正方法')
    tests = specification.get('verification', [])
    require(isinstance(tests, list) and tests, '能力更新缺少实际验证依据')
    evidence = []
    for test in tests:
        require(test.get('passed') is True and isinstance(test.get('summary'), str) and test['summary'].strip(), '能力更新的验证尚未通过')
        saved = local(root, test['evidence'])
        require(saved.is_file() and saved.stat().st_size > 0, '验证记录未实际保存')
        require(isinstance(test.get('covers'), list) and test['covers'], '验证记录缺少对应岗位文件')
        evidence.append({**test, 'sha256': digest(saved.read_bytes())})
    payloads = {}
    managed_pattern = r'<!-- digital-employee-feedback:start -->[\s\S]*?<!-- digital-employee-feedback:end -->'
    for proposed in proposals:
        target = local(root, proposed['file'])
        require(target.is_relative_to(entry.parent) and target != rules_path, '能力更新只能修改当前主岗位skill，确认规则由工具维护')
        relative = target.relative_to(root).as_posix()
        require(not any(part.upper().startswith(('LICENSE', 'COPYING', 'NOTICE', 'THIRD_PARTY', 'SOURCE_AUDIT'))
                        for part in target.relative_to(entry.parent).parts), '原始许可与来源记录继续保留')
        require(target not in payloads, '同一岗位文件重复修改')
        before = ledger['working_hashes'].get(relative)
        require(proposed.get('expected_before_sha256') == before, '岗位文件基线摘要不一致：' + relative)
        require((target.is_file() and before is not None) or (not target.exists() and before is None), '岗位文件有未登记的版本：' + relative)
        replacement = local(root, proposed['replacement_file'])
        require(replacement.is_file() and not replacement.is_relative_to(entry.parent), '先把能力修改候选保存到任务目录，保留当前工作版')
        require(isinstance(proposed.get('reason'), str) and proposed['reason'].strip(), '缺少具体岗位文件修改依据')
        require(any(relative in test['covers'] for test in evidence), '该岗位文件未被验证记录覆盖：' + relative)
        data = replacement.read_bytes()
        require(bool(data), '能力候选文件为空')
        if target == entry:
            old = re.findall(managed_pattern, entry.read_text(encoding='utf-8-sig'))
            new = re.findall(managed_pattern, data.decode('utf-8-sig'))
            require(len(old) == 1 and old == new, '岗位入口修改须保留反馈机制与当前版本')
        payloads[target] = data
    return payloads, evidence, diagnosis


def render_rules(rules):
    lines = ['# 数字员工已确认的岗位规则', '',
             '按当前employee_id、服务对象、实际账号和任务条件选用有效规则；本次用户要求优先。其他员工或其他对象的规则不自动适用。', '']
    for rule in rules:
        if not rule['active']: continue
        scope = rule['scope']
        lines += [f'## {rule["id"]}：{rule["instruction"]}', '',
                  f'- 员工：{scope["employee_id"]}',
                  f'- 范围：{scope["level"]}；对象：{scope.get("entity_name") or "本员工岗位共用方法"}；entity_id：{scope.get("entity_id") or "无"}',
                  f'- 账号：{scope.get("account_id") or "该范围内适用账号"}；内容类型：{scope.get("content_type") or "按下列条件判断"}',
                  f'- 采用条件：{rule["condition"]}',
                  f'- 规则：{rule["instruction"]}',
                  f'- 依据：用户反馈“{rule["feedback_quote"]}”；任务{rule["task_id"]}；认可版本[{Path(rule["accepted_output"]).name}](<{rule["output_link"]}>)',
                  f'- 提炼理由：{rule.get("reason") or "采用用户已确认的做法"}', '']
    if not any(rule['active'] for rule in rules): lines += ['当前没有已确认规则。探索中的草稿与偏好保留在任务记录。', '']
    return ('\n'.join(lines).rstrip() + '\n').encode('utf-8')


def record(root, specification):
    root = Path(root).resolve()
    require(root.is_dir(), '员工工作区不存在')
    feedback = specification.get('feedback', {})
    require(feedback.get('confirmed') is True and feedback.get('source') == 'human_user', '尚未获得真实用户确认，不写入岗位skill')
    require(isinstance(feedback.get('quote'), str) and feedback['quote'].strip(), '缺少真实用户反馈原文')
    config = read(root / '00-岗位与协作/员工配置.json')
    policy = config.get('skill_iteration_policy', {})
    require(policy.get('enabled') is True, '此员工尚未接入本地反馈迭代协议')
    primary = [skill for skill in config['worker_skills'] if skill['primary']]
    require(len(primary) == 1, '没有唯一绑定的岗位skill')
    entry = local(root, primary[0]['entry'])
    require(entry.is_relative_to(root / '.agents/skills') and entry.is_file(), '岗位skill入口不是当前员工的本地工作版')
    rules_path = local(root, policy['rules_file'])
    ledger_path = local(root, policy['ledger'])
    require(rules_path.is_relative_to(entry.parent) and rules_path.is_file(), '确认规则入口缺失或不属于本地岗位skill')
    ledger = read(ledger_path)
    if specification.get('skill_changes') and ledger.get('tracking') != 'primary-skill-files-v2':
        generated = read(root / '_管理/生成清单.json')['generated']
        for relative, expected in generated.items():
            p = local(root, relative)
            if p.is_relative_to(entry.parent) and '__pycache__' not in p.parts and p.suffix not in {'.pyc','.pyo'}:
                ledger['working_hashes'].setdefault(relative, expected)
        ledger['tracking'] = 'primary-skill-files-v2'
    for relative, expected in ledger['working_hashes'].items():
        p = local(root, relative)
        require(p.is_file() and digest(p.read_bytes()) == expected, '本地skill有未记录修改，先核对现状：' + relative)
    capability_files, verification, diagnosis = capability_payloads(root, entry, rules_path, ledger, specification)
    task = specification.get('task_id')
    require(isinstance(task, str) and task.strip(), '缺少实际任务编号')
    output_relative = specification.get('accepted_output')
    require(isinstance(output_relative, str) and output_relative.strip(), '缺少用户认可的交付或验收记录')
    output = local(root, output_relative)
    require(output.is_file() and output.stat().st_size > 0, '认可版本尚未保存为实际文件')
    incoming = specification.get('rule', {})
    require(incoming.get('kind', 'method') == 'method', '业务事实写入知识库，不能作为岗位方法沉淀')
    instruction, condition = incoming.get('instruction'), incoming.get('condition')
    require(isinstance(instruction, str) and instruction.strip(), '缺少可执行规则')
    require(isinstance(condition, str) and condition.strip(), '缺少规则采用条件')
    given_scope = incoming.get('scope', {})
    level = given_scope.get('level', 'entity')
    require(level in {'entity', 'role'}, '规则范围应为entity或role')
    require(given_scope.get('employee_id', config['employee_id']) == config['employee_id'], '规则属于另一个员工')
    scope = {'level': level, 'employee_id': config['employee_id'], 'entity_id': None, 'entity_name': None,
             'account_id': given_scope.get('account_id'), 'content_type': given_scope.get('content_type')}
    if level == 'entity':
        registry = read(local(root, config['object_registry']))
        entity = next((item for item in registry['objects'] if item['entity_id'] == given_scope.get('entity_id')), None)
        require(entity is not None, '对象规则须对应本员工登记的服务对象')
        scope.update(entity_id=entity['entity_id'], entity_name=entity['name'])
        if scope['account_id']:
            require(scope['account_id'] in {a['account_id'] for a in entity.get('accounts', [])}, '实际账号未登记在该对象下')
        reason = incoming.get('reason', '')
        if capability_files and len(registry['objects']) > 1:
            require(any(test.get('kind') == 'scope_isolation' for test in verification), '对象限定的能力更新还须验证其他对象不受影响')
    else:
        require(not given_scope.get('entity_id') and not scope['account_id'], '岗位共用方法不能带对象或账号限定')
        reason = incoming.get('generalization_reason', '')
        require(isinstance(reason, str) and reason.strip(), '提升到岗位共用方法需要概括依据')
    duplicate = None
    for item in ledger['rules']:
        if item['active'] and item['scope'] == scope and item['instruction'] == instruction.strip() and item['condition'] == condition.strip():
            duplicate = item
            break
    if duplicate and not capability_files:
        return {'updated': False, 'duplicate': True, 'rule_id': duplicate['id'], 'revision': ledger['revision']}
    supersedes = incoming.get('supersedes', [])
    require(isinstance(supersedes, list) and all(isinstance(x, str) for x in supersedes), 'supersedes应为既有规则编号列表')
    previous = {item['id']: item for item in ledger['rules']}
    for identity in supersedes:
        require(identity in previous and previous[identity]['active'], '替代的规则不存在或已经失效')
        require(previous[identity]['scope'] == scope, '不能废止其他对象或更大范围的规则')
    if supersedes: require(isinstance(reason, str) and reason.strip(), '替代旧规则需要说明原因')
    if duplicate and capability_files:
        require(not supersedes, '同规则的实现升级不同时废止其他规则')
    revision = ledger['revision'] + 1
    identity = duplicate['id'] if duplicate else f'RULE-{revision:04d}'
    for previous_id in supersedes:
        previous[previous_id]['active'] = False
        previous[previous_id]['superseded_by'] = identity
    rules_relative = rules_path.relative_to(root).as_posix()
    entry_relative = entry.relative_to(root).as_posix()
    backup_relative = f'_管理/skill迭代备份/revision-{revision:04d}'
    backup = local(root, backup_relative)
    if backup.exists():
        backup_relative += '-' + uuid.uuid4().hex[:8]
        backup = local(root, backup_relative)
    output_snapshot = (Path(backup_relative) / ('accepted-version' + output.suffix)).as_posix()
    rule = {'id': identity, 'active': True, 'scope': scope, 'instruction': instruction.strip(), 'condition': condition.strip(),
            'reason': reason, 'task_id': task, 'feedback_quote': feedback['quote'].strip(),
            'accepted_output': output.relative_to(root).as_posix(), 'accepted_output_sha256': digest(output.read_bytes()),
            'accepted_output_snapshot': output_snapshot,
            'output_link': os.path.relpath(root / output_snapshot, rules_path.parent).replace('\\', '/'), 'supersedes': supersedes}
    if not duplicate: ledger['rules'].append(rule)
    entry_text = capability_files.get(entry, entry.read_bytes()).decode('utf-8-sig')
    require(len(re.findall(r'(?m)^本地规则修订：\d+。$', entry_text)) == 1, '岗位入口未完整接入反馈迭代协议')
    entry_text = re.sub(r'(?m)^本地规则修订：\d+。$', f'本地规则修订：{revision}。', entry_text)
    payloads = {**capability_files, entry: entry_text.encode('utf-8'), rules_path: render_rules(ledger['rules'])}
    changes = [{'file': p.relative_to(root).as_posix(), 'before': digest(p.read_bytes()) if p.is_file() else None,
                'after': digest(data)} for p, data in payloads.items()]
    for index, change in enumerate(changes, start=1):
        change['backup_file'] = (Path(backup_relative) / f'before-{index:02d}.bin').as_posix()
    event = {'revision': revision, 'rule_id': identity, 'confirmed': True, 'feedback_source': 'human_user',
             'feedback_quote': rule['feedback_quote'], 'task_id': task, 'scope': scope,
             'accepted_output': rule['accepted_output'], 'accepted_output_sha256': rule['accepted_output_sha256'],
             'accepted_output_snapshot': output_snapshot,
             'diagnosis': diagnosis, 'capability_files': [p.relative_to(root).as_posix() for p in capability_files],
             'verification': [], 'next_task_verification': 'pending',
             'changes': changes, 'backup': backup_relative,
             'recorded_at': datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')}
    for index, test in enumerate(verification, start=1):
        event['verification'].append({**test, 'snapshot': (Path(backup_relative) / f'verification-{index:02d}.bin').as_posix()})
    ledger['events'].append(event)
    ledger['revision'] = revision
    for change in changes: ledger['working_hashes'][change['file']] = change['after']
    payloads[ledger_path] = encoded(ledger)
    originals = {p: p.read_bytes() if p.is_file() else None for p in payloads}
    staged = {}
    try:
        backup.mkdir(parents=True)
        saved_output = local(root, output_snapshot)
        saved_output.parent.mkdir(parents=True, exist_ok=True); saved_output.write_bytes(output.read_bytes())
        for change in changes:
            old = originals[local(root, change['file'])]
            if old is not None: local(root, change['backup_file']).write_bytes(old)
        (backup / 'before-ledger.json').write_bytes(originals[ledger_path])
        for test in event['verification']:
            local(root, test['snapshot']).write_bytes(local(root, test['evidence']).read_bytes())
        for path, data in payloads.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.iteration-', suffix='.tmp', delete=False) as handle:
                handle.write(data); staged[path] = Path(handle.name)
        for path, temporary in staged.items(): os.replace(temporary, path)
        for path, data in payloads.items(): require(path.read_bytes() == data, '写入后回读不一致')
    except Exception:
        for path, data in originals.items():
            if data is None:
                if path.is_file(): path.unlink()
            else: path.write_bytes(data)
        raise
    finally:
        for path in staged.values():
            if path.is_file(): path.unlink()
    return {'updated': True, 'rule_id': identity, 'revision': revision, 'scope': scope,
            'skill_entry': str(entry), 'rules_file': str(rules_path), 'backup': str(backup),
            'capability_files_updated': event['capability_files'], 'next_task_verification': 'pending',
            'source_package_changed': False, 'global_skills_changed': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--feedback-spec', required=True, type=Path)
    args = parser.parse_args()
    try: print(json.dumps(record(args.root, read(args.feedback_spec)), ensure_ascii=False))
    except (ValueError, OSError, KeyError) as error: parser.exit(2, str(error) + '\n')


if __name__ == '__main__': main()
