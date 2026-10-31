"""Prepare the WorkBuddy import from the universal package's single skill tree."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import shutil
import zipfile

def read(path):
    return Path(path).read_text(encoding='utf-8-sig')

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def files(root):
    return {p.relative_to(root).as_posix(): p for p in root.rglob('*') if p.is_file()}

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding='utf-8')

def prepare(bundle, output):
    bundle, output = bundle.resolve(), output.resolve()
    if output.is_relative_to(bundle) or bundle.is_relative_to(output):
        raise ValueError('Keep prepared files outside the original installation package.')
    if output.exists() and any(output.iterdir()):
        raise ValueError('Preserve existing prepared files; choose a new empty output directory.')
    spec = importlib.util.spec_from_file_location('universal_installer', bundle / 'install.py')
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    installer.validate_bundle(bundle)
    version = json.loads(read(bundle / 'VERSION.json'))
    release = version['release']
    output.mkdir(parents=True, exist_ok=True)
    skill = output / 'skill-source'
    shutil.copytree(bundle / 'skills/szyg-new-media-marketing', skill)
    header = ('display_name: 新媒体数字员工\ndisplay_name_en: New Media Digital Team\n'
              'description_zh: 新媒体营销统一入口，十四项岗位能力及完整方法、模板、脚本与验收标准。\n'
              'description_en: Fourteen new media role capabilities with reusable methods and delivery standards.\n'
              'version: "' + version['source_entry_version'] + '"\nauthor: "szyg-new-media-marketing contributors"\n')
    text = read(skill / 'SKILL.md').replace('---\n', '---\n' + header, 1)
    text += '\n## WorkBuddy接入\n\n读取[宿主接入说明](references/workbuddy-setup.md)，从WorkBuddy当前真实工具定位已导入目录，并按当前项目资料使用方法。\n'
    write(skill / 'SKILL.md', text)
    write(skill / 'references/workbuddy-setup.md', '# WorkBuddy接入 · ' + release + '\n\n本Skill由通用安装包准备。使用WorkBuddy本地上传技能导入生成的ZIP，再将实际导入目录交给同目录的Initialize-WorkBuddy.ps1完成工作区初始化。采用当前用户自己的事实和素材；本地改进与已有业务资料先保留、比对和迁移。安装不等于专业成品验收。\n\n官方导入说明：https://intl.cloud.tencent.com/zh/document/product/1316/84503\n')
    save(skill / '版本信息.json', {**version, 'host': 'WorkBuddy'})
    for name in ('LICENSE', 'THIRD_PARTY.md'):
        write(skill / name, read(bundle / name).replace('skills/szyg-new-media-marketing/', ''))
    shared = {name: sha(path) for name, path in files(skill).items() if name.startswith(('capabilities/', 'scripts/'))}
    assert hashlib.sha256(json.dumps(shared, sort_keys=True, separators=(',', ':')).encode()).hexdigest() == version['method_content_sha256']
    kit = output / 'WorkBuddy安装'
    kit.mkdir()
    native = kit / ('新媒体数字员工技能_' + release + '.zip')
    with zipfile.ZipFile(native, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, path in sorted(files(skill).items()):
            archive.write(path, name)
    save(kit / 'skill-files.json', {'schema': 'workbuddy-skill-files/1', 'release': release, 'method_content_sha256': version['method_content_sha256'], 'files': [{'path': name, 'sha256': sha(path), 'bytes': path.stat().st_size} for name, path in sorted(files(skill).items())]})
    for name in ('workbuddy_init.py', 'Initialize-WorkBuddy.ps1'):
        shutil.copy2(bundle / 'distribution' / name, kit / name)
    helper = read(bundle / 'installer-runtime.ps1')
    write(kit / 'offline-helpers.ps1', helper[helper.index('function Assert-SzygHash'):helper.index('function Test-SzygPython')])
    sources = json.loads(read(bundle / 'INSTALLER-SOURCES.json'))
    for arch, row in sources['windows'].items():
        name = 'python-' + sources['python_version'] + '-embed-' + arch + '.zip'
        source = bundle / 'runtime' / name
        if sha(source) != row['sha256']:
            raise ValueError('Runtime archive differs from the recorded official file.')
        target = kit / 'runtime' / name
        target.parent.mkdir(exist_ok=True)
        shutil.copy2(source, target)
        with zipfile.ZipFile(target) as archive:
            license_name = next(name for name in archive.namelist() if name.lower().endswith('license.txt'))
            write(kit / 'licenses' / ('Python-' + arch + '-LICENSE.txt'), archive.read(license_name).decode('utf-8'))
    save(kit / 'RUNTIME-SOURCES.json', sources)
    save(kit / '版本信息.json', {**version, 'host': 'WorkBuddy', 'native_skill_zip': native.name, 'native_skill_sha256': sha(native)})
    write(kit / '安装说明.txt', '在WorkBuddy添加技能中上传“' + native.name + '”。导入后让助手找到实际Skill目录，并运行本目录Initialize-WorkBuddy.ps1 -SkillRoot "实际导入目录"。已有业务资料和本地改进先保留并迁移。\n')
    save(kit / 'offline-files.json', {'schema': 'workbuddy-offline-files/1', 'edition': release, 'release': release, 'default_workspace': '数字员工团队/WorkBuddy新媒体', 'files': [{'path': name, 'sha256': sha(path), 'bytes': path.stat().st_size} for name, path in sorted(files(kit).items())]})
    return {'prepared': True, 'release': release, 'host': 'WorkBuddy', 'import_zip': str(native), 'initialization_script': str(kit / 'Initialize-WorkBuddy.ps1'), 'next': '在WorkBuddy中上传import_zip，定位实际导入目录，再运行initialization_script -SkillRoot "实际导入目录"。', 'method_content_sha256': version['method_content_sha256']}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package-root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.package_root, args.output), ensure_ascii=False, indent=2))
