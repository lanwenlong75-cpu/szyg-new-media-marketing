"""Install one unified Codex skill with integrity checks and rollback."""
from pathlib import Path,PurePosixPath
from datetime import datetime
import argparse,hashlib,importlib.util,json,os,shutil,subprocess,sys,uuid
NAME='szyg-new-media-marketing'
LEGACY={'szyg-team-orchestrator','szyg-digital-employee-builder','szyg-short-video-director','szyg-wechat-editor','szyg-poster-designer','szyg-fullstack-engineer','szyg-private-domain-advisor','szyg-new-media-ops','szyg-duli-motion-video','szyg-duli-motion-video-legacy','szyg-product-manager','szyg-archive-social-video','szyg-archive-social-account'}
def require(ok,msg):
 if not ok:raise ValueError(msg)
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def no_links(p):require(not any(x.is_symlink() or getattr(x,'is_junction',lambda:False)() for x in [p,*p.parents]),'目录含链接，先由当前助手核对，安装器保留原样')
def hashes(root):return {p.relative_to(root).as_posix():sha(p) for p in root.rglob('*') if p.is_file() and not any(x in p.parts for x in ['node_modules','.venv','__pycache__']) and p.name!='.release-baseline.json' and p.suffix not in ['.pyc','.pyo']}
def default_skills(home=None):
 home=Path(home) if home else Path.home();choices=[home/'.agents/skills',home/'.codex/skills']
 active=[p for p in choices if any((p/n/'SKILL.md').is_file() for n in LEGACY|{NAME})]
 require(len(active)<=1,'两处技能目录均有本套入口；先核对实际安装并保留本地已学方法，当前未改动任何目录')
 if active:return active[0]
 return Path(os.environ['CODEX_HOME']).expanduser()/'skills' if os.environ.get('CODEX_HOME') else choices[0]
def validate_bundle(bundle):
 manifest=read(bundle/'manifest.json');require(manifest['skill']==NAME and manifest['release']=='2026.10.31.3','安装包标识无效')
 seen=set()
 for item in manifest['files']:
  value=item['path'];p=PurePosixPath(value);require(not p.is_absolute() and '..' not in p.parts and '\\' not in value and ':' not in value and value not in seen,'安装包路径不合法')
  seen.add(value);target=bundle/Path(*p.parts);no_links(target)
  require(target.resolve().is_relative_to(bundle) and target.is_file() and sha(target)==item['sha256'],'文件完整性校验失败：'+value)
 actual={p.relative_to(bundle).as_posix() for p in bundle.rglob('*') if p.is_file() and p!=bundle/'manifest.json' and '.git' not in p.relative_to(bundle).parts}
 require(actual==seen,'安装包有缺失或未登记文件')
 require(len(list((bundle/'skills').rglob('SKILL.md')))==1,'安装包须仅含一个可发现的技能入口')
 return manifest
def remove_created(p,parent,prefix):
 p=Path(p);parent=Path(parent);require(p.resolve().is_relative_to(parent.resolve()) and p.resolve()!=parent.resolve() and p.name.startswith(prefix),'临时目录清理边界不匹配');no_links(p)
 if p.exists():shutil.rmtree(p)
