"""Prepare native WorkBuddy ZIPs from selected independent canonical skills."""
from pathlib import Path
import argparse,hashlib,json,shutil,sys,zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from install import validate_bundle
from distribution.workspaces import read,save,hashes

def prepare(output,names=None):
    manifest=validate_bundle(ROOT);output=Path(output).resolve()
    if output.exists() or output.is_relative_to(ROOT):raise ValueError('使用包目录之外的新输出目录，保留已有文件。')
    catalog=read(ROOT/'catalog.json')['skills'];selected=[r for r in catalog if not names or r['name'] in names or r['id'] in names or r['label'] in names]
    if not selected or names and not all(any(n in (r['name'],r['id'],r['label']) for r in selected) for n in names):raise ValueError('未找到所选Skill')
    output.mkdir(parents=True);rows=[]
    for row in selected:
        source=ROOT/'skills'/row['name'];stage=output/'.staging'/row['name'];shutil.copytree(source,stage)
        entry=stage/'SKILL.md';text=entry.read_text(encoding='utf-8-sig');description=text.split('description:',1)[1].splitlines()[0].strip()
        adapted='---\nname: '+row['name']+'\ndisplay_name: '+json.dumps(row['label'],ensure_ascii=False)+'\ndisplay_name_en: '+json.dumps(row['name'])+'\ndescription: '+description+'\ndescription_zh: '+description+'\ndescription_en: '+json.dumps('Independent '+row['name']+' skill for the current project.')+'\nversion: '+json.dumps(row['version'])+'\nauthor: "Digital Employee Skills"\nmetadata:\n  version: '+json.dumps(row['version'])+'\n  release: '+json.dumps(manifest['release'])+'\n---'+text.split('---',2)[2]
        entry.write_text(adapted,encoding='utf-8')
        save(stage/'.workbuddy-import.json',{'name':row['name'],'release':manifest['release'],'files':hashes(stage)})
        name=row['label']+'_v'+row['version']+'_WorkBuddy.zip';archive=output/name
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
            for p in sorted(stage.rglob('*')):
                if p.is_file():z.write(p,p.relative_to(stage).as_posix())
        rows.append({'name':row['name'],'label':row['label'],'version':row['version'],'archive':str(archive),'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'import_files':read(stage/'.workbuddy-import.json')['files'],'id':row['id']})
    save(output/'prepared-skills.json',{'release':manifest['release'],'skills':rows})
    for name in ('workspaces.py','workbuddy_init.py'):shutil.copy2(ROOT/'distribution'/name,output/name)
    for name in ('installer-runtime.ps1','Initialize-WorkBuddy.ps1'):shutil.copy2(ROOT/name,output/name)
    shutil.copy2(ROOT/'INSTALLER-SOURCES.json',output/'INSTALLER-SOURCES.json')
    if (ROOT/'runtime').is_dir():shutil.copytree(ROOT/'runtime',output/'runtime')
    (output/'导入说明.txt').write_text('逐个上传所选岗位的WorkBuddy ZIP。导入后让助手定位每个实际Skill目录，按英文名称建立JSON映射，再运行workbuddy_init.py --skills-map 映射.json --workspace-root 新团队目录。只导入一个时可用--skill-root 实际目录 --skill 英文名称。客户端要求点击时按界面完成。\n',encoding='utf-8')
    staging=output/'.staging'
    assert staging.resolve().is_relative_to(output) and staging.parent==output
    shutil.rmtree(staging)
    return {'prepared':True,'release':manifest['release'],'output':str(output),'skills':[{k:r[k] for k in ('name','archive','version','sha256')} for r in rows]}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--skill',action='append');a=p.parse_args()
    try:print(json.dumps(prepare(a.output,a.skill),ensure_ascii=False,indent=2))
    except Exception as e:p.exit(2,str(e)+'\n')
