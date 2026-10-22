"""Create role-aware employee workspaces using only the Python standard library."""
from pathlib import Path
from urllib.parse import unquote
from collections import deque
import argparse
import hashlib
import json
import os
import re
import sys

SKILL_ROOT = Path(__file__).resolve().parent.parent
BASE_DIRS = ['00-岗位与协作', '01-共用知识', '02-服务对象', '03-任务与交付',
             '04-复盘与改进', '30-参考与待归属', '90-来源档案', '99-知识治理', '_管理']


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


def component(value):
    require(isinstance(value, str) and value.strip(), '目录或对象名称为空')
    value = value.strip()
    require(value not in {'.', '..'} and not re.search(r'[<>:"/\\|?*\x00-\x1f]', value), '目录名含路径或非法字符：' + value)
    require(not value.endswith(('.', ' ')), '目录名结尾不合法：' + value)
    require(not re.fullmatch(r'(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?', value), '保留的系统目录名：' + value)
    return value


def category(value):
    parts = Path(value or '00-已知资料').parts
    require(not Path(value or '').is_absolute(), '分类必须是相对目录')
    return Path(*(component(part) for part in parts))


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


def skill_name(entry):
    text = entry.read_text(encoding='utf-8-sig')
    require(text.startswith('---'), '岗位skill缺少frontmatter：' + str(entry))
    frontmatter = text.split('---', 2)[1]
    match = re.search(r'^name:\s*["\']?([a-z0-9][a-z0-9-]*)["\']?\s*$', frontmatter, re.M)
    require(match is not None, '岗位skill缺少有效name：' + str(entry))
    require(re.search(r'^description:\s*\S', frontmatter, re.M), '岗位skill缺少description：' + str(entry))
    return match[1]


