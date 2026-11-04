# 整号资料采集（新媒体运营内部工具）

Run an evidence-first batch workflow. Treat the creator profile as a changing collection of independent sources.

## Resolve the project

1. Use an explicitly supplied project root.
2. Otherwise use `LANDULI_PROJECT_ROOT` when set.
3. Otherwise use the active workspace only when it contains `AGENTS.md`.
4. Stop and ask for the project root when multiple candidates remain.
5. Read the project `AGENTS.md` before writing knowledge-base content.

For a new computer or missing automation files, read
[references/portable-setup.md](references/portable-setup.md) and install the
bundled runtime into the selected project. Never copy credentials between
computers.

Before building an inventory or analysis report, read
[references/inventory-and-analysis-schema.md](references/inventory-and-analysis-schema.md).

## Profile inventory

1. Open the profile in the signed-in browser.
2. Resolve share links to the canonical profile URL and record the platform user ID.
3. Capture the displayed work count.
4. Scroll until the video list stops growing and the captured count matches the displayed count.
5. Extract each canonical video URL, platform video ID, title, publication time when visible, and display order.
6. Deduplicate by `platform:video_id`.
7. Compare IDs with the project state index and raw archive.
8. Save `profile-inventory.json` before downloading anything.

For unsupported platforms, use the browser or approved platform API. Do not infer a complete inventory from the first visible screen.

## Cost and acquisition

1. Check the current endpoint price and available credit before a batch.
2. Report the projected maximum request count and cost.
3. Require explicit approval when the user has not already authorized the expected spend.
4. Use exactly one billable acquisition request per missing video.
5. Save the full API response before downloading media.
6. If a CDN download fails after a saved response exists, resume from that response with `续传TikHub视频.ps1`. Never repeat the billable API request.
7. Reuse existing media when the platform ID and media hash match.
8. Keep the API credential encrypted with Windows DPAPI and never print decrypted text.

Preferred Douyin entry points after runtime installation:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<project>\自动化\批量采集抖音博主.ps1" `
  -InventoryPath "<profile-inventory.json>" `
  -OutputRoot "<audit-root>\videos"
```

If an item has `tikhub-response.json` but lacks a valid `source.mp4`, run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<project>\自动化\续传TikHub视频.ps1" `
  -OutputDirectory "<item-directory>" `
  -SourceUrl "<canonical-video-url>"
```

## GPU transcription

1. Run the GPU check before the batch:

   `powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<project>\自动化\check-social-video-runtime.ps1"`

2. Retry once with `-Repair` when dependency repair is appropriate.
3. Report the concrete error before any CPU fallback.
4. Require CUDA for long-form video unless the user explicitly accepts CPU.
5. Use `large-v3-turbo`, word timestamps, and `fast` mode by default.
6. Use `accurate` for noisy audio, dialect, overlapping speakers, dense names/numbers, or maximum-accuracy requests.
7. Batch archive downloaded videos with:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<project>\自动化\批量归档抖音视频.ps1" `
  -AcquisitionRoot "<audit-root>\videos" `
  -StatePath "<audit-root>\archive-state.json"
```

8. At the end, verify every row reports `RuntimeDevice=cuda`. Re-run any legacy CPU item with `-RequireGpu -TranscriptionMode accurate`.

## Verification

For every video:

1. Confirm the transcript starts near `00:00`.
2. Confirm the final timestamp covers the complete media duration.
3. Preserve the original transcript and word-level JSON.
4. Generate contact sheets or representative frames across the full duration.
5. Check chapter boundaries, on-screen captions, names, numbers, quoted passages, and low-confidence spans.
6. Mark unresolved wording `[听不清]` and unresolved speakers `[说话人待确认]`.
7. Keep revenue, growth, savings, headcount, user count, and outcome claims labeled `视频当事人自述` until independently verified.

Do not analyze from titles, summaries, or partial captions.

## Per-video analysis

Produce one entry for every profile video:

- source ID, title, duration, and canonical URL;
- project or topic;
- what the full transcript says;
- extracted SOP;
- what the user can learn;
- verification boundary;
- links to original and organized transcripts.

Then produce a master account report that groups the creator's content themes and extracts a reusable content-production method.

## Knowledge-base compilation

1. Keep external material in the external/source layer until the user approves promotion.
2. Preserve speaker attribution and source links.
3. Follow the project's daily compilation limit. Analyze the full batch, then compile only the allowed highest-value sources.
4. Update the source index, compilation log, directory overview, and state CSV.
5. Collect and anonymize the first 50 public comments when the request includes audience,传播, or topic analysis.
6. Run `python <OPS>/scripts/check_archive.py --transcript <raw-transcript.json>`; apply additional project checks only if those checks are configured in the selected project.

## Final report

Report:

- profile works found;
- reused, downloaded, failed, and resumed counts;
- API requests, projected/actual cost, and remaining credit when verified;
- total media size and duration;
- transcription device and speed;
- analyzed, compiled, and pending counts;
- validation results;
- clickable paths to the master report and transcript index.

During downloads and transcription, send a concise progress update at least once per minute.



## 可迁移初始标准

每次使用本工具先读[沿用的审美、经验、标准与要求](references/inherited-standards.md)。接收者反馈从空白开始，初始标准继续执行。真实业务事实、账号和素材只取当前使用者项目。自动化脚本路径从本次项目根展开；随包源码位于OPS/capabilities/source-archive/account/scripts，参考文件相对当前GUIDE展开。





## 开源初始标准

使用本工具前读取[沿用的审美、经验、标准与要求](references/inherited-standards.md)。业务事实、账号、素材和本人经历以接收者当前项目为准。


这些是新媒体运营岗位内部的方法、程序和资源，不是另一个Skill或数字员工。岗位入口是所属运营Skill的SKILL.md；工具改进由运营维护，服务对象、素材与账号始终取本次项目。

OPS是本工具所属的新媒体运营Skill目录。项目没有Wiki体系时，来源记录和全文保存在本次任务归档目录，不创建或写入其他项目的知识层。
