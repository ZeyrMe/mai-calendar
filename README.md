# 今天是什么日子 · `zeyr.mai-calendar`

> 四级权威中国法定调休/农历/节气历法、不瞎猜阴历阳历的重要日子倒计时，以及覆盖本人、约定、他人与“随口默默惦记”的自然语言待办本。

![Version](https://img.shields.io/badge/version-0.2.0-green)
![MaiBot](https://img.shields.io/badge/MaiBot-1.4.8%2B-blue)
![SDK](https://img.shields.io/badge/SDK-2.23.0-teal)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

## 核心特性

- **四级历法权威 + 年度调休自动同步（告别每年手动升级库）**：
  1. 用户显式手动覆盖 `workday_overrides`（最高权威）；
  2. 本地持久化的静态年度调休 JSON 缓存（默认内置多镜像 `NateScarlet/holiday-cn` 模板，缺当年表或每年 11–12 月自动静默同步次年国务院调休并标明“放假 / 调休补班”）；
  3. 本地 `chinese_calendar` 库离线兜底；
  4. 周一至周五常规兜底。
- **严格区分阳历与农历，绝不玄学猜测**：内置 `lunar-python` 自动计算二十四节气、除夕与传统农历节日；用户登记生日或纪念日时，必须显式选择 `solar` 或 `lunar`（支持闰月）才会按农历每年自动换算公历日期。
- **三账分离 + 自然时间解析**：
  - 历法与节气（只读背景）/ 重要日子倒计时 / 一次性待办与惦记，三张表严格隔离；
  - 对话时间支持直接传入 `明天 20:00`、`12-01 09:30`、`周五晚上8点` 或标准 ISO 时间。
- **自然语言四类归属 + “默默惦记 (`care_note`)”**：
  - `self`（自己要做的事）与 `mutual`（双方约定）：可自主协商记入并同步给 `mai-day` 排进生活日程；
  - `other`（帮朋友记事）：不进自己的日程，到点提醒对方；
  - `care_note`（随口一提默默记着）：相手随口聊到“后天体检/明晚答辩”时静默记下，**绝不发冰冷定时闹钟**，而是在对应时间窗轻提示让 Bot 自然关心一句。
- **与 MaiBot 1.4.8+ 原生提醒和平共存**：提供 `native_reminder_enabled` 一键开关，自由选择由本插件到点提醒，还是专心当宿主的日历与约定数据源。

---

## 安装与快速配置

将 `mai-calendar/` 放入宿主 `plugins/` 目录并重启 MaiBot（宿主会自动安装 `chinese-calendar`、`lunar-python` 与 `httpx`）。

`config.toml` 示例：

```toml
enabled = true
timezone = "Asia/Shanghai"

[[dates]]
title = "老朋友生日"
date = "2000-08-15"
calendar = "lunar"       # solar | lunar，农历必须显式声明
yearly = true
kind = "birthday"
reminder_days = 3

[[workday_overrides]]
date = "2026-10-10"
is_workday = true
```

---

## 工具、命令、接口与 WebUI 控制台

### 对话工具（`@Tool`）
| 工具名 | 主要参数 | 作用 |
|---|---|---|
| `query_calendar` | `range="today"` | 查询 `today` / `week` / 指定 `YYYY-MM-DD` 的公农历、节气、调休、倒计时与待办 |
| `manage_todos` | `action`, `owner_type`, `text`, `start`, `end`, ... | 自然语言新增、列出、完成或取消 `self / mutual / other / care_note` 事项；`self / mutual` 自动检查生活档期冲突 |

### 强制快捷命令
| 命令格式 | 鉴权与效果 |
|---|---|
| `/待办 + <self\|mutual\|other> <开始时间> <结束时间> <内容>` | 帮别人记 `other` 直接放行；强制录入 `self / mutual` 需管理员权限，适合不走心理协商的硬性录入 |

### 对外联动接口（`@API(..., version="1")`）
- `get_day_context(date="")` / `get_schedulable_todos(date="")`（仅向外返回 `self / mutual`）/ `manage_todo(...)`

### WebUI 运行时控制台（`config_widgets`）
| 控件 | 类型 | 说明 |
|---|---|---|
| `运行状态与生效范围` | 实时状态 | 展示今日公农历、节气、工作日状态、年度调休表缓存年份及四类待办统计 |
| `同步年度调休表` | 一键按钮 | 立即从配置镜像同步当年与次年调休 JSON 并刷新缓存 |
| `刷新今日历法` | 一键按钮 | 立即重算今日历法与提示状态 |
| `清理已完成或过期待办` | 二次确认按钮 | 清除已结束或过期的待办记录 |

---

## 生态联动与注意事项

- **与 `mai-day` 联动**：若同装生活插件，`mutual` 会自动作为 `locked` 约定写进当天日程，`self` 依刚度排入；新增 `self / mutual` 前先调 `mai-day.check_availability` 避免与已有刚性日程撞车；到点发送与命令回执走 30 秒精确服务发送授权，绝不被睡眠门控误杀，同时严格尊重观察群禁言。
- **跨会话隔离**：待办与 `care_note` 绑定原会话 `stream_id` 与群/用户锚点，严禁跨群修改或泄漏提示。

<details>
<summary>开发、门禁与安全审计（独立仓库维护）</summary>

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r .github/requirements-ci.txt
.venv/bin/python scripts/check.py
```

- 依赖同步包含 `chinese-calendar`、`lunar-python` 与 `httpx`，并已锁定 `.github/requirements-ci.txt` 哈希校验文件。

</details>
