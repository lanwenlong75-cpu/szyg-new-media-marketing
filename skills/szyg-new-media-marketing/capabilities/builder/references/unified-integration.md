# 新岗位接入统一总入口

用户希望员工未来并入总Skill，或当前已用统一入口时，先查看真实总入口、项目profile和能力注册表。知识与产品事实留在员工项目，通用岗位方法进入能力模块。不要先做一套平行独立入口再要求用户迁移。

已有岗位直接绑定现用内部GUIDE。没有对应岗位时，基于用户授权创建真实方法、必要引用和验收；保持总入口薄、岗位方法独立、对象事实外置。仅当用户另行要求独立分发时打独立包，不能从停用包恢复当前入口。

## 本机接线

1. 在总入口`capabilities/<能力ID小写>/GUIDE.md`维护唯一方法，保留frontmatter名称、description与版本；相对资源从GUIDE目录展开。
2. 主管`skill同步注册表.json`登记唯一ID、职责、`source.owner=szyg-new-media-marketing`及内部entry；新增员工登记`员工注册表.json`。保留既有成员和副本策略。
3. 新项目写AGENTS与`.agents/new-media-profile.json`，明确role、primary_capability、focus、registry、governance_root及本项目业务范围。员工配置的worker_skills与capability_binding指向相同模块，maintenance_root只允许本员工维护本模块。
4. 当前build_employee.py的plan/apply仍只接受独立SKILL.md包，check已支持模块。统一模块模式先以worker_skills=[]建档，再增量绑定GUIDE；不得为绕过检查复制GUIDE成独立SKILL.md。中间状态不作为最终交付。
5. GUIDE保留反馈管理块及唯一的`本地规则修订：0。`初始化标记（迁移保留真实修订号），否则更新工具会拒绝。接入模块反馈工具`module_iteration.py`的工作区包装入口，规则文件放模块references，台账使用`@capability/`摘要键。初始化或迁移保留冻结前台账、摘要、preserved_revision、模块基线及来源复制清单；初次接入明确type=initial_binding，不编造旧用户认可事件。
6. 修改前备份并登记来源与摘要，回读真实目标。既有模块有维护台账时经所属员工迭代机制变更，不重置历史规则与反馈。

## 验收

执行hub.py context/resolve --instructions/check核对新项目以及一个原项目；执行build_employee.py check --root核对模块绑定、来源、对象及反馈链；对新方法做一个真实小任务，保留事实与建议分离、具体交付和下游缺项。脚本/配置检查、实际专业效果、用户认可和跨岗位试用分别报告。

交付当前模块路径、版本、配置/注册表变更和必要合并说明。其他机器的路径、账号与安装依赖单列；本机通过不代表跨设备可用。用户未来才安排的岗位串联，先给交接资料，不把准备状态写成已派单或已发送。
