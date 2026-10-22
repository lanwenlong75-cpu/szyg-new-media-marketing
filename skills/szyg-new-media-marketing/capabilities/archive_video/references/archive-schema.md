# Archive and Wiki schema

## Raw archive

`知识库/第六层-输入/社媒视频原始同步/{平台}/{YYYY}/{MM}/{DD}/{平台ID}-{标题}/`

Required:

- `00-来源信息.md`
- `01-逐字稿-原始.md`
- `01-逐字稿-原始.json`
- `02-逐字稿-整理.md`
- cover
- high-value or uncertain original video

Conditional:

- `03-评论语料.md` for topic,传播, or audience analysis

Delete temporary audio after verification.

## Wiki compilation

- `01-核心观点`: external judgment with attribution
- `02-真实案例`: mark external public case and verification level
- `03-客户痛点`: real operating needs and resistance
- `04-原话与表达`: exact speaker and timestamp; never mix with 当前IP quotes
- `05-选题机会`: direction, 当前IP evidence, missing evidence, non-anxiety titles
- `06-方法与流程`: steps, workflow, department changes, acceptance checks
- `07-来源卡片`: metadata, summary, chapters, clips, risks, related pages

## Source-card fields

- `source_id`
- platform and platform ID
- author and speakers
- publication time and clean URL
- verification status
- interaction snapshot time
- timestamped usable clips
- risks and related pages

## Verification levels

1. `视频自述`
2. `交叉核验`
3. `已确认`

Do not silently upgrade a claim.
