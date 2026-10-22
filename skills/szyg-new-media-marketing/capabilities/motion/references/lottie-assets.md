# 可选外部动画素材接口

需要辅助动画时，读取 [外部服务地址登记](../source-notices/external-services.json)，从其中真实的 animation_catalog_base 获取 manifest、annotations 或按 preset 下载文件。该服务属于外部依赖，地址和许可按登记与实时结果核对；本地维护者是 duli。

先查看 manifest 并按本期语义选择动画，再把实际文件保存到本期工程。下载后检查 JSON、渲染效果及来源许可；使用已提供的用户素材也可以完成制作。外部素材库不代替整片分镜、真实人物或业务证据。

接口为只读 GET，路径包括 /manifest、/annotations 和 /file/{preset}.json。请按登记中的实际 base 地址构造请求，处理 HTTP 状态与 CORS；无 API Key 不代表任意素材都获得再分发许可。下载失败时如实记录依赖，不能虚构文件或生成端点。
