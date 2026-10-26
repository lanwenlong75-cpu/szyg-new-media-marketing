"""Build synchronized Codex and WorkBuddy archives from one sealed public tree."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,zipfile

ROOT=Path(__file__).resolve().parents[1]
SKILL=ROOT/'skills/szyg-new-media-marketing'
def read(path):return path.read_text(encoding='utf-8-sig')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value):
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def write(path,text,bom=False):
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding='utf-8-sig' if bom else 'utf-8',newline='\r\n' if path.suffix in {'.ps1','.cmd'} else '\n')
def files(root):return {p.relative_to(root).as_posix():p for p in root.rglob('*') if p.is_file() and '.git' not in p.relative_to(root).parts}
def archive(root,target):
 if target.exists():raise ValueError('Preserve sealed archive: '+str(target))
 with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for name,path in sorted(files(root).items()):z.write(path,name)
 with zipfile.ZipFile(target) as z:
  for name,path in files(root).items():assert hashlib.sha256(z.read(name)).hexdigest()==sha(path)
 write(target.with_suffix(target.suffix+'.sha256'),sha(target)+'  '+target.name+'\n')
 return {'name':target.name,'sha256':sha(target),'bytes':target.stat().st_size}
def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path);parser.add_argument('--runtime-cache',required=True,type=Path);args=parser.parse_args()
 out=args.output.resolve();runtime_cache=args.runtime_cache.resolve()
 if out.is_relative_to(ROOT) or ROOT.is_relative_to(out):raise ValueError('Output must be separate from the repository')
 out.mkdir(parents=True,exist_ok=True)
 version=json.loads(read(ROOT/'VERSION.json'));release=version['release']
 manifest=json.loads(read(ROOT/'manifest.json'));assert release==manifest['release']
 expected={r['path']:r for r in manifest['files']};actual=files(ROOT)
 assert set(actual)==set(expected)|{'manifest.json'}
 assert all(sha(actual[name])==row['sha256'] for name,row in expected.items())
 shared={p.relative_to(SKILL).as_posix():sha(p) for folder in ['capabilities','scripts'] for p in (SKILL/folder).rglob('*') if p.is_file()}
 assert hashlib.sha256(json.dumps(shared,sort_keys=True,separators=(',',':')).encode()).hexdigest()==version['method_content_sha256']
 # Both packages use this exact canonical method tree.
 codex=archive(ROOT,out/('szyg-new-media-marketing-codex-'+release+'.zip'))
 stage=out/'.staging';stage.mkdir()
 imported=stage/'workbuddy-skill';shutil.copytree(SKILL,imported)
 skill_version=json.loads(read(imported/'版本信息.json'));skill_version['host']='WorkBuddy';save(imported/'版本信息.json',skill_version)
 header='''display_name: 新媒体数字员工
display_name_en: New Media Digital Team
description_zh: 新媒体营销统一入口，十四项岗位能力及完整方法、模板、脚本与验收标准。
description_en: Fourteen new media role capabilities with reusable methods and delivery standards.
version: "SOURCE_VERSION"
author: "szyg-new-media-marketing contributors"
'''.replace('SOURCE_VERSION',version['source_entry_version'])
 text=read(imported/'SKILL.md').replace('---\n','---\n'+header,1)
 text+='\n\n## WorkBuddy接入\n\n读取[宿主接入说明](references/workbuddy-setup.md)，按WorkBuddy当前真实技能目录与可用工具使用本方法。发行号读取本目录版本信息.json；岗位方法按GUIDE执行，业务资料使用当前接收者自己的项目。\n'
 write(imported/'SKILL.md',text)
 host_guide='''# WorkBuddy接入 · RELEASE

本Skill和同发行Codex版使用同一公开岗位方法快照。发行号读取版本信息.json，内部模块源版本仅用于追溯。

使用WorkBuddy“添加技能 → 上传技能”导入本地Skill ZIP，遵循客户端当前的安全扫描和确认。不要将整个外层安装总包当作单个Skill上传。导入后从WorkBuddy真实工具返回确定本Skill目录，不借用其他宿主的安装路径。

当前工作区先读AGENTS.md和.agents/new-media-profile.json，按项目岗位读取本入口与实际GUIDE。文档、图像、终端等执行采用当前宿主真实可用能力。缺工具时记录缺项；安装、客户端调用、专业成品验收分别报告。

新团队可运行scripts/portable.py init --root <自己的空团队目录>，逐岗运行scripts/hub.py check。Windows离线总包包含官方Python和Initialize-WorkBuddy.ps1，按包内说明传入真实-SkillRoot。

已有Skill或团队先核对当前版本、本地改进和业务资料。跨版本采用备份、比对、迁移和检查，不强制覆盖；旧版按发行保留。安装回执记录本发行号、实际入口和共用方法摘要。

官方本地导入：https://intl.cloud.tencent.com/zh/document/product/1316/84503
官方Skill结构：https://open.workbuddy.cn/en/docs/skill
'''.replace('RELEASE',release)
 write(imported/'references/workbuddy-setup.md',host_guide)
 for name in ['LICENSE','THIRD_PARTY.md']:write(imported/name,read(ROOT/name).replace('skills/szyg-new-media-marketing/',''))
 for name,digest in shared.items():assert sha(imported/name)==digest,name
 native_name='新媒体数字员工技能_'+release+'.zip'
 native=archive(imported,out/native_name)
 kit=stage/'workbuddy-kit';kit.mkdir()
 shutil.copy2(out/native_name,kit/native_name)
 skill_files=[{'path':name,'sha256':sha(path),'bytes':path.stat().st_size} for name,path in sorted(files(imported).items())]
 save(kit/'skill-files.json',{'schema':'workbuddy-skill-files/1','release':release,'method_content_sha256':version['method_content_sha256'],'files':skill_files})
 for name in ['workbuddy_init.py','Initialize-WorkBuddy.ps1']:shutil.copy2(ROOT/'distribution'/name,kit/name)
 helper=read(ROOT/'installer-runtime.ps1');write(kit/'offline-helpers.ps1',helper[helper.index('function Assert-SzygHash'):helper.index('function Test-SzygPython')])
 runtime_sources=json.loads(read(ROOT/'INSTALLER-SOURCES.json'))
 for arch,row in runtime_sources['windows'].items():
  name='python-'+runtime_sources['python_version']+'-embed-'+arch+'.zip';source=runtime_cache/name
  assert source.is_file() and sha(source)==row['sha256'],'Official runtime archive unavailable or different: '+name
  target=kit/'runtime'/name;target.parent.mkdir(exist_ok=True);shutil.copy2(source,target)
  with zipfile.ZipFile(target) as z:
   licenses=[n for n in z.namelist() if n.lower().endswith('license.txt')];assert licenses
   write(kit/'licenses'/('Python-'+arch+'-LICENSE.txt'),z.read(licenses[0]).decode('utf-8'))
 save(kit/'RUNTIME-SOURCES.json',runtime_sources)
 save(kit/'版本信息.json',{**version,'host':'WorkBuddy','native_skill_zip':native_name,'native_skill_sha256':native['sha256']})
 prompt='''请帮我把《新媒体数字员工_RELEASE_WorkBuddy版.zip》安装或升级到WorkBuddy。完整解压并按包内说明完成技能导入、十四个岗位工作区的创建和检查，保留我已有的资料与本地改进。需要我操作界面时告诉我具体步骤；完成后告诉我实际安装版本、使用入口和缺少的工具。'''.replace('RELEASE',release)
 write(kit/'安装提示词.txt',prompt+'\n');write(out/('安装提示词_'+release+'_WorkBuddy.txt'),prompt+'\n')
 guide='''# 新媒体数字员工 · RELEASE · WorkBuddy版

**当前总发行号：RELEASE。** GitHub下载与微信收到的同宿主压缩包逐字节一致。版本信息.json记录发行号与共用方法摘要；内部Python、视频引擎和各岗位源版本不用于挑选总安装包。

1. 完整解压本总包，在WorkBuddy“添加技能 → 上传技能”选择同目录的《NATIVE》。按实际客户端完成安全检测与确认。
2. 将《安装提示词.txt》发给WorkBuddy，并选择这个解压文件夹作为工作区。
3. 导入后定位真实Skill目录，按以下命令初始化自己的团队：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\Initialize-WorkBuddy.ps1 -SkillRoot "实际SKILL.md所在目录"
```

默认团队位于用户主目录“数字员工团队/WorkBuddy新媒体”，可传-WorkspaceRoot选择自己的空目录。脚本使用随包官方Python，检查14岗位绑定，生成START-HERE-WorkBuddy.md和WorkBuddy安装回执.json。已有不同团队、业务目录或本地方法先比对迁移，不强制覆盖。

## 持续更新

每次用新发行号保存安装包，旧版保留。收到更新时让WorkBuddy先核对已装版本和本地改进，再升级并检查实际回执；发出的旧包不会自动变成新版。服务对象、账号与业务素材始终使用接收者自己的资料。

## 安装范围

Skill文件与基础初始化使用本地资源。Windows包含官方x64/ARM64 Python；x64实际执行验证，ARM64尚无实机回执。macOS/Linux可导入内层Skill ZIP，再使用已有Python3.10+运行Skill的portable.py；本总包不含其运行时。WorkBuddy模型、专业工具、图像、转写、发布等依赖按接收者实际环境配置。客户端原生导入与真实成品质量以接收端回执为准。
'''.replace('RELEASE',release).replace('NATIVE',native_name)
 write(kit/'先读我-WorkBuddy离线安装.md',guide)
 save(kit/'offline-files.json',{'schema':'workbuddy-offline-files/1','edition':release,'release':release,'default_workspace':'数字员工团队/WorkBuddy新媒体','files':[{'path':name,'sha256':sha(path),'bytes':path.stat().st_size} for name,path in sorted(files(kit).items())]})
 wb=archive(kit,out/('szyg-new-media-marketing-workbuddy-'+release+'.zip'))
 # English GitHub asset names and Chinese WeChat filenames refer to the same bytes.
 for host,asset in [('Codex',codex),('WorkBuddy',wb)]:
  alias='新媒体数字员工_'+release+'_'+host+'版.zip';shutil.copy2(out/asset['name'],out/alias);assert sha(out/alias)==asset['sha256']
  write(out/(alias+'.sha256'),asset['sha256']+'  '+alias+'\n');asset['wechat_name']=alias
 bootstrap=out/'Install-New-Media-Team-Windows.cmd';shutil.copy2(ROOT/bootstrap.name,bootstrap)
 write(out/(bootstrap.name+'.sha256'),sha(bootstrap)+'  '+bootstrap.name+'\n')
 codex_prompt='请帮我把《新媒体数字员工_'+release+'_Codex版.zip》安装或升级到Codex。完整解压并按包内说明安装统一Skill、创建并检查十四个岗位工作区，保留已有资料和本地改进。完成后告诉我实际安装版本、使用入口和缺少的工具。'
 write(out/('安装提示词_'+release+'_Codex.txt'),codex_prompt+'\n')
 result={**version,'assets':[codex,wb,{'name':bootstrap.name,'sha256':sha(bootstrap),'bytes':bootstrap.stat().st_size}],'native_skill':native,'packages_share_method_snapshot':True,'wechat_copies_byte_identical':True}
 save(out/'release-assets.json',result)
 print(json.dumps({'release':release,'output':str(out),'package_count':2,'shared_method_sha256':version['method_content_sha256'],'wechat_copies_byte_identical':True},ensure_ascii=False))
if __name__=='__main__':main()
