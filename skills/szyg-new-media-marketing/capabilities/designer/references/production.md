# 制作与可编辑交付

当前普通海报优先走 [整张海报生图](whole-poster-generation.md)。用户已明确要求字体、文案和版式由生图模型一起生成；本文件的HTML、图层编辑器与JSON脚本路线仅用于用户另行明确要求的可编辑工程、程序排版或批量换字。

## 选择方式

- 照片、插画、材质或视觉概念：使用现有图像生成/编辑能力，按参考角色明确目标，保存项目素材。
- 信息较多、中文必须精确、倒计时系列、证据案例或多版替换：在HTML/CSS或可编辑图层中排版。保留图像与文字层，导出时检查真实结果。
- 当前提供的HTML模板和构建脚本是离线起点，不代表“只能用这些版式”。实际需求不同就改模板或自定义工程。

## JSON输入

```json
{
  "kind":"product",
  "brand":"品牌名称",
  "brandTag":"出品方",
  "audience":"具体受众",
  "strap":"简短价值标题",
  "heroMessage":"有依据的主要信息",
  "features":[{"title":"真实应用","description":"简短解释"}],
  "delivery":"真实交付",
  "cta":"实际行动",
  "disclaimer":"必要条件",
  "image":"可选本地图片绝对路径"
}
```

`kind` 为 `product`、`countdown`、`case`。产品模板按三种风格适配，不要求固定六个项目；内容超出模板容量时拆页或调整布局，不删必要事实。

倒计时提供 `eventName`、`deadlineText`。正式稿必须有带时区的ISO `deadline`、时区标签 `timezone` 与口径 `countdownBasis`（`calendarDays` 自然日差，或 `durationDaysCeiling` 剩余时长按天向上取整）；构建脚本会计算 `countdownValue`、保存计算记录并拒绝过期稿。可用 `referenceNow` 固定试做的参考时间，否则用运行时刻。发布时按当前时间重算。没有真实活动只能 `sample:true` 并给示范 `countdownValue`，或待填写草稿。

案例另外提供 `caseTitle`、`beforeTitle`、`beforeText`、`afterTitle`、`afterText`、`process`、`evidence`，图片可用 `beforeImage` 和 `afterImage`。真实案例缺证明或结果，就先做过程案例或留空，不能自补数字。本轮示范文件均有 `sample:true`，不是客户效果证明。

构建会复制字体、许可证、实际引用的本地图片、输入JSON和文案到输出目录。模板内文字可以点击编辑，再保存修改后的HTML；跨目录移动时要一起移动 `assets` 和 `licenses`。PNG不是分层源文件，HTML保留独立文字和样式。

## 渲染

使用 `scripts/render_poster.cjs`，指定验证过的Playwright模块和浏览器。脚本等待字体与图像加载，对每个可见文本块检查溢出、文字互相重叠与画布边界，导出PNG与手机宽度预览。结果JSON保留问题。若检测失败，先修版式，再重新渲染。

浏览器渲染不依赖图像模型或新增API密钥。成品审美仍须由助手实际查看并记录判断；结构检查通过不能写“用户审美已通过”。

## 编辑器

Fabritor完整前端的代码与运行方式见工作区调研报告。模板JSON需符合Fabritor 3.1版本的 `fabritor_schema_version` 与 `fabritor-sketch` 画布字段；普通Fabric JSON不自动等于Fabritor工程。未做真实导入测试的文件不得称为已兼容。

默认交付PNG、HTML/可编辑工程、文案、来源和修改记录。若用户要印刷，再确认成品毫米尺寸、出血、色彩配置、字体和印厂要求，并另行制作印刷稿。
