# 今天是什么日子

`zeyr.mai-calendar` · 节日、倒计时与待办提醒。

开发基线 MaiBot 1.4.8 / SDK 2.23.0。可独立安装，其他 zeyr 插件仅通过公开 API 自动联动。

第二批已实现：本地节假日/工作日判断、日期覆盖、固定节日/生日/倒计时、逻辑日、self/mutual/other 待办、`get_day_context` / `get_schedulable_todos` / `manage_todo` API、`query_calendar` / `manage_todos` 工具和 `/待办 + ...` 短命令。`other` 只提醒，不进入 `mai-day` 的生活日程。

安装时将整个目录同步到宿主 plugins；运行 config.toml 由 SDK 生成。实例名单、个人资料和密钥只填运行配置，不提交。

检查：`python -m pytest`，开发依赖见 pyproject.toml。
