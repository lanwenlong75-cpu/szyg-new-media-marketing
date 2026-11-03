# 数字员工独立Skill

**当前发行：2026.11.03.1。十四个独立Skill，各自维护、安装和升级。**主管负责团队协作与版本治理，各岗位直接读取自己的SKILL.md。

## 快速开始

从[最新Release](https://github.com/lanwenlong75-cpu/szyg-new-media-marketing/releases/latest)下载`szyg-digital-employees-independent-2026.11.03.1.zip`安装全部，或下载所需岗位的单独安装包。微信收到的中文名包与GitHub对应附件字节一致。完整解压，复制“安装提示词.txt”给Codex或WorkBuddy即可开始；只安装某岗位可直接说明。

```text
请帮我安装或升级这个数字员工Skill安装包，发行2026.11.03.1。完整解压并读取先读我.md，按我正在使用的软件安装所需的独立岗位Skill，没有指定则安装全部，创建或接入我的项目。保留已有资料和本地改进；有旧版先备份、比对迁移。完成后告诉我每个实际安装的Skill名称、版本和使用入口。
```

没有本地包时，将下面的提示词交给能访问GitHub的助手：

```text
请从 https://github.com/lanwenlong75-cpu/szyg-new-media-marketing 的最新正式Release下载数字员工独立Skill安装包，核对附件SHA-256并完整解压。读取先读我.md，按我正在使用的软件安装所需的独立Skill并创建项目。保留已有资料和本地改进；有旧版先备份、比对迁移。完成后告诉我实际安装的名称、版本和入口。
```

具体的安装、创建项目、改名和已有版本迁移见[先读我](先读我.md)。Codex可用install.ps1 -Skill 岗位名，WorkBuddy运行Prepare-WorkBuddy.ps1生成对应的独立导入ZIP，按宿主实际界面导入。

## 岗位与版本

| 岗位 | Skill | 自身版本 | 方法 |
| --- | --- | --- | --- |
| 短视频编导 | `szyg-short-video-director` | 1.1.1 | [查看Skill](skills/szyg-short-video-director/SKILL.md) |
| 公众号编辑 | `szyg-wechat-editor` | 0.4.2 | [查看Skill](skills/szyg-wechat-editor/SKILL.md) |
| 海报设计师 | `szyg-poster-designer` | 0.1.1 | [查看Skill](skills/szyg-poster-designer/SKILL.md) |
| 全栈工程师 | `szyg-fullstack-engineer` | 1.0.1 | [查看Skill](skills/szyg-fullstack-engineer/SKILL.md) |
| 私域顾问 | `szyg-private-domain-advisor` | 0.1.1 | [查看Skill](skills/szyg-private-domain-advisor/SKILL.md) |
| 新媒体运营 | `szyg-new-media-ops` | 1.0.10 | [查看Skill](skills/szyg-new-media-ops/SKILL.md) |
| 视频制作引擎 | `szyg-duli-motion-video` | 3.14.0-rc.2 | [查看Skill](skills/szyg-duli-motion-video/SKILL.md) |
| 数字员工搭建师 | `szyg-digital-employee-builder` | 1.2.2 | [查看Skill](skills/szyg-digital-employee-builder/SKILL.md) |
| 新媒体主管 | `szyg-team-orchestrator` | 1.1.1 | [查看Skill](skills/szyg-team-orchestrator/SKILL.md) |
| 单条视频归档 | `szyg-archive-social-video` | 0.1.1 | [查看Skill](skills/szyg-archive-social-video/SKILL.md) |
| 账号作品归档 | `szyg-archive-social-account` | 0.1.1 | [查看Skill](skills/szyg-archive-social-account/SKILL.md) |
| 产品经理 | `szyg-product-manager` | 0.2.1 | [查看Skill](skills/szyg-product-manager/SKILL.md) |
| 小红书运营 | `szyg-xiaohongshu-operator` | 0.2.2 | [查看Skill](skills/szyg-xiaohongshu-operator/SKILL.md) |
| 课件打造师 | `szyg-courseware-designer` | 0.2.1 | [查看Skill](skills/szyg-courseware-designer/SKILL.md) |

## 管理和更新

只改某岗位，就维护该目录并增加它自己的版本；整套发行另标日期版本。catalog.json登记各岗位实际版本与文件摘要。视频制作等跨岗位依赖按任务声明，不把其他岗位隐藏在总入口中。旧Release和旧附件保留，初始专业方法、审美及验收标准随岗位迁移，私人业务资料排除。

构建：`python distribution/build_independent.py --output 新输出目录 --runtime-cache 官方运行时目录`。同时生成整套和每个岗位的独立离线安装包。来源与许可见[THIRD_PARTY](THIRD_PARTY.md)及各Skill的许可文件。
