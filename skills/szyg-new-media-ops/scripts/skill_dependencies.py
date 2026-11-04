"""Resolve job-role skills; legacy function keys address internal OPS tools only."""
from pathlib import Path
import json,re
ALIASES={'szyg-duli-motion-video':'capabilities/video-production',
         'szyg-archive-social-video':'capabilities/source-archive/single',
         'szyg-archive-social-account':'capabilities/source-archive/account'}
def resolve_skill(name,project_root=None):
    start=Path(__file__).resolve().parents[1]
    own=next((p for p in (start,*start.parents) if (p/'SKILL.md').is_file()),start)
    wanted='szyg-new-media-ops' if name in ALIASES else name
    candidates=[]
    if own.name==wanted:candidates.append(own)
    if project_root:
        root=Path(project_root).resolve()
        for parent in (root,*root.parents):
            profile=parent/'.agents/new-media-profile.json'
            if not profile.is_file():continue
            value=json.loads(profile.read_text(encoding='utf-8-sig'))
            registry=Path(value['registry'])
            for role in json.loads(registry.read_text(encoding='utf-8-sig'))['roles']:
                if role['source'].get('owner')==wanted:candidates.append(Path(role['source']['entry']).parent)
            break
    candidates.append(own.parent/wanted)
    for folder in candidates:
        entry=folder/'SKILL.md'
        if not entry.is_file():continue
        match=re.search(r'^name:\s*[\"\']?([a-z0-9-]+)',entry.read_text(encoding='utf-8-sig'),re.M)
        if not match or match[1]!=wanted:continue
        if name not in ALIASES:return folder.resolve()
        component=folder/ALIASES[name]
        if (component/'GUIDE.md').is_file():return component.resolve()
    raise ValueError('当前任务需要'+('新媒体运营岗位及其内置工具' if name in ALIASES else '岗位Skill '+wanted)+'；请按岗位安装或登记实际入口。')
