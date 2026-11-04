"""Generate the homepage's direct job-role ZIP download table from catalog.json."""
from pathlib import Path
from urllib.parse import quote
import argparse,json,re
ROOT=Path(__file__).resolve().parents[1]
START='<!-- role-downloads:start -->';END='<!-- role-downloads:end -->'
ORDER=['DIRECTOR','OPS','XHS','EDITOR','DESIGNER','COURSEWARE','PRODUCT','PRIVATE','ENGINEER','BUILDER','SUPERVISOR']
DESCRIPTION={'DIRECTOR':'选题、口播文案、分镜','OPS':'剪辑、字幕、封面、发布与复盘，含制作和采集工具','XHS':'小红书账号分析、笔记与复盘','EDITOR':'公众号选题、文章与图文排版','DESIGNER':'品牌、课程、活动海报','COURSEWARE':'课程大纲、逐页讲稿与课件','PRODUCT':'产品探索、权益与交付设计','PRIVATE':'客户分析、跟进与朋友圈内容','ENGINEER':'功能开发、代码修复与交付','BUILDER':'创建数字员工项目与知识库','SUPERVISOR':'多岗位协作、技能管理与同步'}
def render(catalog):
    base='https://github.com/lanwenlong75-cpu/szyg-new-media-marketing/releases/download/v1.0.0-skills.'+catalog['release']+'/'
    rows=sorted(catalog['skills'],key=lambda r:ORDER.index(r['id']) if r['id'] in ORDER else len(ORDER))
    lines=[START,'| 我需要的岗位 | 可以交给它的工作 | 岗位版本 | 单独下载 | Skill说明 |','| --- | --- | --- | --- | --- |']
    for row in rows:
        filename=row['label']+'_v'+row['version']+'_'+catalog['release']+'.zip'
        lines.append('| **'+row['label']+'** | '+DESCRIPTION.get(row['id'],'查看岗位说明')+' | '+row['version']+' | **[下载 ZIP]('+base+quote(filename)+')** | [说明]('+row['entry']+') |')
    lines.append(END)
    return '\n'.join(lines)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true');args=p.parse_args()
    catalog=json.loads((ROOT/'catalog.json').read_text(encoding='utf-8-sig'));readme=ROOT/'README.md';text=readme.read_text(encoding='utf-8-sig')
    pattern=re.escape(START)+r'[\s\S]*?'+re.escape(END);matches=re.findall(pattern,text)
    if len(matches)!=1:p.exit(2,'README download table markers are missing or duplicated\n')
    expected=render(catalog)
    if args.check:
        if matches[0]!=expected:p.exit(2,'README download links differ from catalog\n')
    else:readme.write_text(re.sub(pattern,lambda m:expected,text),encoding='utf-8')
    print(json.dumps({'roles':len(catalog['skills']),'release':catalog['release'],'checked':args.check}))
