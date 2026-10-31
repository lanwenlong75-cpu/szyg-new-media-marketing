# 新媒体数字员工

**当前发行：2026.10.31.3。一个通用安装包，同时支持Codex和WorkBuddy。**

## 下载和开始

从[最新正式发行](https://github.com/lanwenlong75-cpu/szyg-new-media-marketing/releases/latest)下载唯一的通用安装ZIP：`szyg-new-media-marketing-universal-2026.10.31.3.zip`。微信收到的中文名通用包与GitHub附件内容一致。

完整解压，将包内`安装提示词.txt`发给你正在使用的软件。具体步骤见[先读我](先读我.md)，也可使用[在线安装提示词](INSTALL-PROMPT.md)。Windows Codex单文件启动器仍可使用，它会下载这一份通用包。

## 本版更新

将原来分开发送的Codex、WorkBuddy包合并为一个对外安装包。十四项岗位方法共用一份源文件，WorkBuddy所需的导入ZIP在接收端从同一份源文件准备；Windows官方基础Python随包提供。版本、文件清单和安装回执统一标注2026.10.31.3。原始隐私资料及私有业务事实不随包分发，旧发行保留。

## 包含的能力

新媒体主管、短视频编导、新媒体运营、公众号编辑、海报设计师、私域顾问、全栈工程师、产品经理、数字员工搭建师、视频制作引擎、单条视频归档、账号归档、小红书运营和课件打造师。安装一个Skill，按当前任务读取需要的内部能力。

## 构建

采用`distribution/build_universal.py --output <新输出目录> --runtime-cache <已核对摘要的官方运行时目录>`。通用包只包含一份`skills/szyg-new-media-marketing`；运行时加入最终包清单并逐文件核对。`distribution/build_release.py`仅供旧分包工程兼容核验，当前发行不用它生成对外分包。

方法、模板、工具、来源和验收边界见包内资料；专业工具和真实业务成品仍需接收端验证。第三方来源与许可见[THIRD_PARTY.md](THIRD_PARTY.md)。
