"""Build all-skills and per-skill offline kits from one audited catalog."""
from pathlib import Path
import argparse,hashlib,json,shutil,sys,zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from install import validate_bundle
from distribution.workspaces import read,save
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def files(root):return {p.relative_to(root).as_posix():p for p in root.rglob('*') if p.is_file() and not set(p.parts)&{'.git','__pycache__'} and p.suffix not in {'.pyc','.pyo'}}
def seal(root,release):save(root/'manifest.json',{'schema':'independent-skills-bundle/1','release':release,'files':[{'path':n,'sha256':sha(p),'bytes':p.stat().st_size} for n,p in sorted(files(root).items()) if n!='manifest.json']})
def build(output,cache):
    validate_bundle(ROOT);catalog=read(ROOT/'catalog.json');release=catalog['release'];output=Path(output).resolve()
    if output.exists() or output.is_relative_to(ROOT) or ROOT.is_relative_to(output):raise ValueError('使用仓库之外的新输出目录，保留封存版本。')
    output.mkdir(parents=True);assets=[]
    for row in [None,*catalog['skills']]:
        label=row['label'] if row else '全部岗位';key=row['name'] if row else 'all-skills';stage=output/'.staging'/key;stage.mkdir(parents=True)
        for n,p in files(ROOT).items():
            if n.startswith('skills/') and row and n.split('/')[1]!=row['name']:continue
            target=stage/n;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
        if row:
            save(stage/'catalog.json',{**catalog,'skills':[row]})
            (stage/'README.md').write_text('# '+row['label']+'独立Skill\n\nSkill：'+row['name']+' '+row['version']+'；发行：'+release+'。\n\n本包只包含本岗位，可单独维护和安装。完整解压，读取[先读我](先读我.md)，将安装提示词.txt交给Codex或WorkBuddy。具体方法见[本岗位SKILL.md]('+row['entry']+')。跨岗位制作按实际任务另装必要Skill。\n',encoding='utf-8')
        sources=read(ROOT/'INSTALLER-SOURCES.json')
        for arch,meta in sources['windows'].items():
            name='python-'+sources['python_version']+'-embed-'+arch+'.zip';source=Path(cache)/name
            if sha(source)!=meta['sha256']:raise ValueError('官方运行时摘要不一致')
            (stage/'runtime').mkdir(exist_ok=True);shutil.copy2(source,stage/'runtime'/name)
        prompt='请帮我安装或升级这个数字员工Skill安装包，发行'+release+'。完整解压并读取先读我.md，按我正在使用的软件安装'+(row['label'] if row else '所需的独立岗位Skill，没有指定则安装全部')+'，创建或接入我的项目，保留已有资料和本地改进；有旧版先备份、比对迁移。完成后告诉我每个实际安装的Skill名称、版本和使用入口。'
        if row is None:prompt=(ROOT/'安装提示词.txt').read_text(encoding='utf-8-sig').strip()
        (stage/'安装提示词.txt').write_bytes((prompt+'\n').encode('utf-8'))
        seal(stage,release);validate_bundle(stage)
        name=('szyg-digital-employees-independent-'+release+'.zip') if row is None else label+'_v'+row['version']+'_'+release+'.zip';archive=output/name
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for n,p in sorted(files(stage).items()):z.write(p,n)
        with zipfile.ZipFile(archive) as z:
            if z.testzip():raise ValueError('ZIP CRC失败')
            for n,p in files(stage).items():
                if hashlib.sha256(z.read(n)).hexdigest()!=sha(p):raise ValueError('ZIP字节不一致')
        digest=sha(archive);archive.with_suffix('.zip.sha256').write_text(digest+'  '+name+'\n',encoding='utf-8')
        alias='新媒体数字员工_'+release+'_独立Skill合集.zip' if row is None else label+'_v'+row['version']+'_'+release+'.zip'
        if archive!=output/alias:shutil.copy2(archive,output/alias)
        assets.append({'name':name,'wechat_name':alias,'skill':row['name'] if row else None,'label':label,'version':row['version'] if row else None,'bytes':archive.stat().st_size,'sha256':digest})
    save(output/'release-assets.json',{'release':release,'architecture':'independent-skills','skills':len(catalog['skills']),'assets':assets})
    print(json.dumps({'release':release,'packages':len(assets),'output':str(output)},ensure_ascii=False))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--runtime-cache',type=Path,required=True);a=p.parse_args();build(a.output,a.runtime_cache)
