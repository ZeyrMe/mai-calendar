# 今天是什么日子

`zeyr.mai-calendar` · 节日、倒计时与待办提醒。

开发基线 MaiBot 1.4.8 / SDK 2.23.0。可独立安装，其他 zeyr 插件仅通过公开 API 自动联动。

当前为第二批骨架：已完成配置、清晰的 API 预留和契约测试，但尚未开放节日/调休/待办运行时工具。不会伪装成已实现功能。

安装时将整个目录同步到宿主 plugins；运行 config.toml 由 SDK 生成。实例名单、个人资料和密钥只填运行配置，不提交。

检查：`python -m pytest`，开发依赖见 pyproject.toml。
