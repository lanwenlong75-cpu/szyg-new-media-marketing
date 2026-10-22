# 剪辑与编导

新原片接收先读[原片接收与命名](../../director/references/source-intake.md)。当前工作区配置了`.agents/source-intake.json`时，按已授权项目规则先完成命名与登记，再剪辑。无该配置时沿用本项目既有原片路径约定；只读刷新台账不触发改名。

EDITING_DIR=SKILL_DIR/../../motion是随包引擎，不依赖同名外部安装。保留许可证、字体许可和显式模板版本。候选效果按本期素材验收，不能说成已稳定。

原片/工程先核对编号、原片、主版、已发版本和项目记录。按任务读取：

- [口播语义和波形切点](../../motion/references/spoken-editing.md)
- [编导思维](../../motion/references/director-thinking.md)
- [口播降噪](../../motion/references/voice-denoise.md)
- [发布场景的字幕位置与可读性](subtitle-placement.md)

横屏原片先检查`.agents/video-landscape-to-portrait.json`。已确认采用的项目按[横屏转竖屏标准](../../director/references/landscape-to-portrait.md)直接制作；完整原画在中间，上下黑边分别承载累计模型与居中字幕，字体和原声沿用。此布局不重新启动风格探索，也不套用竖屏真人全屏裁切。

新文案、新参考或风格转向先按[文案选型与协作](../../director/references/copy-style-collaboration.md)判断内容任务和素材条件，读取当前项目的样片协作偏好；已有风格的局部修正直接完成。

先判断每次重说的意思、保留哪一次和上下文，再用波形/VAD找切点。候选不自动删除，字幕省略不代表原声已删。完整课程保留教学内容，除非用户要求拆条。有SRT或转录先复用核对；没有ASR按宿主实际能力配置，不虚报人工听校。

精剪可按审阅后的保留区间用FFmpeg同步裁剪声画和映射字幕。需要动效时读[引擎执行说明](../../motion/GUIDE.md)、相关模板和manifest。跨平台入口：

```text
python EDITING_DIR/scripts/pipeline.py doctor
python EDITING_DIR/scripts/pipeline.py packs
```

按主题、片长、画幅和实际素材选模板，生成brief/spec并构建，不要求用户手填工程槽位。命令参数依随包帮助和流程，不猜高级模板字段。讲提示词默认说一句、显示一句，逐句替换并记录实际口播时码；未讲到的后文不可见，不套用整张静态全文内容卡。逐句内容完整覆盖原提示词，另附可复制字稿。讲产品用真实素材，讲步骤对应真实操作，人物动效为信息让位。

对最终编码核对声画、切点、字幕时钟、时长、画幅、SAR/DAR、完整解码、音量及实际播放。提示词逐个检查换句点并连续播放整个段落，确认当前句随口播出现、后文未提前露出、无闪现全文，记录实际验收范围。抽帧和退出码不能证明连续声画已验收；没有实际听校依据，humanListeningChecked保持false。

交付新版MP4、需要的无字幕母版、可编辑SRT/ASS/工程、校对入口和验收记录。用ops.py register --root ROOT --media 新版MP4 --id 既有编号 --kind master登记，再刷新台账和工作台。旧发布继续绑定旧文件。任务有可审阅交付写待审阅，有实际完成证据再写已完成。

每条视频另存完整逐字稿，原片与成片的时码分开；改版另存对应逐字稿，保留旧记录。有当前成片同目录的字幕映射或SRT时，`python SKILL_DIR/scripts/transcripts.py --root ROOT`复用导出；没有全文时先对实际音频完整转写，再执行`python SKILL_DIR/scripts/transcripts.py --root ROOT --id 内容编号 --input 完整转写JSON或SRT`。输入应覆盖整条视频且与当前播放版本一致，不使用提示词文本、摘要、局部转写或尚未合入成片的校对草稿代替。

输出位于逐字稿/编号/版本记录/，包括全文TXT、带时间码TXT、SRT、JSON及独立观看页；逐字稿/index.html为合集，工作台视频详情可查看、复制、下载并按时间定位。ops.py index和register同步导出已有的当前字幕，仍缺转写的编号显示待补齐，助手继续补转写后交付。仅有字幕整理或自动识别时保留待听校与疑难项；原片的重说、口头语和未完成句不做内容润色或静默删减。
