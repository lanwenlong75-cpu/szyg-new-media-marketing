"""Recipient-owned independent role projects; no account or business seed data."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,re,shutil,uuid

def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def save(p,v):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def hashes(root):return {p.relative_to(root).as_posix():sha(p) for p in sorted(root.rglob('*')) if p.is_file() and not set(p.parts)&{'__pycache__','node_modules','.git','.venv'} and p.suffix not in {'.pyc','.pyo'} and p.name!='.release-baseline.json'}

def initialize(root,skills,release):
    root=Path(root).resolve()
    marker=root/'.independent-skills-team.json'
    if root.exists() and any(root.iterdir()):
        if not marker.is_file():raise ValueError('已有业务目录保持原样。请选择空目录创建项目；旧统一团队先备份、比对并迁移绑定与反馈基线。')
        existing=read(marker)
        if existing['release']!=release:raise ValueError('团队已有另一发行。技能与资料保持原样；先迁移现有项目绑定及反馈台账。')
        for item in skills:
            prior=existing['skills'].get(item['name'])
            if not prior or Path(prior['entry']).resolve()!=Path(item['entry']).resolve():raise ValueError('团队岗位或安装目录不同，先比对迁移。')
        return {'created':False,'preserved_existing':True,'team':str(root),'projects':existing['projects']}
    root.mkdir(parents=True,exist_ok=True)
    governance=root/'团队管理'
    registry=governance/'00-岗位与协作/skill同步注册表.json'
    save(registry,{'schema':'skill-sync-registry-v1','runtime_policy':'independent-skills-v1','roles':[{'id':r['id'],'name':r['label'],'skill_name':r['name'],'source':{'owner':r['name'],'entry':r['entry']},'copies':[]} for r in skills]})
    projects=[];members=[]
    for item in skills:
        project=root/item['label'];entry=Path(item['entry']).resolve();skill=entry.parent
        for name in ['00-岗位与协作','01-共用知识','02-服务对象','03-任务与交付','04-复盘与改进','_管理']:(project/name).mkdir(parents=True,exist_ok=True)
        config={'schema':'digital-employee-config-v1','employee_id':'EMP-'+uuid.uuid4().hex[:12],'employee_name':item['label'],'role':item['id'].lower(),'default_service_object_id':None,'object_registry':'02-服务对象/服务对象注册表.json','worker_skills':[{'name':item['name'],'entry':str(entry),'primary':True,'capability':item['id']}],'capability_binding':{'owner':item['name'],'id':item['id'],'entry':str(entry),'maintenance_root':str(project),'migration_record':'_管理/独立Skill迁移.json'},'skill_iteration_policy':{'enabled':True,'rules_file':str(skill/'references/数字员工确认规则.md'),'ledger':'_管理/skill迭代记录.json','tool':'_管理/record_skill_iteration.py','tracking':'primary-skill-files-v2'},'context':{'current_user_data_only':True},'live_task_validated':False}
        if item['id']=='OPS':
            defaults=skill/'references/defaults'
            for p in defaults.glob('*.json'):
                data=read(p)
                if p.name=='script-alignment.json':
                    director=next((r for r in skills if r['id']=='DIRECTOR'),None)
                    data['scriptWorkspace']=str(root/director['label']) if director else None
                    data['scriptDirectory']='03-任务与交付'
                save(project/'.agents'/p.name,data)
        save(project/'00-岗位与协作/员工配置.json',config)
        save(project/config['object_registry'],{'schema':'employee-entities-v1','default_id':None,'objects':[]})
        baseline={'@capability/'+k:v for k,v in hashes(skill).items()}
        ledger={'schema':'employee-skill-iterations-v1','tracking':'primary-skill-files-v2','revision':0,'rules':[],'events':[],'working_hashes':baseline}
        frozen=project/'_管理/初始反馈台账.json';save(frozen,ledger);save(project/config['skill_iteration_policy']['ledger'],ledger)
        save(project/config['capability_binding']['migration_record'],{'kind':'independent_skill_initial_binding','prior_ledger':str(frozen),'prior_ledger_sha256':sha(frozen),'preserved_revision':0,'module_baseline':baseline,'human_feedback_created':False})
        save(project/'_管理/来源复制清单.json',[])
        save(project/'_管理/生成清单.json',{'generated':{'00-岗位与协作/员工配置.json':sha(project/'00-岗位与协作/员工配置.json')}})
        save(project/'_管理/知识依赖检查.json',{'unresolved':[]})
        save(project/'.agents/new-media-profile.json',{'schema':'new-media-project-profile-v1','role':item['label'],'primary_capability':item['id'],'primary_skill':item['name'],'entry':str(entry),'entry_version':item['version'],'runtime_mode':'independent-skills-v1','registry':str(registry),'governance_root':str(governance),'business_context_root':str(project)})
        (project/'AGENTS.md').write_text('# '+item['label']+'\n\n正常提出业务目标即可使用本岗位。先读员工配置与项目资料，再读独立Skill `'+entry.as_posix()+'`及所需引用。业务事实、账号、素材与真实反馈留本项目；跨岗位按任务读取已安装Skill，外部动作按真实授权。\n',encoding='utf-8')
        (project/'README.md').write_text('# '+item['label']+'\n\n从AGENTS.md开始。把真实资料放本项目，直接告诉助手本次目标。\n',encoding='utf-8')
        (project/'00-岗位与协作/反馈与skill迭代.md').write_text('# 反馈与改进\n\n先修交付，再依真实人类长期反馈或认可，用_管理/record_skill_iteration.py修改实际岗位方法，保留范围、备份与验证。初始继承标准不是接收者的新认可事件。\n',encoding='utf-8')
        (project/'04-复盘与改进/能力迭代记录模板.md').write_text('# 能力改进\n\n记录任务、真实反馈、原因、变更、备份、复验和后续实际效果。\n',encoding='utf-8')
        (project/'_管理/record_skill_iteration.py').write_text('import runpy,sys\nsys.path.insert(0,'+repr(str(skill/'scripts'))+')\nrunpy.run_path('+repr(str(skill/'scripts/module_iteration.py'))+",run_name='__main__')\n",encoding='utf-8')
        projects.append({'role':item['id'],'skill':item['name'],'root':str(project),'entry':str(entry)})
        members.append({'id':item['id'],'name':item['label'],'kind':'employee','root':str(project),'config':'00-岗位与协作/员工配置.json','purpose':item['label']+'实际任务'})
    save(governance/'00-岗位与协作/员工注册表.json',{'schema':'employee-team-registry-v1','project_id':'RECIPIENT-TEAM','project_root':str(root),'members':members,'support_skills':[]})
    save(governance/'00-岗位与协作/skill同步记录.json',{'schema':'skill-sync-ledger-v1','records':[]})
    result={'schema':'independent-skills-team/1','release':release,'skills':{r['name']:r for r in skills},'projects':projects,'created_at':datetime.now(timezone.utc).isoformat()}
    save(marker,result)
    (root/'AGENTS.md').write_text('# 数字员工团队\n\n岗位目录中各自绑定独立Skill。先打开所需岗位目录，再说本次目标；需要跨岗位时使用新媒体主管。团队管理保存注册与协作记录。\n',encoding='utf-8')
    (root/'START-HERE.md').write_text('# 开始使用\n\n发行：'+release+'。\n\n在你使用的软件中新建本地项目，选择下列岗位目录；项目名称可以改为自己的名称，保留实际目录绑定即可。要移动目录，先备份并更新项目profile和员工配置里的绝对路径，再检查入口。\n\n'+'\n'.join('- '+r['label']+'：'+str(root/r['label'])+'（'+r['name']+' '+r['version']+'）' for r in skills)+'\n\n直接描述任务和提供自己的资料。缺工具按实际任务配置，技术安装不等于专业成品验收。\n',encoding='utf-8')
    return {'created':True,'team':str(root),'projects':projects}
