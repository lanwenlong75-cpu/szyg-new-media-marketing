"""Install selected independent skills, preserving local methods and projects."""
from pathlib import Path
import argparse,hashlib,json,shutil,sys,uuid,time
from datetime import datetime
sys.path.insert(0,str(Path(__file__).resolve().parent))
from distribution.workspaces import initialize,hashes,read,save

ROOT=Path(__file__).resolve().parent
def require(ok,message):
    if not ok:raise ValueError(message)
def no_links(path):
    require(not any(p.is_symlink() or getattr(p,'is_junction',lambda:False)() for p in (path,*path.parents)),'目标经过链接，先核对真实目录。')
def rename(source,target):
    for attempt in range(6):
        try:source.rename(target);return
        except PermissionError:
            if attempt==5:raise
            time.sleep(0.2*(attempt+1))
def validate_bundle(bundle):
    bundle=Path(bundle).resolve();manifest=read(bundle/'manifest.json')
    require(manifest['schema']=='independent-skills-bundle/1','安装包标识无效')
    files={p.relative_to(bundle).as_posix():p for p in bundle.rglob('*') if p.is_file() and '.git' not in p.parts and p!=bundle/'manifest.json' and '__pycache__' not in p.parts and p.suffix not in {'.pyc','.pyo'}}
    require(set(files)=={r['path'] for r in manifest['files']},'包内文件清单不一致')
    for row in manifest['files']:
        path=files[row['path']];require(not path.is_symlink() and path.resolve().is_relative_to(bundle),'包内文件越界')
        require(hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256'],'包内文件摘要不一致：'+row['path'])
    return manifest

def install(bundle,skills_root,workspace=None,names=None):
    bundle=Path(bundle).resolve();skills_root=Path(skills_root).expanduser().resolve()
    no_links(skills_root);manifest=validate_bundle(bundle);catalog=read(bundle/'catalog.json')['skills']
    selected=[r for r in catalog if not names or r['name'] in names or r['id'] in names or r['label'] in names]
    require(selected and (not names or all(any(n in (r['name'],r['id'],r['label']) for r in selected) for n in names)),'未找到所选Skill，请查看catalog.json')
    require(not skills_root.is_relative_to(bundle) and not bundle.is_relative_to(skills_root),'安装目标与包目录不能重叠')
    legacy=skills_root/'szyg-new-media-marketing'
    require(not legacy.exists(),'检测到旧统一入口。请助手先备份、比对并迁移现有项目绑定与反馈基线，再停用旧入口；没有改动现有文件。')
    if workspace:
        workspace=Path(workspace).expanduser().resolve();no_links(workspace)
        require(not workspace.is_relative_to(skills_root) and not skills_root.is_relative_to(workspace),'资料目录与Skill目录不能重叠')
        if workspace.exists() and any(workspace.iterdir()):
            marker=workspace/'.independent-skills-team.json'
            require(marker.is_file() and read(marker)['release']==manifest['release'],'已有业务目录或另一发行保持原样；先迁移或选空目录。')
    # Complete every preflight before changing any skill.
    for row in selected:
        target=skills_root/row['name'];no_links(target)
        if target.exists():
            baseline=target/'.release-baseline.json'
            require(baseline.is_file() and hashes(target)==read(baseline)['files'],'已有Skill含本地改进或无基线，先比对迁移：'+row['name'])
    retired=[]
    for name,known in read(bundle/'legacy-function-baselines.json')['skills'].items():
        target=skills_root/name;no_links(target)
        if not target.exists():continue
        require(any(r['id']=='OPS' for r in selected),'旧功能Skill需要随新媒体运营岗位迁移；请选OPS或整套安装，当前文件保持原样。')
        baseline=target/'.release-baseline.json'
        require(baseline.is_file() and hashes(target)==read(baseline)['files']==known,
                '旧功能Skill有本地改进或无可信基线，先合并到运营岗位；未改动现有文件：'+name)
        retired.append(target)
    skills_root.mkdir(parents=True,exist_ok=True)
    transaction=skills_root.parent/'skill-backups'/('independent-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8])
    transaction.mkdir(parents=True)
    stages=[];installed=[];backups=[];retired_backups=[]
    workspace_was_empty=workspace and (not workspace.exists() or not any(workspace.iterdir()))
    try:
        for row in selected:
            target=skills_root/row['name'];stage=skills_root/('.pending-'+row['name']+'-'+uuid.uuid4().hex[:8])
            shutil.copytree(bundle/'skills'/row['name'],stage);stages.append(stage)
            require(hashes(stage)==row['files'],'Skill文件校验失败：'+row['name'])
            save(stage/'.release-baseline.json',{'release':manifest['release'],'skill_version':row['version'],'files':hashes(stage)})
        for row,stage in zip(selected,stages):
            target=skills_root/row['name']
            if target.exists():
                dest=transaction/row['name'];rename(target,dest);backups.append((target,dest))
            rename(stage,target);installed.append(target)
        for target in retired:
            dest=transaction/'retired-functions'/target.name;dest.parent.mkdir(parents=True,exist_ok=True)
            rename(target,dest);retired_backups.append((target,dest))
        bound=[{**r,'entry':str(skills_root/r['name']/'SKILL.md')} for r in selected]
        team=initialize(workspace,bound,manifest['release']) if workspace else None
        receipt={'installed':True,'release':manifest['release'],'skills':[{k:r[k] for k in ('id','name','label','version','entry')} for r in bound],'team':str(workspace) if workspace else None,'initialization':team,'backup_directory':str(transaction),'retired_function_skills':[{'name':t.name,'backup':str(d)} for t,d in retired_backups],'business_quality_accepted':False}
        if workspace:save(workspace/'安装回执.json',receipt)
        return receipt
    except Exception:
        for target,dest in reversed(retired_backups):rename(dest,target)
        for target in reversed(installed):
            require(target.parent==skills_root,'回滚路径越界');shutil.rmtree(target)
        for target,dest in reversed(backups):rename(dest,target)
        if workspace_was_empty and workspace and workspace.exists():
            # Only a workspace created by this transaction can be removed.
            require(workspace.is_absolute() and workspace!=workspace.parent and not workspace.is_relative_to(skills_root),'回滚目录越界')
            shutil.rmtree(workspace)
        raise
    finally:
        for stage in stages:
            if stage.exists():
                require(stage.parent==skills_root and stage.name.startswith('.pending-'),'暂存路径越界');shutil.rmtree(stage)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--skills-root',type=Path,default=Path.home()/'.codex/skills');p.add_argument('--workspace-root',type=Path)
    p.add_argument('--skill',action='append',help='Skill英文名、岗位名或ID，可重复；不提供则安装包内全部')
    p.add_argument('--home',type=Path);p.add_argument('--upgrade-existing',action='store_true');p.add_argument('--archive-legacy',action='store_true')
    a=p.parse_args()
    if a.home:a.skills_root=a.home/'.codex/skills'
    if not a.workspace_root:a.workspace_root=(a.home or Path.home())/'Documents/新媒体数字员工'
    try:print(json.dumps(install(ROOT,a.skills_root,a.workspace_root,a.skill),ensure_ascii=False,indent=2));return 0
    except Exception as e:print(json.dumps({'installed':False,'error':str(e)},ensure_ascii=False),file=sys.stderr);return 2
if __name__=='__main__':raise SystemExit(main())
