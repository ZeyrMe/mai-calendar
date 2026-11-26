<div align="center">

# 今天是什么日子 · `zeyr.mai-calendar`

**每年国务院发新调休不用改代码自动缓存，记生日绝不乱猜阴历阳历，还能帮群友设提醒、默默记下对方随口一提的事**

![Version](https://img.shields.io/badge/version-0.2.0-brightgreen)
![MaiBot](https://img.shields.io/badge/MaiBot-1.4.8%2B-2f81f7)
![SDK](https://img.shields.io/badge/SDK-2.23.0-0e8a16)
![Standalone](https://img.shields.io/badge/独立运行-支持-blue)

[为什么用它](#为什么用它) · [3 步快速开始](#3-步快速开始) · [配置项说明](#常用配置项说明) · [工具与控制台](#工具命令与控制台) · [FAQ](#常见疑问)

</div>

---

## 为什么用它

| 常见问题 | 常见局限 | **今天是什么日子（`zeyr.mai-calendar`）** |
|---|---|---|
| 年一跨，调休补班全过时 | 依赖 PyPI 静态包，每年 11 月出新调休必须手动升级容器里的包 | **四级优先级 + 静态年度 JSON 静默缓存**（缺当年或年底自动拉取 `holiday-cn` 多镜像并持久存盘） |
| 阴历阳历瞎换算 | 自动推导把公历生日硬转成农历或把旧日期写乱 | 默认全按公历；仅你显式选了 `calendar = "lunar"` 才换算，内置节气与传统农历节日 |
| 谁的事都塞进生活日程 | 群友喊“提醒我明天交作业”，结果 Bot 自己日程表多出个任务 | 严格分四类：**只有 `self` 和 `mutual` 会进入 `mai-day` 日程**，`other` 只提醒对方 |
| 对方随口提一嘴的事 | 发冰冷闹钟提醒显得很奇怪，不记又显得没上心 | 新增 **`care_note` 随口惦记**：不报时，只在到时间窗对方说话时轻轻提醒 Bot 顺嘴关心一句 |

---

## 3 步快速开始

### WebUI 上手（推荐）
1. 将 `mai-calendar/` 放入宿主 `plugins/` 目录并重启，打开 **今天是什么日子** 配置页。
2. 核对 **本地时区**（默认 `Asia/Shanghai`）；在 **重要日子与生日** 添上生日或倒计时（农历生日把历法下拉选成 `lunar` 并勾上重复）。
3. 打开 **运行状态与生效范围** 面板确认今日公农历与调休缓存状态，也可以随时点击 **同步年度调休表** 立刻拉取最新年份。

<details>
<summary>手改 config.toml 示例（附完整注释）</summary>

```toml
enabled = true
timezone = "Asia/Shanghai"
enable_solar_terms = true                            # 感知二十四节气（如冬至、清明）
enable_traditional_lunar_holidays = true             # 感知春节、元宵、端午、中秋、除夕等

[[dates]]
title = "老朋友生日"
date = "2000-08-15"                                  # 写农历八月十五
calendar = "lunar"                                   # 必须显式指定 lunar 才会按农历换算
yearly = true
kind = "birthday"
reminder_days = 3                                    # 提前 3 天开始在对话里提起

[[workday_overrides]]
date = "2026-10-10"                                  # 最高优先级：手动强制覆盖这一天是否上班/上课
is_workday = true
```

</details>

---

## 常用配置项说明

| 配置项 | 默认值 | 怎么填与效果说明 |
|---|---|---|
| `dates` | `[]` | 重要日子与倒计时；`calendar` 默认 `solar`（公历），阴历生日务必选 `lunar` |
| `holiday_sync` | 自动启用 | 静态年度调休 JSON 镜像同步配置；支持配置私有/内网外代理镜像（遵循公网安全检查） |
| `workday_overrides` | `[]` | 优先级最高的手动调休覆盖，压过远程 JSON 与本地库 |
| `care_note_enabled` | `true` | 允许模型在聊天中记录 `care_note` 随口惦记；到前后 12 小时内自然轻提示 |
| `native_reminder_enabled` | `true` | 是否由本插件发到期提醒；如习惯全交由 MaiBot 1.4.4+ 原生唤醒可关掉此项 |
| `use_chinese_calendar` | `true` | 断网且无本地 JSON 缓存时的内置离线兜底库 |

---

## 工具、命令与控制台

### 对话工具（`@Tool`）
| 工具名 | 作用 |
|---|---|
| `query_calendar(range="today")` | 查询 `today` / `week` / 指定 `YYYY-MM-DD` 的公农历、节气、调休与待办 |
| `manage_todos(action, owner_type, text, start, end, ...)` | 自然语言记录或管理 `self / mutual / other / care_note`；时间支持 `明天 20:00`、`12-01 09:30`、`周五晚上8点`；记 `self / mutual` 会自动先检查 `mai-day` 档期是否冲突 |

### 强制指令与控制台
- **快捷强制命令**：`/待办 + <self|mutual|other> <开始> <结束> <内容>`（`other` 人人可用，`self/mutual` 需管理员）。
- **WebUI 控制台**：`运行状态与生效范围`（今日历法 + 调休缓存年份 + 账本统计）、`同步年度调休表`、`刷新今日历法`、`清理已完成或过期待办`。

---

## 生态联动与常见疑问

- **联动关系**：与 `mai-day` 共存时为其提供放假/补班判断及 `self/mutual` 日程，并在睡着期间通过 30 秒精确授权正常发出到期提醒（绝不被误杀、绝不破坏观察群禁言）。
- **Q：所有群共享一份待办吗？**
  不共享。待办与 `care_note` 严格绑定原会话 `stream_id` 与群/人锚点，严禁跨群查询或修改。

<details>
<summary>开发、门禁与安全审计</summary>

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r .github/requirements-ci.txt
.venv/bin/python scripts/check.py
```

- 已同步锁定 `chinese-calendar`、`lunar-python` 与 `httpx` 到 `.github/requirements-ci.txt`，包含 39 项测试。

</details>
