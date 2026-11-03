# Inventory and analysis schema

## Profile inventory

Save UTF-8 JSON:

```json
{
  "platform": "douyin",
  "profile_name": "creator name",
  "profile_url": "https://www.douyin.com/user/...",
  "platform_user_id": "public user id when available",
  "displayed_work_count": 24,
  "scanned_at": "2026-07-30T00:00:00+08:00",
  "videos": [
    {
      "order": 1,
      "video_id": "1234567890123456789",
      "url": "https://www.douyin.com/video/1234567890123456789",
      "title": "title",
      "published_at": null,
      "status": "待采集"
    }
  ]
}
```

Allowed inventory status values:

- `待采集`
- `已存在`
- `采集失败`
- `已下载`

## Required raw archive files

For every source:

```text
00-来源信息.md
01-逐字稿-原始.md
01-逐字稿-原始.json
02-逐字稿-整理.md
source.mp4
```

Optional:

```text
cover.jpg / cover.webp
03-评论语料.md
```

## Analysis entry

Use this structure:

```markdown
## <order>. <title>

- source_id:
- type:
- duration:
- source URL:
- organized transcript:

### Project or topic

### What the full transcript says

### Extracted SOP

1.
2.
3.

### What the user can learn

### Verification boundary
```

## Batch acceptance

- Inventory count matches the profile count or explains the discrepancy.
- Every inventory ID is unique.
- Every downloaded video has an acquisition result and saved API response.
- Every transcript covers the complete duration and has word timestamps.
- Every transcription runtime is CUDA when GPU is required.
- Every video has an analysis entry.
- External claims remain attributed to the video speaker.
- Wiki compilation respects the project's per-run limit.
- Broken links, missing metadata, and prohibited patterns equal zero.
