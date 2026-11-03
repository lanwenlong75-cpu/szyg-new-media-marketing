# 已接入的开源产品探索能力

2026-10-18固定版本接入，未设置后台更新。名称为上游项目；当前实际调用仍为总入口内部PRODUCT。原始SKILL.md在本模块命名为METHOD.md，内容未改，防止产生平行独立入口。

| 上游与固定commit | 当前安装内容 | 实际使用入口 |
|---|---|---|
| [phuryn/pm-skills](https://github.com/phuryn/pm-skills/tree/07b34f64ee828df08953f505b7f747aef85ae7c6) | 7个技能：新/现产品创意、四类假设、假设优先级、机会方案树、实验设计、访谈脚本 | [产品探索流程](discovery-and-brainstorming.md)按需要路由 |
| [alirezarezvani/claude-skills](https://github.com/alirezarezvani/claude-skills/tree/19392f7a08264ed00486a251f5b2098321771f94) | Product Discovery完整技能目录，包含方法、框架及原始assumption_mapper.py | 同上；安全JSON包装脚本调用原始评分对象，补输入检查与证据状态 |
| [BMAD-METHOD](https://github.com/bmad-code-org/BMAD-METHOD/tree/85186edf6b5918152af9f99101a13307865ec7b8) | 原始brain-methods.csv方法库，本轮选用其中5种创意方法 | 同上，在发散受阻时选用适合的方法 |

原始许可： [PM Skills MIT](../third_party/phuryn-pm-skills/LICENSE)、[Claude Skills MIT](../third_party/alireza-product-discovery/LICENSE)、[BMAD MIT](../third_party/bmad-brainstorming/LICENSE)。原作者版权保留。[逐文件来源与摘要](../third_party/source-manifest.json)、[归属说明](../third_party/THIRD_PARTY.md)。

适配：用户通过自然语言与产品经理讨论；不需要调用上游Claude命令，不带入软件开发阶段、固定数目、固定周期、发布动作或其他项目的身份。第三方材料只提供专业方法，当前项目约定与用户授权继续生效。没有启动BMAD项目、Superpowers工作流、后台服务或上游安装钩子。

调研过的Superpowers作为完整开发流程参考，当前不接管产品经理对话；Product-Manager-Skills实际LICENSE是CC BY-NC-SA 4.0，本轮仅研究，不复制到现用模块，便于当前商业产品及后续总Skill分享保持清晰来源范围。该选择依据实际文件，并非仅看GitHub徽章。
