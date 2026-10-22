"""Resolve project roles and live skill sources. Read-only; standard library only."""
from pathlib import Path
import argparse,hashlib,json,re,sys

PROFILE='.agents/new-media-profile.json'
def require(condition,message):
    if not condition:raise ValueError(message)
def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def inside(root,relative):
    require(isinstance(relative,str) and not Path(relative).is_absolute(),'配置入口使用工作区相对路径')
    result=(root/relative).resolve();require(result.is_relative_to(root),'绑定入口超出员工工作区');return result
def project(path):
    path=Path(path).expanduser();require(path.is_absolute() and path.is_dir(),'指定实际项目目录绝对路径');path=path.resolve()
    for root in [path,*path.parents]:
        profile=root/PROFILE
        if profile.is_file():
            config=read(profile);require(config.get('schema')=='new-media-project-profile-v1','项目能力配置版本无效')
            require(Path(config['registry']).is_absolute() and Path(config['governance_root']).is_absolute(),'注册表与主管目录使用实际绝对路径')
            require((root/'AGENTS.md').is_file(),'项目AGENTS入口缺失');return root,profile,config
    raise ValueError('当前目录及其父目录没有新媒体能力配置；先接入真实项目，不能套用其他项目身份。')
HUB=Path(__file__).resolve().parents[1]
def source(role):
    value=role['source'];require(value.get('owner')=='szyg-new-media-marketing','旧独立入口已停用，拒绝回退')
    entry=Path(value['entry']).resolve();expected=(HUB/'capabilities'/role['id'].lower()/'GUIDE.md').resolve()
    require(entry==expected and entry.is_relative_to(HUB/'capabilities'),'能力须由总入口内部模块提供')
    return entry,None

def metadata(role):
    entry,root=source(role)
    result={'id':role['id'],'name':role['name'],'entry':str(entry),'exists':entry.is_file(),
            'worker_root':str(root) if root else None,'name_in_skill':None,'version':None,'description':None}
    if entry.is_file():
        text=entry.read_text(encoding='utf-8-sig');require(text.startswith('---'),'实际skill缺少frontmatter：'+str(entry))
        front=text.split('---',2)[1]
        for key in ['name','description']:
            match=re.search(r'^'+key+r':\s*(.+)$',front,re.M);require(match is not None,'实际skill元数据缺失：'+key)
            result['name_in_skill' if key=='name' else key]=match[1].strip().strip('"\'')
        version=re.search(r'^\s+version:\s*(.+)$',front,re.M)
        result['version']=version[1].strip().strip('"\'') if version else None
        result['entry_sha256']=digest(entry);result['requires_full_read_before_use']=True
    return result
def context(path):
    root,profile,config=project(path);registry=Path(config['registry']).resolve();governance=Path(config['governance_root']).resolve()
    require(registry.is_relative_to(governance),'注册表应位于已配置主管工作区')
    roles=read(registry)['roles'];ids=[r['id'] for r in roles];require(len(ids)==len(set(ids)),'能力注册表编号重复')
    require(config['primary_capability'] in ids,'项目主能力未登记')
    return {'schema':'new-media-project-context-v1','project_root':str(root),'profile':str(profile),
        'role':config['role'],'primary_capability':config['primary_capability'],'focus':config.get('focus',[]),
        'governance_root':str(governance),'registry':str(registry),
        'business_context':{'root':str(root),'policy':'当前用户明确对象与本项目事实优先；不继承能力提供方的默认业务对象'},
        'capabilities':[metadata(r) for r in roles],
        'execution':'assistant_reads_selected_skill_and_executes; resolver_does_not_run_worker_tools'}
def resolve(path,identifier,instructions=False):
    data=context(path);row=next((r for r in data['capabilities'] if r['id']==identifier),None)
    require(row is not None,'能力未在主管注册表登记：'+identifier);require(row['exists'],'实际工作版入口缺失：'+row['entry'])
    result={'project_root':data['project_root'],'role':data['role'],'business_context':data['business_context'],
            'governance_root':data['governance_root'],'selected_capability':row}
    if instructions:
        result['instructions']=Path(row['entry']).read_text(encoding='utf-8-sig')
        require(digest(Path(row['entry']))==row['entry_sha256'],'读取过程中入口变化，请重新读取')
        result['scope']='已读取选定方法；按该方法和所需引用实际执行后才可报告业务已完成。'
    return result
def check(path):
    data=context(path);missing=[r['id'] for r in data['capabilities'] if not r['exists']]
    return {'ok':not missing,'project_root':data['project_root'],'role':data['role'],
            'primary_capability':data['primary_capability'],'capabilities':len(data['capabilities']),
            'missing_capabilities':missing,'scope':'角色配置与真实工作版入口；专业成品质量另验'}
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['context','resolve','check']);parser.add_argument('--project-root',required=True)
    parser.add_argument('--capability');parser.add_argument('--instructions',action='store_true');args=parser.parse_args()
    try:
        if args.command=='context':result=context(args.project_root)
        elif args.command=='check':result=check(args.project_root)
        else:
            require(args.capability,'resolve需要--capability');result=resolve(args.project_root,args.capability,args.instructions)
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0 if result.get('ok',True) else 2
    except (ValueError,OSError,KeyError,TypeError) as error:
        print(json.dumps({'ok':False,'error':str(error)},ensure_ascii=False),file=sys.stderr);return 2
if __name__=='__main__':sys.exit(main())
