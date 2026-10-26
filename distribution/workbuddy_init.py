"""Initialize workspaces for an already imported WorkBuddy skill; no network."""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys

def read(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def save(path,value): Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skill-root',type=Path,required=True)
    parser.add_argument('--workspace-root',type=Path,required=True)
    args=parser.parse_args();skill=args.skill_root.resolve();team=args.workspace_root.expanduser().resolve()
    manifest=read(Path(__file__).with_name('skill-files.json'))
    for row in manifest['files']:
        target=(skill/row['path']).resolve()
        if not target.is_relative_to(skill) or not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest()!=row['sha256']:
            raise ValueError('Imported skill differs from this offline edition: '+row['path'])
    if team==skill or team.is_relative_to(skill) or skill.is_relative_to(team): raise ValueError('Keep the team and imported skill in separate folders')
    prior_receipt=team/'WorkBuddy安装回执.json'
    if (team/'.new-media-team.json').exists():
        if not prior_receipt.is_file(): raise ValueError('Existing team has no WorkBuddy release receipt. Back up and verify its registry and feedback ledgers before migration.')
        prior=read(prior_receipt)
        if prior.get('release',prior.get('source_public_release'))!=manifest['release']:
            raise ValueError('Existing team uses a different release. Preserve business files and learned methods; compare and migrate its registry and feedback ledgers before reinitializing.')
    result=subprocess.run([sys.executable,'-X','utf8','-B',str(skill/'scripts/portable.py'),'init','--root',str(team)],capture_output=True,text=True,encoding='utf-8')
    if result.returncode: raise ValueError(result.stderr[-1600:] or result.stdout[-1600:])
    projects=read(team/'.new-media-team.json')['projects']
    if len(projects)!=14: raise ValueError('Expected fourteen real project bindings')
    checks=[]
    for project in projects:
        value=subprocess.run([sys.executable,'-X','utf8','-B',str(skill/'scripts/hub.py'),'check','--project-root',project['root']],capture_output=True,text=True,encoding='utf-8')
        if value.returncode or not json.loads(value.stdout)['ok']: raise ValueError('Project binding failed: '+project['root'])
        checks.append(json.loads(value.stdout))
    guide=team/'START-HERE-WorkBuddy.md'
    if not guide.exists():
        lines=['# WorkBuddy 新媒体团队 · '+manifest['release'],'','在WorkBuddy中选择下面某个岗位目录作为本次工作区。先在技能页面启用新媒体营销数字员工。',
               '第一条需求：读取当前工作区AGENTS.md、.agents/new-media-profile.json与已安装Skill，按本项目岗位和我的真实资料开始工作。',
               '项目或任务显示名可填写“数字员工-岗位名”；改显示名不需要改磁盘路径。搬迁磁盘目录需重新绑定并验证。','',
               '| 岗位名称 | 工作区目录 |','|---|---|']
        for row in projects: lines.append('| 数字员工-'+Path(row['root']).name+' | '+row['root']+' |')
        lines+=['','Skill入口：'+str(skill/'SKILL.md'),'Python运行时：'+sys.executable,'',
                '安装与基础脚本可离线执行；WorkBuddy模型、联网检索、图像生成、账号发布、专业工具和素材仍按接收者的实际环境配置。',
                '原有方法和多种风格保留，实际成品仍按本期素材验收。','']
        guide.write_text('\n'.join(lines),encoding='utf-8')
    receipt={'host':'WorkBuddy','release':manifest['release'],'source_public_release':manifest['release'],'offline_edition':manifest['release'],'method_content_sha256':manifest['method_content_sha256'],'skill':str(skill),'team':str(team),'python':sys.executable,
             'start_here':str(guide),'role_bindings':len(checks),'files_verified':len(manifest['files']),
             'skill_files_modified':False,'native_client_import_verified':False,'business_quality_accepted':False,'network_required_for_setup':False}
    save(team/'WorkBuddy安装回执.json',receipt)
    print(json.dumps(receipt,ensure_ascii=False,indent=2))

if __name__=='__main__':
    try: main()
    except (OSError,ValueError,KeyError,TypeError) as error: sys.exit(str(error))
