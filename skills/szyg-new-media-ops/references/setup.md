# 新媒体运营首次使用

安装本岗位完整目录即可取得运营程序、视频制作和资料采集源码，不另安装功能型Skill。SKILL_DIR是本岗位SKILL.md所在目录，ROOT是接收者当前项目。

先执行`python SKILL_DIR/scripts/ops.py doctor --root ROOT`。需要视频制作时再执行`python SKILL_DIR/capabilities/video-production/scripts/pipeline.py doctor`。基础剪辑需要Python 3.10+、FFmpeg及ffprobe，动效还需Node.js、Chrome与工具锁文件依赖；缺项按实际报告配置，安装源码不表示这些外部软件已经可用。

新工作区执行`python SKILL_DIR/scripts/ops.py init --root ROOT --name 我的内容团队`；已有工作台先盘点保留。视频运行依赖可用`python SKILL_DIR/scripts/ops.py bootstrap --root ROOT --editing`配置，首次联网安装按本次用户授权执行。不要运行不存在的旧总入口命令。采集运行时接入按[source-archive.md](source-archive.md)。

发布使用官方蚁小二CLI与正式规则，账号与密钥在使用者自己的环境配置；正式发布按本次授权及实际回执验收。安装本身不启动服务、不接账号、不发布。
