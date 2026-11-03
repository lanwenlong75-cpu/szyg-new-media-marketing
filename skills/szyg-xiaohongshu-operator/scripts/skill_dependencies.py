"""Find an explicitly registered peer skill, or a canonical sibling installation."""
from pathlib import Path
import json,re

def resolve_skill(name, project_root=None):
    own=Path(__file__).resolve().parents[1]
    candidates=[]
    if project_root:
        root=Path(project_root).resolve()
        for parent in (root,*root.parents):
            profile=parent/'.agents/new-media-profile.json'
            if not profile.is_file():continue
            value=json.loads(profile.read_text(encoding='utf-8-sig'))
            registry=Path(value['registry'])
            for role in json.loads(registry.read_text(encoding='utf-8-sig'))['roles']:
                if role['source'].get('owner')==name:candidates.append(Path(role['source']['entry']).parent)
            break
    candidates.append(own.parent/name)
    for folder in candidates:
        entry=folder/'SKILL.md'
        if entry.is_file():
            text=entry.read_text(encoding='utf-8-sig')
            match=re.search(r'^name:\s*[\"\']?([a-z0-9-]+)',text,re.M)
            if match and match[1]==name:return folder.resolve()
    raise ValueError('当前任务需要独立Skill '+name+'；请安装该Skill或在项目注册表登记实际入口。')