def prepare(spec):
    profiles = read_json(SKILL_ROOT / 'assets/role-profiles.json')['roles']
    role = spec.get('role')
    profile = spec.get('profile') or profiles.get(role)
    require(profile is not None, '未知岗位，请选择预设或提供自定义profile')
    for field in ['label','entity_kind','entity_prefix','mission','reasoning_lens','entity_modules','outputs','acceptance']:
        require(field in profile, '岗位结构缺少：' + field)
    for name in profile['entity_modules']: component(name)
    name = component(spec.get('employee_name') or profile['label'])
    display_name = component(spec.get('project_display_name') or '数字员工-' + name)
    usage_mode = spec.get('usage_mode', 'workspace')
    require(usage_mode in {'workspace', 'simulation'}, '未知usage_mode')
    parent = absolute(spec['parent_dir'])
    folder_name = component(spec.get('folder_name') or '数字员工-' + name + '的知识库')
    root = parent / folder_name
    require(root.parent.resolve() == parent, '目标不在指定父目录')
    existing = absolute(spec['existing_dir']) if spec.get('existing_dir') else root
    moving = existing != root
    if moving:
        require(existing.is_dir() and existing.parent == parent and existing != Path(existing.anchor), '改名源必须是指定父目录下的实际目录')
        require(not root.exists(), '重命名目标已存在')
        require(not (existing / '.git').exists(), '不自动移动Git工作区，请用宿主支持的项目操作')
        require(not any(path.is_symlink() for path in existing.rglob('*')), '不自动移动含符号链接的目录')
    require(not root.is_symlink(), '目标是符号链接')
    payloads, sources, dependencies, bindings = {}, [], [], []

    def put(relative, data):
        relative = Path(relative)
        require(not relative.is_absolute() and '..' not in relative.parts, '生成路径越界')
        key = relative.as_posix()
        value = data if isinstance(data, bytes) else (data.strip() + '\n').encode('utf-8')
        require(key not in payloads or payloads[key] == value, '重复目标具有不同内容：' + key)
        payloads[key] = value

    objects, object_paths = [], {}
    for index, item in enumerate(spec.get('service_objects', []), 1):
        entity_id = component(item.get('id') or f'{profile["entity_prefix"]}-{index:03d}')
        entity_name = component(item['name'])
        require(entity_id not in object_paths, '服务对象编号重复：' + entity_id)
        base = Path('02-服务对象') / (entity_id + '-' + entity_name)
        object_paths[entity_id] = base
        accounts = item.get('accounts', [])
        account_ids = [account['account_id'] for account in accounts]
        require(len(account_ids) == len(set(account_ids)), '对象账号编号重复')
        for account in accounts:
            require(account.get('entity_id', entity_id) == entity_id, '账号归属跨对象')
        entity = {'entity_id': entity_id, 'name': entity_name, 'kind': profile['entity_kind'],
                  'facts': item.get('facts', {}), 'accounts': accounts, 'folder': base.as_posix()}
        objects.append(entity)
        put(base / '对象档案.json', json_bytes(entity))
        rows = '\n'.join(f'| {module.split("-",1)[-1]} | [进入]({module}/README.md) |' for module in profile['entity_modules'])
        put(base / 'README.md', f'# {entity_name}工作档案\n\n服务对象：{entity_name}；编号：{entity_id}。先读[对象档案](对象档案.json)，按该对象的事实、账号和工作要求执行。\n\n| 内容 | 入口 |\n|---|---|\n{rows}')
        for module in profile['entity_modules']:
            put(base / module / 'README.md', f'# {entity_name}{module.split("-",1)[-1]}\n\n本模块只保存{entity_name}的对应资料与项目。已知事实见[对象档案](../对象档案.json)。新增材料记录来源、作者、人物、公开范围与有效日期；新任务绑定entity_id={entity_id}和实际账号。\n\n实际任务保存[当前项目](当前项目/README.md)，历史材料保持原状态。')
            put(base / module / '当前项目/README.md', '# 当前项目\n\n按任务编号建立记录，保存服务对象、实际账号、目标、素材来源、版本、交付和实际状态。空模板不计为已完成任务。')
    default_id = spec.get('default_service_object_id')
    if default_id is None and len(objects) == 1: default_id = objects[0]['entity_id']
    require(default_id is None or default_id in object_paths, '默认服务对象未登记')

    worker_skills = spec.get('worker_skills', [])
    if worker_skills:
        require(sum(bool(skill.get('primary')) for skill in worker_skills) == 1, '需要恰好一个主岗位skill')
    for skill in worker_skills:
        source = absolute(skill['source'])
        entry = source / 'SKILL.md' if source.is_dir() else source
        require(entry.name == 'SKILL.md' and entry.is_file(), '岗位skill入口不存在')
        package = entry.parent
        key = skill_name(entry)
        require(not any(binding['name'] == key for binding in bindings), '岗位skill名称重复')
        dest = Path('.agents/skills') / key
        snapshot = Path('_管理/岗位skill原始快照') / key
        count, size = 0, 0
        for file in sorted(package.rglob('*')):
            require(not file.is_symlink(), 'skill包含符号链接：' + str(file))
            if not file.is_file() or '.git' in file.relative_to(package).parts: continue
            data = file.read_bytes()
            relative = dest / file.relative_to(package)
            put(relative, data)
            raw_relative = snapshot / file.relative_to(package)
            put(raw_relative, data)
            sources.append({'source': str(file), 'destination': raw_relative.as_posix(), 'working': relative.as_posix(),
                            'sha256': hash_bytes(data), 'working_sha256': hash_bytes(data), 'kind': 'worker-skill'})
            count += 1
            size += len(data)
        bindings.append({'name': key, 'entry': (dest / 'SKILL.md').as_posix(), 'primary': bool(skill.get('primary')),
                         'package_files': count, 'package_bytes': size, 'source': str(entry), 'runtime_verified': False,
                         'reviewed_for_role': bool(skill.get('reviewed_for_role', False)),
                         'capability_notes': skill.get('capability_notes', '技能包存在不代表正式岗位效果已验收')})

    allowed_roots = [absolute(path) for path in spec.get('allowed_source_roots', [])]
    imports = spec.get('imports', [])
    for item in imports:
        source = absolute(item['source'])
        require(source.is_file(), 'imports应列出已筛选的实际文件：' + str(source))
        allowed = absolute(item.get('allowed_root') or source.parent)
        require(source.is_relative_to(allowed), '来源不在指定来源目录')
        allowed_roots.append(allowed)
    allowed_roots = list(dict.fromkeys(allowed_roots))
    texts = []
    for item in imports:
        first = absolute(item['source'])
        scope = item.get('scope', 'pending')
        require(scope in {'entity', 'shared', 'reference', 'pending'}, '未知材料scope')
        entity_id = item.get('entity_id')
        require(scope != 'entity' or entity_id in object_paths, '对象资料须绑定已登记entity_id')
        base = object_paths[entity_id] if scope == 'entity' else Path('01-共用知识') if scope == 'shared' else Path('30-参考与待归属') / scope
        base = base / category(item.get('category')) / '资料'
        import_id = 'SRC-' + hashlib.sha256(str(first).encode()).hexdigest()[:12]
        working_map = {}
        import_texts = []
        queue, visited = deque([first]), set()
        while queue:
            file = queue.popleft()
            if file in visited: continue
            visited.add(file)
            require(len(visited) <= 5000, '单份来源依赖超过5000个文件，需要重新界定入库范围')
            require(file.is_file() and not file.is_symlink(), '来源文件不可读取')
            require(any(file.is_relative_to(allowed) for allowed in allowed_roots), '来源依赖未授权：' + str(file))
            origin_rel = Path(hashlib.sha256(str(file).encode()).hexdigest()[:10]) / file.name
            raw_dest = Path('90-来源档案') / import_id / origin_rel
            data = file.read_bytes()
            put(raw_dest, data)
            work_dest = base / import_id / origin_rel if file.suffix.lower() == '.md' else raw_dest
            working_map.setdefault(file, work_dest)
            sources.append({'source': str(file), 'destination': raw_dest.as_posix(), 'working': work_dest.as_posix(),
                            'sha256': hash_bytes(data), 'kind': 'knowledge', 'scope': scope, 'entity_id': entity_id,
                            'source_state': item.get('source_state', '按原文保留作者、公开范围和历史状态')})
            if file.suffix.lower() != '.md': continue
            text = data.decode('utf-8-sig')
            import_texts.append((file, text, work_dest))
            for _, _, _, value in markdown_urls(text):
                target = local_ref(value, file)
                if target is None: continue
                if not target.is_file():
                    dependencies.append({'source': str(file), 'reference': value, 'state': 'missing'})
                elif not any(target.is_relative_to(allowed) for allowed in allowed_roots):
                    dependencies.append({'source': str(file), 'reference': value, 'state': 'outside-authorized-roots'})
                else:
                    queue.append(target)
        texts.extend((file, text, work_dest, working_map) for file, text, work_dest in import_texts)
    for file, text, dest, working_map in texts:
        edits = []
        for start, end, raw, value in markdown_urls(text):
            target = local_ref(value, file)
            if target not in working_map: continue
            target_dest = working_map[target]
            suffix = value[len(re.split(r'[?#]', value, maxsplit=1)[0]):]
            rewritten = os.path.relpath(target_dest, dest.parent).replace('\\', '/') + suffix
            if raw.startswith('<'):
                rewritten = '<' + rewritten + '>' + raw[raw.index('>') + 1:]
            elif len(raw) > len(value):
                rewritten += raw[len(value):]
            edits.append((start, end, rewritten))
        for start, end, value in reversed(edits): text = text[:start] + value + text[end:]
        put(dest, text)

    employee_id = 'EMP-' + hashlib.sha256(str(root).encode()).hexdigest()[:12]
    primary = next((item for item in bindings if item['primary']), None)
    rules_relative = (Path(primary['entry']).parent / 'references/数字员工确认规则.md').as_posix() if primary else None
    iteration_policy = {'enabled': True, 'trigger': '真实用户认可对应版本或直接给出长期规则', 'scope': '当前员工本地岗位skill',
                        'rules_file': rules_relative, 'ledger': '_管理/skill迭代记录.json',
                        'protocol': '00-岗位与协作/反馈与skill迭代.md', 'tool': '_管理/record_skill_iteration.py',
                        'tracking': 'primary-skill-files-v2', 'mode': 'feedback-driven-capability-improvement',
                        'iteration_record_template': '04-复盘与改进/能力迭代记录模板.md',
                        'change_targets': ['岗位判断','工作流程','对象偏好','模板','工具脚本','验收标准'],
                        'next_task_verification': '后续同类任务实际发生时记录采用范围、效果与是否再犯',
                        'global_source_updates': '按用户对全局共享skill的实际授权另行处理'}
    put(iteration_policy['protocol'], (SKILL_ROOT/'references/feedback-iteration.md').read_bytes())
    put(iteration_policy['tool'], (SKILL_ROOT/'scripts/record_skill_iteration.py').read_bytes())
    working_hashes = {}
    if primary:
        entry = Path(primary['entry'])
        skill_text = payloads[entry.as_posix()].decode('utf-8-sig')
        managed = '''<!-- digital-employee-feedback:start -->
## 数字员工反馈与岗位规则

本地规则修订：0。

先定位并修好用户指出的交付问题，再复盘原因与改对的方法。依据用户认可或明确长期纠正，自主修改岗位判断、流程、模板、工具与验收；对象偏好限定范围，业务事实归知识库。未确认探索不成为稳定规则，不要求用户手写技术规则或反复提醒写入。

每次任务先读[已确认岗位规则](references/数字员工确认规则.md)和实际岗位流程，只采用与当前employee_id和服务范围匹配的方法，本次用户明确要求优先。读取当前工作区的00-岗位与协作/反馈与skill迭代.md，使用04-复盘与改进/能力迭代记录模板.md及_管理/record_skill_iteration.py更新相关工作版文件，替换冲突旧方法并保留来源、反馈、认可交付、旧版与验证。原失败样例验证通过后回读实际入口；下一次同类任务再记录是否采用及效果，不提前宣称未来任务已验证。
<!-- digital-employee-feedback:end -->'''
        pattern = r'<!-- digital-employee-feedback:start -->[\s\S]*?<!-- digital-employee-feedback:end -->'
        skill_text = re.sub(pattern, managed, skill_text) if re.search(pattern, skill_text) else skill_text.rstrip()+'\n\n'+managed+'\n'
        payloads[entry.as_posix()] = skill_text.encode('utf-8')
        # A new employee starts with its own scoped feedback ledger, even if
        # a provided source package contains another employee's learnt rules.
        payloads[rules_relative] = '# 数字员工已确认的岗位规则\n\n按当前employee_id、服务对象、实际账号和任务条件选用有效规则；本次用户要求优先。\n\n当前没有已确认规则。探索中的草稿与偏好保留在任务记录。\n'.encode('utf-8')
        working_hashes = {relative: hash_bytes(data) for relative, data in payloads.items()
                          if Path(relative).is_relative_to(entry.parent) and '__pycache__' not in Path(relative).parts
                          and Path(relative).suffix not in {'.pyc','.pyo'}}
        for source in sources:
            if source['kind'] == 'worker-skill': source['working_sha256'] = hash_bytes(payloads[source['working']])
    put(iteration_policy['ledger'], json_bytes({'schema':'employee-skill-iterations-v1', 'tracking':'primary-skill-files-v2', 'revision':0,
                                              'rules':[], 'events':[], 'working_hashes':working_hashes}))
    state = ('已绑定岗位skill，待真实任务验收' if primary['reviewed_for_role'] else '已绑定岗位skill，适用能力待审查') if primary else '待绑定岗位skill'
    if usage_mode == 'simulation': state = '模拟搭建与工作流试用，正式岗位效果未验收'
    config = {'schema': 'digital-employee-config-v1', 'employee_id': employee_id, 'employee_name': name,
              'project_display_name': display_name, 'knowledge_folder_name': folder_name, 'role': role or 'custom',
              'role_profile': profile, 'context': spec.get('context', {}), 'default_service_object_id': default_id, 'usage_mode':usage_mode,
              'object_registry': '02-服务对象/服务对象注册表.json', 'worker_skills': bindings, 'state': state,
              'skill_iteration_policy': iteration_policy,
              'live_task_validated': False, 'application_project_state': '未由文件脚本修改应用项目'}
    put('00-岗位与协作/员工配置.json', json_bytes(config))
    put('02-服务对象/服务对象注册表.json', json_bytes({'schema':'employee-entities-v1', 'default_id':default_id, 'objects':objects}))
    put('00-岗位与协作/岗位身份.md', f'# {name}岗位身份\n\n我的职责：{profile["mission"]}。\n\n我的判断角度：{profile["reasoning_lens"]}。\n\n与用户自然交流，用“我”承担判断、行动与交付。当前对象从注册表读取，姓名、品牌、受众、口吻和事实按该对象资料确定。\n\n状态：{state}。')
    skill_instruction = f'业务任务先读取主岗位skill [{primary["name"]}]({primary["entry"]})，按它的真实流程和验收要求完成。' if primary else '当前尚未绑定岗位skill。可以整理真实资料和已知需求；专业岗位能力仍待用户提供或选定真实skill后接入。'
    put('AGENTS.md', f'''# {name}数字员工

先读00-岗位与协作/员工配置.json，确认岗位、当前服务对象与账号，再读对象档案和本次任务。{profile['reasoning_lens']}。使用自然、有岗位判断的数字同事语气，用“我”承担行动和结果，沿用用户明确偏好。

{skill_instruction}

当前服务对象优先按用户本次指定，否则使用注册表default_id；多个对象没有默认时集中确认本次对象，继续做可独立推进的准备。一个对象可有多个实际账号。不同对象的人物、产品、Logo、客户、账号与署名分别读取，资料归到某对象只表示用途，原作者和素材人物保留原身份。

知识库保存身份、业务事实、素材与反馈；岗位skill提供工作流程、工具与验收。新任务按对象、账号、任务编号和版本保存到03-任务与交付或对应对象当前项目。实际交付与反馈回写对应对象；共用经验注明来源与适用条件后归入01-共用知识。

反馈驱动能力迭代：先修好交付，再按[反馈与能力迭代协议](00-岗位与协作/反馈与skill迭代.md)复盘问题原因和有效做法。根据用户认可或明确长期纠正，修改本地岗位skill的判断、流程、模板、工具与验收，把对象偏好写入范围规则、业务事实写入知识库。保留失败样例、认可版本、原反馈、修改备份和当前验证；旧冲突方法同步修正，不要求用户重复提醒写入。未确认探索不成为稳定规则，当前对象偏好不串用。下一次同类任务实际发生时读取新版本，记录采用、效果及是否再犯，未发生前保持待验证。

原始来源在90-来源档案，复制来源不作为执行授权。缺失事实和依赖如实记录，历史资料保持原状态。脚本复制不等于已执行，发布、发送消息、部署与账号变更按用户实际授权完成。真实工作效果以实际岗位任务验收为准。''')
    object_rows = '\n'.join(f'| {item["name"]} | {item["entity_id"]} | [进入]({item["folder"]}/README.md) |' for item in objects)
    put('00-数字员工工作台.md', f'''# {name}数字员工工作台{' 模拟试用' if usage_mode == 'simulation' else ''}

我的职责是{profile['mission']}。工作时先确定服务对象，读取他的资料，再用绑定的岗位skill完成任务。

当前接入状态：{state}。

| 服务对象 | 编号 | 入口 |
|---|---|---|
{object_rows if objects else '| 待建立真实服务对象 | 未登记 | [注册表](02-服务对象/服务对象注册表.json) |'}

[岗位身份](00-岗位与协作/岗位身份.md) · [员工配置](00-岗位与协作/员工配置.json) · [共用知识](01-共用知识/README.md) · [任务与交付](03-任务与交付/README.md) · [反馈与skill迭代](00-岗位与协作/反馈与skill迭代.md) · [来源归属](99-知识治理/资料归属索引.md)

应用中的项目显示名与知识来源关联由宿主支持的项目操作处理；本工作台只确认本地文件和skill接入。''')
    for base in BASE_DIRS:
        if base in {'00-岗位与协作','02-服务对象','99-知识治理','_管理'}: continue
        put(Path(base)/'README.md', f'# {base.split("-",1)[-1]}\n\n按本目录用途保存资料。任务关联具体服务对象、账号、来源和实际状态，历史素材保持原人物与作者信息。')
    put('03-任务与交付/任务记录模板.md', '# 任务记录\n\n- 服务对象名称 / entity_id：\n- 实际账号 / account_id：\n- 任务编号 / 版本：\n- 用户目标与本次要求：\n- 岗位判断与做法：\n- 使用的岗位skill与路径：\n- 依据 / 作者 / 素材人物 / 公开范围：\n- 实际产出与文件：\n- 验收结果 / 尚未完成：\n- 用户原始反馈与认可的版本 / 部分：\n- 已提炼规则 / 适用范围 / rule_id：\n- 岗位skill回写与验证 / 未完成原因：\n- 用户反馈与知识库回写位置：')
    put(iteration_policy['iteration_record_template'], '# 能力迭代记录\n\n- 当前员工 / 服务对象 / 账号 / 任务 / 版本：\n- 用户原话与认可范围 / 明确长期纠正：\n- 问题表现与失败样例：\n- 原因与定位依据：\n- 改对的方法与适用条件：\n- 方法 / 对象偏好 / 业务事实的归属：\n- 岗位skill具体变更文件 / 旧规则替换：\n- 修改前基线 / 修改后摘要 / 备份 / 迭代编号：\n- 原失败样例的复验与相关场景检查：\n- 当前检查实际通过项 / 未验证项：\n- 下一次同类任务 / 实际读取版本 / 采用或排除依据：\n- 后续效果 / 是否再犯 / 下一轮修正：\n\n后续任务发生前，后续效果保持待验证。没有新方法时不编造迭代。')
    for facet, values in profile.get('facets', {}).items():
        for value in values:
            put(Path('01-共用知识')/component(facet)/component(value)/'README.md', f'# {value}共用方法\n\n本目录保存{value}的工作方法、结构与空白模板。实际人物、品牌、产品、价格、素材和结果从当前对象取得。依据岗位skill与实际案例补充方法，不把空目录说明计为已有专业材料。')
    registry_rows = []
    for source in sources:
        if source['kind'] == 'knowledge':
            registry_rows.append(f'| {Path(source["source"]).name.replace("|","｜")} | {source.get("entity_id") or source["scope"]} | [原件](<../{source["destination"]}>) · [工作版](<../{source["working"]}>) |')
    put('99-知识治理/资料归属索引.md', '# 资料归属索引\n\n服务用途与原作者、人物分别辨认；各原文的许可、日期和历史状态继续保留。\n\n| 文件 | 用途 | 入口 |\n|---|---|---|\n'+'\n'.join(registry_rows))
    put('_管理/来源复制清单.json', json_bytes(sources))
    put('_管理/知识依赖检查.json', json_bytes({'unresolved':dependencies,'scope':'知识Markdown引用闭包；外部代码运行、二进制格式和账号能力另行验收'}))
    generated = {key: hash_bytes(value) for key,value in payloads.items()}
    put('_管理/生成清单.json', json_bytes({'schema':'employee-files-v1','generated':generated,'employee_id':employee_id}))
    check_root = existing if moving else root
    conflicts = [key for key,data in payloads.items() if (check_root/key).exists() and (not (check_root/key).is_file() or (check_root/key).read_bytes()!=data)]
    require(not conflicts, '已有不同内容，未执行任何创建或改名：' + ', '.join(conflicts[:12]))
    if check_root.exists():
        for key in payloads:
            current = check_root / key
            for parent_path in [current, *current.parents]:
                if parent_path == check_root.parent: break
                require(not parent_path.is_symlink(), '目标路径经过符号链接：' + str(parent_path))
    return {'root':root,'existing':existing,'moving':moving,'payloads':payloads,'config':config,'dependencies':dependencies,'objects':objects,'sources':sources}


