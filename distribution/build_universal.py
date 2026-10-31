"""Build one forwardable installation ZIP for Codex and WorkBuddy."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]

def read(path):
    return path.read_text(encoding='utf-8-sig')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def files(root):
    return {p.relative_to(root).as_posix(): p for p in root.rglob('*') if p.is_file() and '.git' not in p.parts}

def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--runtime-cache', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    if out.is_relative_to(ROOT) or ROOT.is_relative_to(out):
        raise ValueError('Build output must be outside the public repository.')
    out.mkdir(parents=True, exist_ok=True)
    spec = importlib.util.spec_from_file_location('installer', ROOT / 'install.py')
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    installer.validate_bundle(ROOT)
    version = json.loads(read(ROOT / 'VERSION.json'))
    release = version['release']
    stage = out / '.staging' / 'universal'
    if stage.exists():
        raise ValueError('Preserve an existing staging directory.')
    stage.mkdir(parents=True)
    for name, source in files(ROOT).items():
        target = stage / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    sources = json.loads(read(ROOT / 'INSTALLER-SOURCES.json'))
    runtime = stage / 'runtime'
    runtime.mkdir()
    for arch, row in sources['windows'].items():
        name = 'python-' + sources['python_version'] + '-embed-' + arch + '.zip'
        source = args.runtime_cache / name
        if not source.is_file() or sha(source) != row['sha256']:
            raise ValueError('Missing or different official Python archive: ' + name)
        shutil.copy2(source, runtime / name)
    manifest = json.loads(read(ROOT / 'manifest.json'))
    manifest['files'] = [{'path': name, 'sha256': sha(path), 'bytes': path.stat().st_size} for name, path in sorted(files(stage).items()) if name != 'manifest.json']
    save(stage / 'manifest.json', manifest)
    installer.validate_bundle(stage)
    archive = out / ('szyg-new-media-marketing-universal-' + release + '.zip')
    if archive.exists():
        raise ValueError('Preserve the sealed archive.')
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as output:
        for name, path in sorted(files(stage).items()):
            output.write(path, name)
    with zipfile.ZipFile(archive) as output:
        for name, path in files(stage).items():
            assert hashlib.sha256(output.read(name)).hexdigest() == sha(path), name
    digest = sha(archive)
    archive.with_suffix('.zip.sha256').write_text(digest + '  ' + archive.name + '\n', encoding='utf-8')
    alias = '新媒体数字员工_' + release + '_通用版.zip'
    shutil.copy2(archive, out / alias)
    assert sha(out / alias) == digest
    assets = [{'name': archive.name, 'wechat_name': alias, 'bytes': archive.stat().st_size, 'sha256': digest}]
    bootstrap = out / 'Install-New-Media-Team-Windows.cmd'
    shutil.copy2(ROOT / bootstrap.name, bootstrap)
    bootstrap.with_suffix('.cmd.sha256').write_text(sha(bootstrap) + '  ' + bootstrap.name + '\n', encoding='utf-8')
    assets.append({'name': bootstrap.name, 'bytes': bootstrap.stat().st_size, 'sha256': sha(bootstrap)})
    result = {**version, 'assets': assets, 'external_installation_packages': 1, 'canonical_skill_trees': 1, 'supported_hosts': ['Codex', 'WorkBuddy'], 'single_forwardable_zip': True, 'wechat_copies_byte_identical': True}
    save(out / 'release-assets.json', result)
    print(json.dumps({'release': release, 'archive': str(archive), 'bytes': archive.stat().st_size, 'external_installation_packages': 1, 'canonical_skill_trees': 1}, ensure_ascii=False))

if __name__ == '__main__':
    main()
