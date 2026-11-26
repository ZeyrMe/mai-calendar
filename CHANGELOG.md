# 更新日志 · 今天是什么日子 (`zeyr.mai-calendar`)

本日志遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 规范。

## [0.2.0] - 2026-11-27

### 新增
- **年度调休静态 JSON 自动同步**：新增 `HolidaySyncConfig` 与 `holidays.py`，支持多镜像 `NateScarlet/holiday-cn` 静态文件静默拉取、公网 URL 校验、本地 `data_dir/holidays/{year}.json` 持久化缓存、11–12 月自动探查次年调休，以及 WebUI `同步年度调休表` 一键按钮。
- **农历、节气与自然时间**：集成 `lunar-python` 支持二十四节气、除夕、传统农历节日与显式 `lunar` 年复一年生日/纪念日；时间输入支持 `明天 20:00`、`12-01 09:30`、`周五晚上8点` 等自然写法。
- **随口惦记（`care_note`）与原生提醒开关**：支持记录不发冰冷闹钟、仅在对应时段温和提示关心的惦记事项；新增 `native_reminder_enabled` 方便与 MaiBot 原生唤醒配合；新增 `manage_todos` 档期冲突检查。
- **独立范围 `[scope]` 与 WebUI 控制台**：新增范围卡片、`同步年度调休表`、`刷新今日历法` 与 `清理已完成或过期待办` 按钮。

### 优化
- **WebUI 与文案优化**：`workday_overrides` 改为条目列表；隐藏旧版 `events` 与内部 ID/超时保护字段；补充短中文标题并润色惦记与到点提醒话术。

### 修复
- 修复跨年或缺失 `chinese_calendar` 年份时报错传播问题与后台循环启动时序。

## [0.1.0] - 2026-11-26

### 新增
- 初始开发版本：法定假日/调休基础判断、倒计时、`self/mutual/other` 待办提醒及 `/待办` 命令。
