---
name: szyg-archive-social-video
description: Download, transcribe, verify, classify, and archive social-media videos into the 当前IP enterprise-AI knowledge base. Use whenever the user gives a Douyin, WeChat Channels, Xiaohongshu, Bilibili, or other social-video link and asks to extract content, analyze the video, summarize it, derive topics, inspect audience comments, or save the material into the knowledge base.
---

# szyg-单条视频采集归档

Run the complete evidence-first workflow. Do not analyze a video from its title, chapter summary, or partial captions.

## Project

Use the explicitly selected current project root. Read its `AGENTS.md` before writing knowledge-base content.

Use these verified entry points:

- `自动化\社媒视频归档.ps1`
- `自动化\转写社媒视频.py`
- `自动化\check-social-video-runtime.ps1`
- `自动化\测试社媒视频归档.ps1`
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
2. The TikHub script uses `/api/v1/douyin/web/fetch_one_video_by_share_url`, currently budgeted at USD 0.001 per request. Make exactly one acquisition request per source. Never retry a billable request or call the USD 0.005 highest-quality endpoint without explicit user approval.
3. Record the clean source URL, author, title, publication time, API response, acquisition result, download time, and local video path. Never print or copy the decrypted API key into logs.
4. When TikHub is unavailable, or for unsupported platforms, use the Chrome browser-control skill and the user's signed-in Chrome. Open the detail page and use 社媒助手 as the fallback for video, audio, cover, and copied video information.
5. For topic,传播, or audience analysis, load public comments and archive the first 50 anonymously. TikHub media acquisition does not replace comment collection; use the public comment panel or an approved comment endpoint and record the chosen method.
6. When transcription is required, run the runtime check from the project root:

   `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\自动化\check-social-video-runtime.ps1`

   If it fails, retry once with `-Repair`. Report the concrete error before choosing any CPU fallback.
7. Run `社媒视频归档.ps1` with platform, clean URL, title, author, publication time, downloaded paths, and `-RequireGpu`. Use `powershell.exe -NoProfile -ExecutionPolicy Bypass -File` because this Windows machine blocks unsigned PowerShell scripts by default.
8. Confirm that the raw transcript starts near `00:00`, covers the full media duration, reports `device: cuda`, and preserves word-level JSON.
9. Verify chapter timestamps, screen captions, speaker attribution, names, numbers, quoted passages, and low-confidence segments. Mark unresolved text `[听不清]` or `[说话人待确认]`.
10. Compile the source into the Wiki categories required by the schema. Create only categories supported by the source; always create or update the source card.
11. Update the source card, Wiki index, compilation log, directory overview, material-source library, source rules when needed, and state CSV.
12. Run the archive test and Wiki check. Deliver analysis and topics only after the relevant checks pass.

## Evidence rules

- Use `platform:platform_id` as `source_id`.
- Keep external speakers separate from 当前IP.
- Label growth, revenue, efficiency, headcount, and outcome claims as `视频当事人自述` until independently verified.
- Keep external material in the seventh-layer Wiki until 当前IP explicitly approves promotion.
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


## 当前自用入口与维护位置

本方法已并入`szyg-new-media-marketing`内部能力`ARCHIVE_VIDEO`，本目录为当前工作版。旧独立skill及旧调用名已停用；通过总入口按项目角色选择本方法，不回退到归档。相对脚本与资源以本GUIDE所在目录展开。原有审美、经验、风格选择及验收要求继续执行。业务资料和实际工程保持原位，当前服务对象由项目配置与用户本次需求确定。


## 可迁移初始标准

每次使用本模块先读[沿用的审美、经验、标准与要求](references/inherited-standards.md)。接收者反馈从空白开始，初始标准继续执行。真实业务事实、账号和素材只取当前使用者项目。所有相对脚本从本GUIDE目录展开。


接收电脑先从ARCHIVE_ACCOUNT的references/portable-setup.md安装随包归档运行时到当前项目，随后检查GPU/模型/获取工具；凭据由接收者自行配置。未配置下载或转写时如实报告，不能从标题推断视频内容。


<!-- digital-employee-feedback:start -->
## 当前使用者反馈

本地规则修订：0。

真实长期反馈通过所属工作区的_管理/record_skill_iteration.py记录，保留范围、旧版与验证；初始标准不当作当前使用者的认可。
<!-- digital-employee-feedback:end -->


## 开源初始标准

使用本模块前读取[沿用的审美、经验、标准与要求](references/inherited-standards.md)。业务事实、账号、素材和本人经历以接收者当前项目为准。
