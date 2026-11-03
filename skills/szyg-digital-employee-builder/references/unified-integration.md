# 独立Skill接入

新岗位在独立目录维护SKILL.md、references、scripts及必要assets。名称与目录一致，版本由本岗位维护，普通业务请求可自动发现；知识、账号、客户和业务事实留各自项目。

已有岗位直接绑定当前SKILL.md。主管注册表登记ID、skill_name、source.owner及真实entry；项目profile的entry、员工worker_skills和capability_binding指向同一入口。maintenance_root为实际员工工作区。

新员工优先用build_employee.py的plan/apply接入独立技能。旧工作区迁移先备份配置、反馈台账和当前Skill，保留全部原始事件与证据；结构变化写迁移记录和新基线，不冒充新增人类认可。后续通过所属员工迭代工具修改实际工作版。

以主管scripts/skills.py context/resolve/check核对注册入口，以build_employee.py check检查真实项目、资料与反馈链。脚本验证和专业成品按实际范围分别记录。
