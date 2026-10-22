# 搭建说明与文件操作

助手把用户的自然语言与上下文整理成JSON。脚本需要Python 3.9或更高版本，只使用标准库，按传入的路径工作，技能本身不依赖作者机器上的盘符或知识库。

最小示例：

```json
{
  "schema": "digital-employee-build-v1",
  "parent_dir": "D:/员工项目",
  "employee_name": "公众号编辑",
  "role": "wechat-editor",
  "service_objects": [],
  "worker_skills": [],
  "imports": []
}
```

`parent_dir`使用用户指定的绝对父目录；`folder_name`可覆盖默认“数字员工-岗位名的知识库”；`role`使用assets/role-profiles.json中的键，自定义岗位用`profile`给出label、entity_kind、entity_prefix、mission、reasoning_lens、entity_modules、outputs、acceptance及facets。

| 字段 | 内容 |
|---|---|
| employee_name | 员工显示名称 |
| project_display_name | 用户指定的应用项目名称；只登记目标名称，应用修改另行回读 |
| usage_mode | workspace为真实工作区建档，simulation为明确标识的模拟试用；合成资料或测试skill使用simulation |
| folder_name | 最终目录名，可省略 |
| existing_dir | 明确要继续使用或重命名的现有目录；目标相同时复用，目标不同时可恢复改名 |
| context | 用户已知目标、受众、语气、工作范围与待确认事项，使用对象而非猜测事实 |
| service_objects | `{id, name, facts, accounts}`列表；未知信息留空 |
| default_service_object_id | 已登记的当前默认对象；多个对象没有默认时按任务指定 |
| worker_skills | `{source, primary, reviewed_for_role, capability_notes}`列表；恰好一个primary。助手读取真实skill并确认它支持该岗位时填写reviewed_for_role=true；测试包及未审查技能保持false |
| imports | `{source, scope, entity_id, category, allowed_root}`列表；source为实际文件，scope为shared、entity、reference或pending |
| allowed_source_roots | 获用户授权的来源根目录；文档附件闭包只在这些目录内读取 |

对于imports，主体资料使用scope=entity并填写登记过的entity_id；category可使用该主体模块名。知识文件复制进90来源档案，MD另建对应工作阅读版；附件按链接追踪。作者、说话人、公开许可及历史状态继续以原文为准。

对目录进行迁移时，先筛选具体文件，形成imports，不把整个资料盘盲目入库。源文件在allowed_root或allowed_source_roots内，拒绝符号链接与越界读取。未授权的依赖和缺失附件列入依赖检查，脚本不自行扩大权限。

角色skill复制完整包。脚本拒绝包内符号链接，不执行复制来的脚本。包内的绝对机器路径、命令中的旧盘符与外部账号依赖需要助手审查并登记；Markdown文件引用的越界、缺失目标由检查报告指出。

岗位skill的原始包另存为`_管理/岗位skill原始快照/`，本地工作版位于`.agents/skills/`，两者分别记录。工作版接入反馈与能力迭代协议、范围规则和迭代记录模板，员工配置默认启用本地自主改进，并随工作区携带标准库更新工具。岗位判断、流程、模板、脚本与验收均可根据真实反馈更新，相关文件必须有候选、基线、依据与验证。来源校验保护原始快照；工作版按初始摘要和已记录修改链核对，新文件登记在链中。Python缓存不作为静态能力文件的摘要基线。

1.2把当前主岗位skill完整工作包纳入跟踪，保留1.1纯规则更新接口。已有员工增量接入新协议和工具后，首次文件升级可从原生成清单补齐基线，已确认规则与版本继续保留；有未记录修改时先核对现状。不会把升级当成重新建库或重新归零。

已有不同内容的目标文件会在预检时报告冲突，整个生成操作暂停，原目录保持原状。助手读取冲突内容后，按用户已授权范围做增量整合并保留备份，不能把“强制覆盖”当作通用解决方式。目录改名只在源和目标为指定父目录的直接子目录时自动执行，盘根、链接和Git目录不自动移动。

脚本建立的是本地文件工作区。应用侧项目添加、重命名与来源关联使用宿主受支持能力，分别回读状态。当前环境没有此能力时，把“本地目录已完成”和“应用项目待接入”分别报告。
