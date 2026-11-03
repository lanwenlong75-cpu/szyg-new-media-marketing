"""Read current employee/product routing without secrets or external writes."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def inspect(workspace, entity_id=None):
    config = read_json(workspace / '00-岗位与协作/员工配置.json')
    registry = read_json(workspace / config['object_registry'])
    selected = entity_id or config['default_service_object_id']
    entity = next((item for item in registry['objects'] if item['entity_id'] == selected), None)
    if entity is None:
        raise ValueError('当前产品未在服务对象注册表登记')
    relative = Path(entity['facts']['repo_relative_path'])
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('代码入口应为工作区内的已登记相对路径')
    repo = (workspace / relative).resolve()
    if not repo.is_relative_to(workspace) or not repo.is_dir():
        raise ValueError('代码目录缺失或超出员工工作区')
    issues = []
    for name in ['AGENTS.md', 'SOURCE_OF_TRUTH.md', 'package.json', 'project.config.json']:
        if not (repo / name).is_file():
            issues.append('缺少产品入口：' + name)
    if issues:
        return {'ok': False, 'entity_id': selected, 'issues': issues}
    project = read_json(repo / 'project.config.json')
    package = read_json(repo / 'package.json')
    expected_appid = entity['facts'].get('appid')
    if expected_appid and project.get('appid') != expected_appid:
        issues.append('实际AppID与产品档案不一致')
    if not (repo / project.get('miniprogramRoot', 'miniprogram')).is_dir():
        issues.append('原生客户端目录缺失')
    if not package.get('scripts', {}).get('test'):
        issues.append('缺少已登记的本地测试入口')
    git = shutil.which('git')
    git_state = {'available': bool(git)}
    if git:
        branch = subprocess.run([git, 'branch', '--show-current'], cwd=repo,
                                capture_output=True, text=True, encoding='utf-8')
        status = subprocess.run([git, 'status', '--porcelain'], cwd=repo,
                                capture_output=True, text=True, encoding='utf-8')
        git_state.update(branch=branch.stdout.strip(),
                         changed_files=len(status.stdout.splitlines()),
                         read_ok=branch.returncode == 0 and status.returncode == 0)
        if not git_state['read_ok']:
            issues.append('Git入口检查失败，错误输出需单独安全核对')
    recent = None
    report_file = repo / 'qa/check-report.json'
    if report_file.is_file():
        recorded = read_json(report_file)
        keys = ['checkedAt', 'wxmlWxssCompiler', 'mainBytes', 'wechatDevicePreview',
                'wechatShare', 'developmentUpload', 'release']
        recent = {key: recorded.get(key) for key in keys}
    return {'ok': not issues, 'employee_id': config['employee_id'], 'entity_id': selected,
            'product': entity['name'], 'repo_relative_path': relative.as_posix(),
            'appid': project.get('appid'), 'git': git_state,
            'node_requirement': package.get('engines', {}).get('node'),
            'workflow_commands': {key: package.get('scripts', {}).get(key)
                                  for key in ['test', 'check:native', 'preview']},
            'recent_record_only': recent,
            'issues': issues, 'executed_tests': False, 'external_writes': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True, type=Path)
    parser.add_argument('--entity')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        result = inspect(args.workspace.resolve(), args.entity)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        result = {'ok': False, 'error': str(error), 'external_writes': False}
    content = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding='utf-8')
    print(content)
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
