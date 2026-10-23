# 新媒体营销数字员工 Skill

> **把团队的审美、经验和交付标准，装进一个可安装、可协作、可持续改进的 Codex Skill。**

**一个入口 · 14 项岗位能力 · 按项目自动选用 · 开源可迁移**

Portable Codex skill for new-media teams: content planning, design, video production, operations and skill governance.

[快速开始](#快速开始) · [看一次完整协作](#一条需求如何被处理) · [下载固定版本](https://github.com/lanwenlong75-cpu/szyg-new-media-marketing/releases/tag/v0.2.7-public.2026.10.23.1) · [查看能力版本](SOURCE-VERSIONS.json)

---

你可能遇到过：同一条口播，在一台电脑上剪得对味；把 Skill 装到另一台电脑，节奏、字幕、画面却变了。原因往往是判断方法、参考工程、字体和验收要求散落在不同地方，安装时只带走了其中一部分。

这个项目把**岗位方法、风格选择、制作工具和验收规则**收进一个统一入口。接入项目后，你照常提出需求，Codex 会先识别当前项目的角色和资料，再按任务读取需要的能力。新媒体主管负责跨岗位交接、版本核对与方法同步；你的客户、账号、产品和素材仍由你自己的项目提供。

## 本次更新

`2026.10.23.1` 同步海报57项参考目录与按用途检索、公众号文章四维拆解与可选文末承接流程，并补充编导的营销框架推导方法。完整变化见 [发行变更](CHANGELOG.md)。总入口仍为0.2.7，各模块源版本与摘要分别记录。

## 它能帮你做什么

| 你提出的需求 | 会用到的能力 | 重点保留的标准 |
|---|---|---|
| “这条口播帮我剪好，封面和校对材料也准备好” | 编导、视频制作引擎、新媒体运营 | 原声与重说判断、字幕、视觉路线、封面对应核验、版本与审阅材料 |
| “把这个观点做成公众号文章和小红书笔记” | 公众号编辑、小红书运营、海报设计 | 平台表达、事实来源、图文结构和当前项目的视觉要求 |
| “把课程资料变成能讲、能练的课件” | 课件打造师、产品经理、海报设计 | 教学目标、逐页脚本、练习评价和可编辑交付 |
| “让这些岗位以后按同一套方法配合” | 新媒体主管、数字员工搭建师 | 岗位路由、交接、反馈迭代与适用副本同步 |

这套 Skill **保留多种创作风格**，也保存选择风格的判断。剪辑时会结合本期素材、原稿和项目规则决定路线，并把字体、模板、参数和验收结果留在工程里，方便复查和迁移。

## 一条需求如何被处理

```mermaid
flowchart LR
    A[正常提出业务需求] --> B[读取当前项目角色与资料]
    B --> C[按任务选择岗位能力]
    C --> D[编导 / 设计 / 视频 / 运营等执行]
    D --> E[交付文件与专业验收]
    E --> F[确认后的反馈进入对应岗位方法]
    F --> C
```

例如你说：“这段口播有几次重说，做一版竖屏精剪，保留真人和原声，给我字幕、封面和校对入口。”已接入项目中的 Codex 会读取当前素材和要求，按需采用编导、视频制作引擎与运营方法；完成后分别核对语义取舍、声画、字幕、封面和交付版本。**安装成功只说明方法已就位，真实成片仍以这次素材的听校和观看结果为准。**

下面是包内的匿名技术示意，用于展示能力形式；它们不代表某位使用者的真实业务成片。

| 视频动效示意 | 可编辑课件示意 |
|:---:|:---:|
| ![匿名视频动效示意](skills/szyg-new-media-marketing/capabilities/motion/assets/demos/02-B.gif) | ![匿名课件封面示意](skills/szyg-new-media-marketing/capabilities/courseware/assets/examples/01-封面.png) |

## 14 项能力，一个入口

| 工作环节 | 内部能力 |
|---|---|
| 统筹与治理 | 新媒体主管 `SUPERVISOR` |
| 内容与产品 | 短视频编导 `DIRECTOR`、公众号编辑 `EDITOR`、小红书运营 `XHS`、产品经理 `PRODUCT`、课件打造师 `COURSEWARE` |
| 视觉与视频 | 海报设计师 `DESIGNER`、视频制作引擎 `MOTION` |
| 运营与承接 | 新媒体运营 `OPS`、私域顾问 `PRIVATE` |
| 技术与搭建 | 全栈工程师 `ENGINEER`、数字员工搭建师 `BUILDER` |
| 资料归档 | 单条视频归档 `ARCHIVE_VIDEO`、账号作品归档 `ARCHIVE_ACCOUNT` |

仓库只有一个可发现的 [`SKILL.md`](skills/szyg-new-media-marketing/SKILL.md)。岗位方法位于 `capabilities/<能力ID小写>/GUIDE.md`，按任务读取。你在**已接入的项目**里正常提需求即可，无需每次指定入口或先挑岗位。

## 快速开始

**方法一：把仓库链接交给 Codex。**

> 帮我安装 `https://github.com/lanwenlong75-cpu/szyg-new-media-marketing` 里的 `skills/szyg-new-media-marketing`，按 README 初始化我的团队与项目，并运行安装后检查。已有同名 Skill 或本地改进时先比对，保留我的工作区和资料。

**方法二：下载固定版本或克隆仓库安装。**

从 [Releases](https://github.com/lanwenlong75-cpu/szyg-new-media-marketing/releases/tag/v0.2.7-public.2026.10.23.1) 下载 ZIP 并解压，或运行：

```powershell
git clone https://github.com/lanwenlong75-cpu/szyg-new-media-marketing.git
cd szyg-new-media-marketing
python install.py --archive-legacy
```

Windows 也可运行 `Install-Codex-Windows.cmd`。安装器会校验包内文件、把旧独立入口归档到技能扫描目录外，并初始化一个**不预填客户、账号或业务事实**的团队工作区。已有统一入口的本地修改或跨发行版升级需要先比对迁移，安装器会保留现状并停止。详细步骤见[开始使用](开始使用.md)。

安装后运行 `python <已安装Skill目录>/scripts/portable.py doctor` 检查本机工具；现有项目用 `portable.py bind` 接入。视频制作按需准备 Python、FFmpeg、Node、浏览器与转写环境，具体清单见[接收电脑自检](SELF-TEST.md)。

## 这套方法从哪里来

它来自持续的多岗位内容生产与跨电脑交付复盘：把有效的审美判断、失败纠正、版式参数、模板、工具和验收要求沉淀为可读取的方法。新媒体主管维护能力注册和版本关系，让改进落到对应岗位，再同步给适用的副本。

公开版保留可迁移的方法，排除了原使用者身份、客户与账号资料、产品事实、私有照片和视频、凭据及反馈原文。课件示意重新制作成匿名、可编辑的样例。你的业务事实、授权素材与品牌选择始终来自你自己的项目。

当前公开发行对应总入口 **0.2.7**、14 项能力；视频制作引擎源版本为 **3.14.0-rc.1**。各岗位版本与源/公开入口摘要见[版本清单](SOURCE-VERSIONS.json)。本机隔离安装、14 岗位路由和匿名剪辑技术样例已验证；接收电脑的工具环境、真实口播听校和审美认可需要用实际素材完成。完整范围见[验收与边界](验收与边界.md)。

## 一起完善

如果你也在用 Codex 做内容团队协作，欢迎通过 [Issues](https://github.com/lanwenlong75-cpu/szyg-new-media-marketing/issues) 提交可复现的问题、适用场景和改进建议。请先移除客户原文、账号凭据和私有素材。觉得这套方法有用，可以给项目一个 Star，让更多需要稳定交付标准的人找到它。

本仓库原创整合文件采用 [MIT License](LICENSE)；第三方方法、字体和视频引擎按各自许可证使用，见[第三方说明](THIRD_PARTY.md)。
