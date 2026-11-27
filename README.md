# 今天是什么日子（mai-calendar）

为麦麦提供日历、节假日与待办事项支持

## 功能介绍

- **年度调休自动缓存**：自动拉取并本地缓存年度法定节假日与补班 JSON，不依赖每年升级 Python 包，断网时自动退回本地节假日库。
- **公历、农历与节气**：内置二十四节气和常见传统/公历节日；个人生日与纪念日显式区分 `solar`（公历）与 `lunar`（农历），不瞎猜换算。
- **四类待办与日常关心**：严格区分 `self`（自己日程）、`mutual`（双方约定）、`other`（帮人提醒）与 `care_note`（日常关心，不在聊天里发冰冷闹钟）。
- **自然时间解析**：支持“明天 20:00”、“周五晚上8点”、“12-01 09:30”等自然表达，创建前可自动联动 `mai-day` 检查时间冲突。

## 如何使用

1. 将 `mai-calendar/` 放入宿主 `plugins/` 目录并重启，打开 **今天是什么日子** 配置页。
2. 确认 **本地时区**（默认为 `Asia/Shanghai`），在 **重要日子与生日** 中添加生日或倒计时（农历生日将历法选为 `lunar`）。
3. 可在控制台面板查看当前公农历状态与调休缓存年份，也可点击 **同步年度调休表** 立即更新。

<details>
<summary>config.toml 配置示例</summary>

```toml
enabled = true
timezone = "Asia/Shanghai"
enable_solar_terms = true
enable_traditional_lunar_holidays = true

[[dates]]
title = "老朋友生日"
date = "2000-08-15"
calendar = "lunar"
yearly = true
kind = "birthday"
reminder_days = 3

[[workday_overrides]]
date = "2026-10-10"
is_workday = true
```

</details>

## 配置说明

| 配置项 | 默认值 | 说明 |
|---|---|---|
| `dates` | `[]` | 重要日期、生日与倒计时，需显式指定公历或农历 |
| `holiday_sync` | 自动开启 | 高级设置：年度调休 JSON 镜像同步与本地缓存配置 |
| `workday_overrides` | `[]` | 高级设置：优先级最高的工作日/休息日手动覆盖 |
| `care_note_enabled` | `true` | 高级设置：是否记录并在时间窗口内提示日常关心事项 |
| `native_reminder_enabled` | `true` | 高级设置：是否由本插件到点发送待办提醒 |
| `use_chinese_calendar` | `true` | 高级设置：断网且无 JSON 缓存时使用本地 `chinese-calendar` 兜底 |

## 命令与工具

| 类别 | 名称 / 格式 | 说明 |
|---|---|---|
| 对话工具 | `query_calendar(range="today")` | 查询 `today`、`week` 或指定日期的历法、节气、调休和待办 |
| 对话工具 | `manage_todos(action, owner_type, text, start, end, ...)` | 新增、列出或完成 `self` / `mutual` / `other` / `care_note` 事项 |
| 管理命令 | `/待办 + <self\|mutual\|other> <开始> <结束> <内容>` | 快捷录入一条带起止时间的待办（`self`/`mutual` 需管理员） |
| WebUI 控件 | `同步年度调休表` / `刷新今日历法` / `清理已完成或过期待办` | 查看今日日历状态，手动拉取调休数据或清理旧待办 |

<details>
<summary>开发与自检</summary>

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r .github/requirements-ci.txt
.venv/bin/python scripts/check.py
```

</details>
