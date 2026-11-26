# 今天是什么日子

`zeyr.mai-calendar` · 节日、倒计时与待办提醒。

开发基线 MaiBot 1.4.8 / SDK 2.23.0。可独立安装，其他 zeyr 插件仅通过公开 API 自动联动。

第二批已实现：本地节假日/工作日判断、日期覆盖、固定节日/生日/倒计时、逻辑日、self/mutual/other 待办、会话范围校验、成功回执去重的到期提醒、`get_day_context` / `get_schedulable_todos` / `manage_todo` API、`query_calendar` / `manage_todos` 工具和 `/待办 + ...` 短命令。`other` 只提醒，不进入 `mai-day` 的生活日程；self/mutual 待办变化会由 `mai-day` 投影到有效日程。管理接口会校验会话归属，self/mutual 修改需要本地管理员或 `mai-circle` 管理员；服务提醒在 `mai-day` 存在时使用精确短授权。

安装时将整个目录同步到宿主 plugins；运行 config.toml 由 SDK 生成。实例名单、个人资料和密钥只填运行配置，不提交。

检查：`python -m pytest`，开发依赖见 pyproject.toml。


## v2.5 第一批：范围与原生控制台

新增独立 `[scope]`：mode 默认 all；groups / privates / users 接受 `group:标识` / `private:标识` / `user:标识`，可带平台前缀（默认 qq）。mode=whitelist 只允许命中对象；mode=blacklist 排除命中对象；all 允许所有对象。exclude 始终优先。allow_private=false 仅放行名单明确指定的私聊，主动私聊仍需单独配置目标。

可用 `@set:名称` / `@tag:名称` 复用 mai-circle 集合/标签；缺席时按空集合降级，不影响直接对象。受限模式在没有真实会话身份时跳过业务，消息仍正常进入宿主。重启后的会话身份缓存由入站消息恢复。

WebUI 配置页提供运行状态面板与“刷新公共集合缓存”按钮，不调用模型、不发送聊天。范围分组默认折叠；字段采用中文标签与结构化条目卡片。

workday_overrides 改为 date / is_workday 条目列表，旧字典配置自动转换。

本批提供公共基础设施。后续业务能力见下方 0.2.0 说明。旧配置保持可读，Runner 规范化写回后采用新结构；回退旧代码前需恢复相应配置快照。实例 config.toml 仍不进入 Git。


## 0.2.0 · v2.5 业务增量

历法/重要日子/一次性事项三表区分；lunar-python 提供农历、节气、除夕与显式农历年重复日期，超出 chinese_calendar 官方年份标为未经验证。自然时间支持“明天 20:00”“12-01 09:30”“周五晚上8点”。care_note 只在原会话提示、不定时催促、不进入日程。自然语言 self/mutual 可以形成约定并查询生活档期；强制 /待办 操作继续鉴权。控制台可刷新历法和清理已结束事项。

接口保持 `@API(..., version="1")`，缺少可选插件时自动降级。模型生成、网络和宿主上下文效果仍需结合实例配置验收；离线测试不等同于真实聊天送达。