def install(bundle,skills_root,workspace,upgrade=False,archive_legacy=False,home=None):
 bundle=Path(bundle).resolve();skills_root=Path(skills_root).expanduser().resolve();workspace=Path(workspace).expanduser().resolve();home=Path(home) if home else Path.home()
 no_links(skills_root);no_links(workspace)
 require(skills_root!=Path(skills_root.anchor) and workspace!=Path(workspace.anchor),'禁止把盘符根目录作为安装目标')
 require(not skills_root.is_relative_to(bundle) and not bundle.is_relative_to(skills_root),'安装包和技能目标需分开')
 require(not workspace.is_relative_to(skills_root) and not skills_root.is_relative_to(workspace),'业务工作区不能放在技能扫描目录中')
 manifest=validate_bundle(bundle);target=skills_root/NAME;existing=target.exists()
 if existing:
  require(upgrade,'已有同名入口，已保留。需要升级时使用--upgrade-existing')
  no_links(target);baseline=target/'.release-baseline.json'
  require(baseline.is_file() and hashes(target)==read(baseline)['files'],'已有工作版有本地改进或没有安装基线，先让助手比对合并；当前版保持原样')
  require(read(baseline)['release']==manifest['release'],'已有不同版本统一入口。先由助手核对并迁移岗位注册表、账本及本地方法；当前版保持原样')
 legacy=[]
 for parent in list(dict.fromkeys([skills_root,home/'.agents/skills',home/'.codex/skills'])):
  for name in sorted(LEGACY):
   p=parent/name
   if p.exists():no_links(p);legacy.append(p)
 require(not legacy or archive_legacy,'发现旧独立入口。可用--archive-legacy完整归档到扫描目录外，业务工作区保留')
 preexisting_workspace=workspace.exists() and any(workspace.iterdir())
 if preexisting_workspace:
  marker=workspace/'.new-media-team.json';require(marker.is_file() and Path(read(marker)['skill_root']).resolve()==target,'已有非本团队业务目录，保留原样；请选择空团队目录，业务项目另用bind接入')
 skills_root.mkdir(parents=True,exist_ok=True)
 stage=skills_root.parent/('.new-media-stage-'+uuid.uuid4().hex);stage.mkdir();pending=stage/NAME
 shutil.copytree(bundle/'skills'/NAME,pending);require(hashes(pending)==hashes(bundle/'skills'/NAME),'暂存文件校验失败')
 save(pending/'.release-baseline.json',{'release':manifest['release'],'files':hashes(pending)})
 archive=skills_root.parent/'skill-backups'/('new-media-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6]);moved=[];installed=False
 try:
  for idx,p in enumerate(([target] if existing else [])+legacy):
   require(p.resolve().parent in {x.resolve() for x in [skills_root,home/'.agents/skills',home/'.codex/skills']},'旧入口不在明确技能目录')
   dest=archive/(str(idx)+'-'+p.name);require(dest.resolve().is_relative_to(archive.resolve()),'归档路径越界');dest.parent.mkdir(parents=True,exist_ok=True)
   before=hashes(p);shutil.move(str(p),str(dest));require(hashes(dest)==before,'旧入口归档摘要不一致');moved.append((p,dest))
  pending.rename(target);installed=True
  if preexisting_workspace:initialization={'existing_workspace_preserved':True,'team_root':str(workspace)}
  else:
   result=subprocess.run([sys.executable,'-X','utf8','-B',str(target/'scripts/portable.py'),'init','--root',str(workspace)],capture_output=True,text=True,encoding='utf-8')
   require(result.returncode==0,'团队初始化失败：'+result.stderr[-1400:]);initialization=json.loads(result.stdout)
  result=subprocess.run([sys.executable,'-X','utf8','-B',str(target/'scripts/portable.py'),'doctor'],capture_output=True,text=True,encoding='utf-8');require(result.returncode==0,'安装后体检无法运行')
  receipt={'installed':True,'skill':str(target),'release':manifest['release'],'method_content_sha256':read(bundle/'VERSION.json')['method_content_sha256'],'source_entry_version':manifest['source_entry_version'],'team':str(workspace),'governance':str(workspace/'新媒体主管'),'old_entry_backups':[{'original':str(a),'backup':str(b)} for a,b in moved],'initialization':initialization,'preflight':json.loads(result.stdout),'source_standards_preserved':True,'recipient_business_accepted':False,'next':'在Codex打开团队目录或相应岗位项目，下一轮会话读取新入口；缺依赖按预检报告配置，先以同事真实素材做代表段验收'}
  save(workspace/'安装回执.json',receipt);return receipt
 except Exception:
  if installed and target.exists():remove_created(target,skills_root,NAME)
  for original,dest in reversed(moved):
   require(not original.exists(),'恢复位置已被占用，请核对备份');shutil.move(str(dest),str(original))
  if not preexisting_workspace and workspace.exists():remove_created(workspace,workspace.parent,workspace.name)
  raise
 finally:
  if stage.exists():remove_created(stage,skills_root.parent,'.new-media-stage-')
def write_start_guide(receipt):
 team=Path(receipt['team']);guide=team/'START-HERE.md'
 if not guide.exists():
  projects=read(team/'.new-media-team.json')['projects']
  lines=['# 你的数字员工团队 · '+receipt['release'],'','## 先打开这个团队','',
   '在Codex中添加本地项目，选择这个实际文件夹：','',str(team),'',
   '项目名称可填写“我的数字员工团队”。如想先使用主管，也可以只添加下表的新媒体主管文件夹。',
   '本安装器创建磁盘工作区和角色绑定；首次在Codex侧栏添加项目由你选择文件夹完成。','',
   '## 像岗位列表一样创建项目','', '| 建议项目显示名 | 选择的文件夹 |','|---|---|']
  for row in projects:lines.append('| 数字员工-'+row['root'].replace('\\','/').rsplit('/',1)[-1]+' | '+row['root']+' |')
  lines += ['','添加时选对应岗位目录，先把它设为主文件夹；资料保持原位。项目名称与磁盘文件夹名称可以不同。','',
   '## 命名和重命名','',
   '新项目在名称栏填写“数字员工-短视频编导”等便于识别的名称。已有项目从名称旁菜单的“重命名/编辑项目”调整显示名称，入口以当前版本界面为准；保持已绑定文件夹不变。',
   '要移动或改磁盘文件夹名称时，先让主管核对岗位注册表、项目配置和旧路径引用，迁移后检查；不要把只改侧栏显示名当成磁盘迁移。','',
   '## 发出第一条需求','',
   '在主管项目发：请读取本项目配置和总入口，检查团队十四项能力与岗位绑定，列出缺少的工具。先帮我梳理本次任务需要的岗位，服务对象和账号从我的资料读取。','',
   '在编导项目发：你作为本项目短视频编导，先读当前角色和方法。我接下来会提供自己的资料，请先核对素材再推进本次内容。','',
   '## 添加已有业务目录','',
   '把这句交给Codex并替换目录与岗位：请将我的已有目录接入当前数字员工团队，岗位为EDITOR。使用已安装入口scripts/portable.py bind，主管目录读取本团队实际位置。保留已有AGENTS、资料与本地方法，完成后运行hub.py check。','',
   'Skill未出现时新建一条聊天或重新打开Codex。缺少剪辑、图像或发布条件时按安装回执补齐；已安装不代表真实成品已经验收。','']
  guide.write_text('\n'.join(lines),encoding='utf-8')
 receipt['start_here']=str(guide);save(team/'安装回执.json',receipt)
 return receipt

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--skills-root',type=Path);p.add_argument('--workspace-root',type=Path);p.add_argument('--upgrade-existing',action='store_true');p.add_argument('--archive-legacy',action='store_true');p.add_argument('--home',type=Path,help=argparse.SUPPRESS);a=p.parse_args()
 try:
  home=(a.home or Path.home()).expanduser().resolve();skills=a.skills_root or default_skills(home);workspace=a.workspace_root or home/'数字员工团队/Codex新媒体'
  print(json.dumps(write_start_guide(install(Path(__file__).resolve().parent,skills,workspace,a.upgrade_existing,a.archive_legacy,home)),ensure_ascii=False,indent=2))
 except (OSError,ValueError,KeyError,TypeError) as e:p.exit(2,str(e)+'\n')
if __name__=='__main__':main()
