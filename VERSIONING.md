# 独立Skill版本

每个Skill的metadata.version和版本信息.json为自身版本；catalog.json逐个登记。方法或结构改变时只提高受影响Skill的版本，不因别的岗位变化连带升级。distribution_release标记该Skill最近一次纳入当前发行的日期版本，自身版本相同的文件可保持原样复用。

整套发行号采用YYYY.MM.DD.sequence。GitHub与微信对应包字节一致，包名、提示词、清单和安装回执标明发行号及实际Skill版本。封存版本不覆盖；已有本地改进先比对、迁移与验收，保留历史。