def apply(plan):
    root = plan['root']
    before = {}
    if plan['moving']:
        for file in plan['existing'].rglob('*'):
            if file.is_file(): before[file.relative_to(plan['existing']).as_posix()] = hash_bytes(file.read_bytes())
        plan['existing'].rename(root)
    root.mkdir(parents=True, exist_ok=True)
    created = []
    for relative, data in plan['payloads'].items():
        dest = root / relative
        require(dest.resolve().is_relative_to(root.resolve()), '写入越界')
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            require(dest.read_bytes() == data, '文件在预检后发生变化，停止写入：' + relative)
            continue
        with dest.open('xb') as file: file.write(data)
        created.append(relative)
    for relative, expected in before.items():
        require(hash_bytes((root/relative).read_bytes()) == expected, '重命名后文件变化：' + relative)
    return {'root':str(root),'files_created':len(created),'files_retained':len(before),'folder_renamed':plan['moving'],
            'employee_state':plan['config']['state'],'unresolved_knowledge_dependencies':len(plan['dependencies']),
            'application_project_changed':False,'live_task_validated':False}


def check(root):
    root = Path(root).resolve()
    if read_json(root/'00-岗位与协作/员工配置.json').get('capability_binding'):
        sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'scripts'))
        from module_runtime import check as module_check
        return module_check(root)
    root = absolute(root)
    config = read_json(root/'00-岗位与协作/员工配置.json')
    registry = read_json(root/'02-服务对象/服务对象注册表.json')
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
    for p in root.rglob('*.md'):
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


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['plan','apply','check'])
    parser.add_argument('--spec',type=Path)
    parser.add_argument('--root',type=Path)
    args=parser.parse_args()
    try:
        if args.command=='check':
            require(args.root is not None,'check需要--root')
            result=check(args.root)
        else:
            require(args.spec is not None,'plan/apply需要--spec')
            plan=prepare(read_json(args.spec))
            result=apply(plan) if args.command=='apply' else {
                'root':str(plan['root']),'display_name':plan['config']['project_display_name'],
                'folder_rename':plan['moving'],'planned_files':len(plan['payloads']),
                'planned_bytes':sum(len(data) for data in plan['payloads'].values()),
                'service_objects':[{'id':item['entity_id'],'name':item['name']} for item in plan['objects']],
                'worker_skills':[{'name':item['name'],'primary':item['primary']} for item in plan['config']['worker_skills']],
                'employee_state':plan['config']['state'],'unresolved_knowledge_dependencies':plan['dependencies']}
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 0 if result.get('structure_ok',True) else 2
    except (ValueError, OSError, KeyError, UnicodeError, json.JSONDecodeError) as error:
        print(json.dumps({'ok':False,'error':str(error)},ensure_ascii=False),file=sys.stderr)
        return 2


if __name__=='__main__':
    sys.exit(main())
