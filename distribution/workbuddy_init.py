"""Verify actual native import locations and initialize selected role projects."""
from pathlib import Path
import argparse,json,hashlib,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from workspaces import read,initialize,save
ROOT=Path(__file__).resolve().parent

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--skills-map',type=Path);p.add_argument('--skill-root',type=Path);p.add_argument('--skill');p.add_argument('--workspace-root',type=Path,required=True);a=p.parse_args()
    prepared=read(ROOT/'prepared-skills.json')
    mapping=read(a.skills_map) if a.skills_map else {a.skill:str(a.skill_root)} if a.skill and a.skill_root else {}
    if not mapping:raise ValueError('提供实际导入目录；不猜测宿主固定路径。')
    rows=[]
    for name,location in mapping.items():
        row=next((r for r in prepared['skills'] if r['name']==name),None)
        if not row:raise ValueError('未准备此Skill：'+str(name))
        skill=Path(location).expanduser().resolve()
        for relative,digest in row['import_files'].items():
            target=(skill/relative).resolve()
            if not target.is_relative_to(skill) or not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest()!=digest:raise ValueError('实际导入Skill缺失或有本地改动，保留当前状态：'+name+'/'+relative)
        rows.append({k:row[k] for k in ('id','name','label','version')}|{'entry':str(skill/'SKILL.md')})
    result=initialize(a.workspace_root,rows,prepared['release'])
    receipt={'host':'WorkBuddy','release':prepared['release'],'skills':rows,'initialization':result,'native_ui_verified':False,'business_quality_accepted':False}
    save(a.workspace_root/'WorkBuddy安装回执.json',receipt)
    print(json.dumps(receipt,ensure_ascii=False,indent=2))
if __name__=='__main__':
    try:main()
    except Exception as e:print(str(e),file=sys.stderr);raise SystemExit(2)
