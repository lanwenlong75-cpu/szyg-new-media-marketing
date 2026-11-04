# 包内课件制作工具

本岗位自带 `scripts/build_courseware.py`，使用 Python 3.10+ 标准库，读取随包六页可编辑样板并生成真实 PPTX、讲师 notes、内容及备注回读 HTML、结构报告。不需要安装 presentations、documents 或 pdf Skill。Windows 安装包中的私有 Python 可直接运行；助手先发现安装回执中的运行时或当前宿主解释器。

先运行 `python scripts/build_courseware.py --layouts` 查看六种版式的文字字段。根据课程目标选用并重复所需版式，不限六页或固定顺序。输入结构如下；每页必须显式填写该版式的全部字段，可用空字符串清除不需要的文字，避免把样板示例带入正式课件。

```json
{"title":"课程名称","font":"Microsoft YaHei","slides":[{"layout":"cover","text":{"title":"本节课要解决什么","emphasis":"用一句判断说清","subtitle":"本期真实课程资料"},"notes":"讲师实际开场话术、来源与限定。"},{"layout":"closing","text":{"heading":"课后行动","message":"完成一次练习\n带回真实结果"},"notes":"说明成品、完成条件和评价方式。"}]}
```

运行：`python scripts/build_courseware.py --input 本次逐页稿.json --output 新版本目录`。相对图片路径从输入 JSON 所在目录展开。需要插入证据时，每页可加 `images` 数组，项为 `{"path":"截图.png","x":80,"y":160,"width":1120,"height":430}`；按1280×720坐标框等比容纳真实PNG/JPEG，保持原图，正文仍为可编辑文本。证据页的 `evidence_note` 在图片已提供时可显式清空。

脚本复制所选样板页的原生文字、形状和箭头，写入真实备注，校验所有内部关系，并保留已存在输出。它是制作起点，可继续在可编辑对象中改版，不把六种样板当成全部课程的固定风格。复杂表格、原生统计图、动画或视频需根据本次需求直接编辑Open XML或在可用演示软件中完成；不要求再装功能型Skill，不把未完成的高级对象写成已经生成。

`handout.html` 供核对正文、来源和备注，可用浏览器打开或打印；它不是 PPTX 视觉渲染。Windows已装PowerPoint时，运行 `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/render_pptx.ps1 -InputPptx 成品.pptx -OutputDirectory 新预览目录` 导出逐页PNG。其他系统用本机演示软件打开PPTX并导出预览；没有演示软件时明确记录未完成真实渲染，不能将结构报告当作视觉验收。

字体不随PPTX嵌入。`font` 仅指定当前机器实际可用的中文无衬线字体；不要承诺接收者已经安装它。Word/PDF、Google Slides或复杂媒体按实际环境使用现有文件工具或演示软件，核对真实输出，不以某个功能型Skill名称作为前置安装条件。
