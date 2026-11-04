# 单条资料采集（新媒体运营内部工具）

Run the complete evidence-first workflow. Do not analyze a video from its title, chapter summary, or partial captions.

## Project

Use the explicitly selected current project root. Read its `AGENTS.md` before writing knowledge-base content.

Use these verified entry points:

- `自动化\社媒视频归档.ps1`
- `自动化\转写社媒视频.py`
- `自动化\check-social-video-runtime.ps1`
- `自动化\state\social-video-index.csv`

Read [references/machine-profile.md](references/machine-profile.md) before a new transcription. Read [references/archive-schema.md](references/archive-schema.md) before compiling Wiki pages.

## Fast path

1. Extract the platform ID from the link.
2. Check `social-video-index.csv` and the raw archive before opening the browser.
3. Reuse a completed transcript when the platform ID and media hash match.
4. Refresh comments, cover, metadata, and interaction counts without retranscribing unchanged media.
5. Use downloaded audio as the transcription input; retain the original video according to the retention rule.
6. Use `-TranscriptionMode fast` by default. Use `accurate` for noisy audio, heavy dialect, overlapping speakers, dense names or numbers, or a user request for maximum accuracy.
7. Never wait for the video to play in real time. Verify chapter boundaries, low-confidence segments, names, numbers, and quoted passages against the image and audio.

## Workflow

1. For Douyin links, prefer the project's TikHub acquisition script when `自动化/secure/tikhub-credential.xml` exists:
   `powershell.exe -NoProfile -ExecutionPolicy Bypass -File 自动化/TikHub社媒视频采集.ps1 -SourceUrl "<url>" -OutputDirectory "<audit-dir>"`.
2. The TikHub script uses `/api/v1/douyin/web/fetch_one_video_by_share_url`, Check the current price and the authorized budget before use. Make exactly one acquisition request per source; do not repeat a paid acquisition or switch to a more expensive endpoint without the user's applicable authorization.
3. Record the clean source URL, author, title, publication time, API response, acquisition result, download time, and local video path. Never print or copy the decrypted API key into logs.
4. When TikHub is unavailable, or for unsupported platforms, use the Chrome browser-control skill and the user's signed-in Chrome. Open the detail page and use 社媒助手 as the fallback for video, audio, cover, and copied video information.
5. For topic,传播, or audience analysis, load public comments and archive the first 50 anonymously. TikHub media acquisition does not replace comment collection; use the public comment panel or an approved comment endpoint and record the chosen method.
6. When transcription is required, run the runtime check from the project root:

   `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\自动化\check-social-video-runtime.ps1`

   If it fails, retry once with `-Repair`. Report the concrete error before choosing any CPU fallback.
7. Run `社媒视频归档.ps1` with platform, clean URL, title, author, publication time, downloaded paths, and `-RequireGpu`. Use `powershell.exe -NoProfile -ExecutionPolicy Bypass -File` because this Windows machine blocks unsigned PowerShell scripts by default.
8. Confirm that the raw transcript starts near `00:00`, covers the full media duration, reports `device: cuda`, and preserves word-level JSON.
9. Verify chapter timestamps, screen captions, speaker attribution, names, numbers, quoted passages, and low-confidence segments. Mark unresolved text `[听不清]` or `[说话人待确认]`.
10. Compile the source into the Wiki categories required by the schema. Create only categories supported by the source; always preserve the source record; use the selected project's actual knowledge structure.
11. Update the source card, Wiki index, compilation log, directory overview, material-source library, source rules when needed, and state CSV.
12. Run `python <OPS>/scripts/check_archive.py --transcript <raw-transcript.json>` for source and timing structure. Follow the selected project's Wiki/index checks only when that project actually has them. Source verification and professional analysis remain separate.

## Evidence rules

- Use `platform:platform_id` as `source_id`.
- Keep external speakers separate from 当前IP.
- Label growth, revenue, efficiency, headcount, and outcome claims as `视频当事人自述` until independently verified.
- Keep external material in the seventh-layer Wiki until the current project owner explicitly approves promotion.
- Preserve original wording in raw transcripts. Put corrections only in the organized transcript.
- Use non-anxiety titles. Emphasize process, practice, and evidence.
- Obey the project's prohibited-sentence rule in all generated Wiki analysis and topic copy.

## Speed and status

- Before a long transcription, state whether the model is cached and whether the runtime check passed.
- Expect the verified 18-minute sample to transcribe in roughly one minute in fast mode. Treat a multi-minute GPU run as an anomaly and inspect the process, device, and logs.
- Do not silently fall back to CPU on this machine. Report the failure first; use CPU only when GPU repair cannot complete and continuing is appropriate.
- Give a concise progress update at least once per minute during downloads, model setup, or transcription.
- Do not repeat transcription merely to refresh cover, comments, or interaction data.
- Keep model files, CUDA runtime, temporary audio, and benchmarks under `自动化\secure\`.



## 可迁移初始标准

每次使用本工具先读[沿用的审美、经验、标准与要求](references/inherited-standards.md)。接收者反馈从空白开始，初始标准继续执行。真实业务事实、账号和素材只取当前使用者项目。自动化脚本路径从本次项目根展开；随包源码位于OPS/capabilities/source-archive/account/scripts，参考文件相对当前GUIDE展开。


接收电脑先从../account/references/portable-setup.md安装随包归档运行时到当前项目，随后检查GPU/模型/获取工具；凭据由接收者自行配置。未配置下载或转写时如实报告，不能从标题推断视频内容。





## 开源初始标准

使用本工具前读取[沿用的审美、经验、标准与要求](references/inherited-standards.md)。业务事实、账号、素材和本人经历以接收者当前项目为准。


这些是新媒体运营岗位内部的方法、程序和资源，不是另一个Skill或数字员工。岗位入口是所属运营Skill的SKILL.md；工具改进由运营维护，服务对象、素材与账号始终取本次项目。

OPS是本工具所属的新媒体运营Skill目录。项目没有Wiki体系时，来源记录和全文保存在本次任务归档目录，不创建或写入其他项目的知识层。
