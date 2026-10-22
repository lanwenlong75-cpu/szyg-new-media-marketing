"""Portable project bindings, recipient-owned workspaces and offline preflight."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,os,re,shutil,subprocess,sys,uuid

HUB=Path(__file__).resolve().parents[1]
NAMES={'SUPERVISOR':'新媒体主管','DIRECTOR':'短视频编导','OPS':'新媒体运营','EDITOR':'公众号编辑','DESIGNER':'海报设计师','PRIVATE':'私域顾问','ENGINEER':'全栈工程师','PRODUCT':'产品经理','MOTION':'视频制作引擎','BUILDER':'数字员工搭建师','ARCHIVE_VIDEO':'单条视频归档','ARCHIVE_ACCOUNT':'账号作品归档','XHS':'小红书运营','COURSEWARE':'课件打造师'}
MARKER='.new-media-team.json'
def require(ok,msg):
 if not ok:raise ValueError(msg)
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def save(p,v):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);temp=p.with_name(p.name+'.tmp');temp.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');temp.replace(p)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def hashes(root):return {p.relative_to(root).as_posix():sha(p) for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ['.pyc','.pyo']}
def version():
 t=(HUB/'SKILL.md').read_text(encoding='utf-8-sig');return re.search(r'^\s+version:\s*["\']?([^\r\n"\']+)',t,re.M)[1]
def no_links(path):
 require(not any(p.is_symlink() or getattr(p,'is_junction',lambda:False)() for p in [path,*path.parents]),'请先核对目录链接，当前工具不会写入链接目标')
def backup(path,root):
 path=Path(path)
 if path.is_file():
  dest=root/'_管理/入口备份'/datetime.now().strftime('%Y%m%d-%H%M%S-%f')/path.name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest)
def bind(root,role,governance):
 root=Path(root).expanduser().resolve();governance=Path(governance).expanduser().resolve();no_links(root)
 require(role in NAMES and root.is_dir(),'请选择实际目录与已登记岗位')
 registry=governance/'00-岗位与协作/skill同步注册表.json';require(registry.is_file(),'主管能力注册表不存在，先初始化团队')
 profile=root/'.agents/new-media-profile.json'
 data={'schema':'new-media-project-profile-v1','role':NAMES[role],'primary_capability':role,'focus':[NAMES[role]+'的实际任务与交付'],'governance_root':str(governance),'registry':str(registry),'business_context_root':str(root),'entry':str(HUB/'SKILL.md'),'entry_version':version(),'activation':'automatic_for_relevant_project_tasks','runtime_mode':'contained_modules_only'}
 if profile.is_file():
  prior=read(profile);require(Path(prior['registry']).resolve()==registry.resolve() and prior['primary_capability']==role,'已有不同团队或岗位绑定，先由当前助手核对，不自动覆盖')
 backup(profile,root);save(profile,data)
 agents=root/'AGENTS.md';old=agents.read_text(encoding='utf-8-sig') if agents.is_file() else '# '+NAMES[role]+'工作区\n'
 block='<!-- szyg-new-media-marketing:start -->\n## 新媒体统一能力\n\n本项目岗位为'+NAMES[role]+'。用户正常提出相关需求时，先读`.agents/new-media-profile.json`，再完整读取`'+str(HUB/'SKILL.md').replace('\\','/')+'`。按实际任务读取内部GUIDE，沿用随包审美、经验和标准；无需用户点名skill。业务对象、账号和素材读取本项目，旧独立入口与其他使用者事实不带入。安装与工具检查不等于成品审美已认可。外部动作与后台任务按本次真实授权。\n<!-- szyg-new-media-marketing:end -->'
 pattern=r'<!-- szyg-new-media-marketing:start -->[\s\S]*?<!-- szyg-new-media-marketing:end -->'
 new=re.sub(pattern,lambda _:block,old) if re.search(pattern,old) else old.rstrip()+'\n\n'+block+'\n'
 backup(agents,root);agents.write_text(new,encoding='utf-8')
 return {'root':str(root),'role':role,'entry':str(HUB/'SKILL.md')}

def init(root):
 root=Path(root).expanduser().resolve();no_links(root)
 marker=root/MARKER
 if marker.is_file():
  prior=read(marker);require(Path(prior['skill_root']).resolve()==HUB,'已有团队属于另一安装，不改变原工作区')
  return {'initialized':False,'existing_preserved':True,**prior}
 require(not root.exists() or not any(root.iterdir()),'新团队目录需要为空，已有业务请用bind增量接入')
 root.mkdir(parents=True,exist_ok=True);gov=root/'新媒体主管'
 registry={'schema':'skill-sync-registry-v1','owner':'新媒体主管','runtime_policy':'contained_modules_only','roles':[{'id':id,'name':name,'source':{'entry':str(HUB/'capabilities'/id.lower()/'GUIDE.md'),'owner':'szyg-new-media-marketing','module':id},'copies':[]} for id,name in NAMES.items()]}
 save(gov/'00-岗位与协作/skill同步注册表.json',registry)
 save(gov/'00-岗位与协作/skill同步记录.json',{'schema':'skill-sync-ledger-v1','records':[]})
 save(gov/'00-岗位与协作/跨电脑同步回执.json',{'records':[],'business_quality_accepted':False})
 members=[];created=[]
 for id,name in NAMES.items():
  project=root/name;project.mkdir(exist_ok=True);module=HUB/'capabilities'/id.lower();require((module/'GUIDE.md').is_file(),'缺少真实能力：'+id)
  employee='EMP-'+uuid.uuid4().hex[:12]
  for folder in ['00-岗位与协作','01-共用知识','02-服务对象','03-任务与交付','04-复盘与改进','_管理']: (project/folder).mkdir(exist_ok=True)
  config={'schema':'digital-employee-config-v1','employee_id':employee,'employee_name':name,'project_display_name':name,'role':id.lower(),'usage_mode':'workspace','default_service_object_id':None,'object_registry':'02-服务对象/服务对象注册表.json','context':{'current_user_data_only':True,'runtime_reading_entries':['README.md']},'worker_skills':[{'name':'szyg-new-media-marketing','entry':str(module/'GUIDE.md'),'capability':id,'primary':True,'reviewed_for_role':True,'runtime_verified':False,'capability_notes':'随包现用方法与工具已安装；当前接收者真实业务效果另验'}],'capability_binding':{'owner':'szyg-new-media-marketing','id':id,'entry':str(module/'GUIDE.md'),'maintenance_root':str(project),'migration_record':'_管理/统一能力迁移.json'},'skill_iteration_policy':{'enabled':True,'rules_file':str(module/'references/数字员工确认规则.md'),'ledger':'_管理/skill迭代记录.json','tool':'_管理/record_skill_iteration.py','tracking':'primary-skill-files-v2'},'live_task_validated':False,'state':'入口已绑定，尚未登记真实服务对象、账号或业务验收'}
  save(project/'00-岗位与协作/员工配置.json',config)
  save(project/config['object_registry'],{'schema':'employee-entities-v1','default_id':None,'objects':[]})
  baseline={'@capability/'+k:v for k,v in hashes(module).items()}
  ledger={'schema':'employee-skill-iterations-v1','tracking':'primary-skill-files-v2','revision':0,'rules':[],'events':[],'working_hashes':baseline}
  frozen=project/'_管理/初始反馈台账.json';save(frozen,ledger);save(project/config['skill_iteration_policy']['ledger'],ledger)
  save(project/config['capability_binding']['migration_record'],{'prior_ledger':str(frozen),'prior_ledger_sha256':sha(frozen),'preserved_revision':0,'module_baseline':baseline,'kind':'recipient_initialization; inherited standards are not recipient feedback'})
  save(project/'_管理/来源复制清单.json',[]);save(project/'_管理/生成清单.json',{'generated':{'00-岗位与协作/员工配置.json':sha(project/'00-岗位与协作/员工配置.json')}});save(project/'_管理/知识依赖检查.json',{'unresolved':[]})
  (project/'README.md').write_text('# '+name+'\n\n已绑定真实内部方法，业务资料与账号尚待接收者提供。先读AGENTS.md及当前项目配置，再执行实际任务。需要服务对象时从用户资料登记，不把空模板算成真实客户或IP。\n',encoding='utf-8')
  (project/'00-岗位与协作/反馈与skill迭代.md').write_text('# 反馈与能力改进\n\n先修当前交付；真实长期反馈或对应版本认可后，用_管理/record_skill_iteration.py修改本员工绑定模块并保留范围、旧版和验证。初始标准在模块references/inherited-standards.md，不当作接收者自己的认可事件。下一次真实任务发生后再记录采用效果。\n',encoding='utf-8')
  (project/'04-复盘与改进/能力迭代记录模板.md').write_text('# 实际能力改进记录\n\n任务与交付、真实反馈、适用对象、原因、方法修改、验证证据、后续真实效果。\n',encoding='utf-8')
  (project/'_管理/record_skill_iteration.py').write_text('import runpy,sys\nsys.path.insert(0,'+repr(str(HUB/'scripts'))+')\nrunpy.run_path('+repr(str(HUB/'scripts/module_iteration.py'))+",run_name='__main__')\n",encoding='utf-8')
  created.append(bind(project,id,gov));members.append({'id':id,'name':name,'kind':'employee','root':str(project),'config':'00-岗位与协作/员工配置.json','purpose':name+'的实际方法、任务与反馈'})
  if id=='DIRECTOR':
   config['context']['knowledge_layout']={'expression_suffix':'表达规则.md','production_skill':str(HUB/'capabilities/motion/GUIDE.md')};save(project/'00-岗位与协作/员工配置.json',config)
  if id=='OPS':
   for namefile in ['video-style-workflow.json','video-cover-style.json','source-intake.json','script-alignment.json']:
    data=read(HUB/'references/defaults'/namefile)
    if namefile=='script-alignment.json':data['scriptWorkspace']=str(root/NAMES['DIRECTOR']);data['scriptDirectory']='03-任务与交付'
    save(project/'.agents'/namefile,data)
   for sub in ['待剪素材','剪辑项目','成片交付','发布管理','逐字稿']:(project/sub).mkdir(exist_ok=True)
 save(gov/'00-岗位与协作/员工注册表.json',{'schema':'employee-team-registry-v1','project_id':'RECIPIENT-TEAM','project_root':str(root),'members':members,'support_skills':[]})
 result={'schema':'new-media-team/1','skill_root':str(HUB),'team_root':str(root),'governance_root':str(gov),'created_at':datetime.now(timezone.utc).isoformat(),'projects':created}
 save(marker,result)
 (root/'AGENTS.md').write_text('# 新媒体团队\n\n当前统一入口：`'+str(HUB/'SKILL.md')+'`。主管项目位于新媒体主管，常规目标按实际需要调用内部能力。业务数据留各项目，外部动作按实际授权。\n',encoding='utf-8')
 bind(root,'SUPERVISOR',gov)
 return {'initialized':True,**result}

def add_object(root,spec):
 root=Path(root).resolve();no_links(root);config=read(root/'00-岗位与协作/员工配置.json')
 require(re.fullmatch('[A-Za-z0-9_-]{1,80}',spec.get('entity_id','')) and spec.get('name'),'需要当前用户提供的对象编号和真实名称')
 registry_path=root/config['object_registry'];registry=read(registry_path)
 require(not any(x['entity_id']==spec['entity_id'] for x in registry['objects']),'该对象已存在，先读原档案再更新')
 obj={'entity_id':spec['entity_id'],'name':spec['name'],'kind':spec.get('kind','service_object'),'folder':'02-服务对象/'+spec['entity_id'],'facts':spec.get('facts',{}),'accounts':spec.get('accounts',[])}
 save(root/obj['folder']/'对象档案.json',obj);registry['objects'].append(obj)
 if registry['default_id'] is None:registry['default_id']=obj['entity_id'];config['default_service_object_id']=obj['entity_id']
 save(registry_path,registry);save(root/'00-岗位与协作/员工配置.json',config)
 return {'registered':obj['entity_id'],'name':obj['name'],'default_id':registry['default_id']}

def tool_file(root):
 root=Path(root).resolve();profile=root/'.agents/new-media-profile.json'
 require(profile.is_file(),'先接入实际项目再登记工具')
 return Path(read(profile)['governance_root'])/'_管理/runtime-tools.json'
def configured(root):
 if root is None:return {}
 p=tool_file(root)
 return read(p) if p.is_file() else {}
def configure_tools(root,values):
 path=tool_file(root);current=read(path) if path.is_file() else {}
 for key,value in values.items():
  if value:
   p=Path(value).expanduser().resolve();require(p.is_file(),'工具不存在：'+str(p));current[key]=str(p)
 save(path,current);return {'saved':str(path),'tools':current,'global_path_changed':False}
def run_tool(root,capability,script,args):
 require(capability in NAMES and Path(script).name==script and script.endswith(('.py','.mjs','.cjs','.js')),'请指定已注册模块的实际脚本名')
 path=HUB/'capabilities'/capability.lower()/'scripts'/script;require(path.is_file(),'该模块脚本不存在')
 tools=configured(root);env=os.environ.copy();env['PATH']=os.pathsep.join(dict.fromkeys([str(Path(v).parent) for v in tools.values()]))+os.pathsep+env.get('PATH','')
 if tools.get('chrome'):env['CHROME']=tools['chrome']
 env.update(PYTHONUTF8='1',PYTHONIOENCODING='utf-8')
 runtime=HUB/'capabilities/motion/.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
 python=str(runtime) if capability=='MOTION' and runtime.is_file() else sys.executable
 command=([python,'-X','utf8','-B'] if script.endswith('.py') else [tools.get('node') or shutil.which('node') or 'node'])+[str(path),*args]
 return subprocess.call(command,env=env)

def doctor(root=None):
 tools=configured(root);paths={k:tools.get(k) or shutil.which(k) for k in ['ffmpeg','ffprobe','node','npm','yxer']};chrome=tools.get('chrome') or os.environ.get('CHROME')
 if not chrome:
  for p in [Path(os.environ.get('PROGRAMFILES','C:/Program Files'))/'Google/Chrome/Application/chrome.exe',Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')]:
   if p.is_file():chrome=str(p);break
 chrome=chrome or shutil.which('google-chrome') or shutil.which('chromium')
 checks={'python310':sys.version_info>=(3,10),'ffmpeg':bool(paths['ffmpeg']),'ffprobe':bool(paths['ffprobe']),'node18':False,'browser':bool(chrome),'libx264':False,'libass':False,'motion_dependencies':(HUB/'capabilities/motion/node_modules/playwright-core').is_dir(),'licensed_cjk_fonts':(HUB/'capabilities/motion/assets/fonts/NotoSansSC.ttf').is_file()}
 if paths['node']:
  p=subprocess.run([paths['node'],'--version'],capture_output=True,text=True);checks['node18']=p.returncode==0 and int(re.search(r'\d+',p.stdout)[0])>=18
 if paths['ffmpeg']:
  p=subprocess.run([paths['ffmpeg'],'-hide_banner','-encoders'],capture_output=True,text=True);checks['libx264']='libx264' in p.stdout
  p=subprocess.run([paths['ffmpeg'],'-hide_banner','-filters'],capture_output=True,text=True);checks['libass']='subtitles' in p.stdout
 try:import importlib.util;asr=bool(importlib.util.find_spec('faster_whisper'))
 except (ValueError,ImportError):asr=False
 runtime=HUB/'capabilities/motion/.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python');asr_runtime=asr
 if runtime.is_file():
  check=subprocess.run([str(runtime),'-c',"import importlib.util; print(bool(importlib.util.find_spec('faster_whisper')))"],capture_output=True,text=True)
  asr_runtime=asr_runtime or check.returncode==0 and check.stdout.strip()=='True'
 basic=all(checks[x] for x in ['python310','ffmpeg','ffprobe','libx264','libass','licensed_cjk_fonts'])
 return {'schema':'new-media-preflight/1','basic_editing_tools_ready':basic,'animation_tools_ready':basic and checks['node18'] and checks['browser'] and checks['motion_dependencies'],'checks':checks,'tools':{**paths,'chrome':chrome},'asr_in_current_python':asr,'asr_runtime_available':asr_runtime,'asr_model_verified':False,'image_generation':'由当前Codex工具实际能力确认，未调用收费服务','account_connection_tested':False,'gpu_tested':False,'business_quality_accepted':False,'next':['缺工具时从官方渠道安装FFmpeg/Node/Chrome，保持原许可','动效执行MOTION/scripts/pipeline.py setup安装当前包锁定依赖','转写按实际可用工具/GPU/模型准备；没有时记录缺项，不冒充已听校','首次真实素材先做代表段，经接收者反馈后扩展全片'],'project':str(root) if root else None}

def main():
 p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
 q=sub.add_parser('init');q.add_argument('--root',type=Path,required=True)
 q=sub.add_parser('bind');q.add_argument('--project-root',type=Path,required=True);q.add_argument('--role',choices=list(NAMES),required=True);q.add_argument('--governance-root',type=Path,required=True)
 q=sub.add_parser('doctor');q.add_argument('--project-root',type=Path)
 q=sub.add_parser('add-object');q.add_argument('--project-root',type=Path,required=True);q.add_argument('--spec',type=Path,required=True)
 q=sub.add_parser('configure-tools');q.add_argument('--project-root',type=Path,required=True)
 for key in ['ffmpeg','ffprobe','node','chrome']:q.add_argument('--'+key,type=Path)
 q=sub.add_parser('run');q.add_argument('--project-root',type=Path,required=True);q.add_argument('--capability',choices=list(NAMES),required=True);q.add_argument('--script',required=True);q.add_argument('script_args',nargs=argparse.REMAINDER)
 a=p.parse_args()
 try:
  if a.command=='init':v=init(a.root)
  elif a.command=='bind':v=bind(a.project_root,a.role,a.governance_root)
  elif a.command=='doctor':v=doctor(a.project_root)
  elif a.command=='configure-tools':v=configure_tools(a.project_root,{k:getattr(a,k) for k in ['ffmpeg','ffprobe','node','chrome']})
  elif a.command=='run':
   rest=a.script_args[1:] if a.script_args and a.script_args[0]=='--' else a.script_args
   raise SystemExit(run_tool(a.project_root,a.capability,a.script,rest))
  else:v=add_object(a.project_root,read(a.spec))
  print(json.dumps(v,ensure_ascii=False,indent=2))
 except (ValueError,OSError,KeyError,TypeError) as e:p.exit(2,str(e)+'\n')
if __name__=='__main__':main()
