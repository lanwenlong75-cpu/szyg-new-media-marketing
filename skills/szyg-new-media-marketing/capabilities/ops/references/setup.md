# 新媒体运营首次使用

本模块已随统一入口安装，无需另装同名独立skill。项目与岗位由统一入口配置读取，脚本目录为本GUIDE旁的scripts。

先执行 `python <总入口>/scripts/portable.py doctor --project-root <当前项目>`。缺依赖按报告从官方渠道配置。基础口播需要Python 3.10+、FFmpeg与ffprobe（libx264及libass），图形与模板另需要Node18+、Chrome和随包package-lock对应依赖。ASR使用当前助手可用转写或自行配置faster-whisper，模型缓存与GPU自检在接收电脑完成；没有转写或听辨时保留实际缺项。

新内容工作区可执行 `python <本模块>/scripts/ops.py init --root <当前素材工作区> --name 我的内容团队`，已有工作台先盘点保留，不覆盖媒体与业务记录。doctor、register、transcripts、index和start仍采用本模块原有流程。先确认实际可用端口，不能终止其他服务。安装本身不启动服务，不接账号，不发布。

动效依赖使用 `python <MOTION>/scripts/pipeline.py setup`，按随包锁文件安装到接收机，不带作者venv。发布使用官方蚁小二CLI及同步的官方skill，配置接收者自己的账号与密钥，不分发凭据；发布前采用其实际授权及实时回执。
