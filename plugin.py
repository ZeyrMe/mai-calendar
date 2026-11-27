from __future__ import annotations

import asyncio
import builtins
import contextlib
import hashlib
import json
import uuid
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from maibot_sdk import API, Command, HookHandler, MaiBotPlugin, Tool
from maibot_sdk.config_widgets import ConfigWidget, ConfigWidgetState
from maibot_sdk.types import HookOrder, ToolParameterInfo

from .config_models import Config, Todo
from .dates import civil_context, occurrence, parse_time
from .ecosystem import ChatIdentity, EcosystemMixin
from .holidays import HolidayStore
from .runtime import (
    StateFile,
    inject,
    optional_api,
    render,
    result,
    send_receipt,
    send_succeeded,
    service_send,
)


def todo_item(row):
    return {**row, "ownership": row["owner_type"]}


def parse(value):
    return datetime.fromisoformat(value)


class Plugin(EcosystemMixin, MaiBotPlugin):
    config_model = Config
    config_widgets = EcosystemMixin.config_widgets + [
        ConfigWidget(id="refresh_calendar", kind="action", label="刷新今日历法"),
        ConfigWidget(id="sync_holidays", kind="action", label="同步年度调休表"),
        ConfigWidget(
            id="cleanup_todos",
            kind="action",
            label="清理已完成或过期待办",
            confirmation="清理已结束的事项，继续？",
        ),
    ]

    def __init__(self):
        super().__init__()
        self.store = None
        self.holidays = None
        self.zone = ZoneInfo("Asia/Shanghai")
        self.task = None
        self.calendar_status = {}

    @HookHandler("chat.receive.after_process")
    async def remember_scope(self, message=None, **kwargs):
        await self.in_scope(message, **kwargs)
        return {"action": "continue"}

    def console_text(self):
        counts = (
            {
                owner: sum(row["owner_type"] == owner and row["status"] == "open" for row in self.todo_rows())
                for owner in ("self", "mutual", "other", "care_note")
            }
            if self.store
            else {}
        )
        holiday_summary = self.holidays.summary_text(self.now().year) if self.holidays else "暂未初始化"
        status = self.calendar_status or {}
        if status.get("date"):
            work_text = "工作日" if status.get("is_workday") else "休息日"
            if not status.get("valid", True):
                work_text += "（未查到该年份官方调休表，按周末推算）"
            term_text = f" · 节气：{status['solar_term']}" if status.get("solar_term") else ""
            today_line = f"{status['date']}（农历 {status.get('lunar') or '未知'}{term_text} · {work_text}）"
        else:
            today_line = "等待后台刷新"
        todo_line = (
            f"自己 {counts.get('self', 0)} 条 · 双方约定 {counts.get('mutual', 0)} 条 · 帮记提醒 {counts.get('other', 0)} 条 · 日常关心 {counts.get('care_note', 0)} 条"
            if counts
            else "暂无未完成待办"
        )
        return (
            f"今日历法：{today_line}\n"
            f"年度调休缓存：{holiday_summary} · 重要日子/倒计时：{len(self.config.events) + len(self.config.dates)} 个\n"
            f"当前待办：{todo_line}"
        )

    async def on_load(self):
        self.zone = ZoneInfo(self.config.timezone)
        self.store = StateFile(self.ctx.paths.data_dir / "calendar.json", initial_state())
        self.holidays = HolidayStore(self.ctx.paths.data_dir / "holidays")
        today = self.now().date()
        self.holidays.load_from_disk([today.year, today.year + 1])
        self.seed_todos()
        self.refresh_status()
        self.task = asyncio.create_task(self.loop(), name="zeyr-mai-calendar")

    async def on_unload(self):
        if self.task:
            self.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.task

    async def sync_holidays_if_needed(self, *, force=False):
        if not self.holidays or not self.config.holiday_sync.enabled:
            return
        now = self.now()
        targets = [now.year]
        if force or now.month in (11, 12):
            targets.append(now.year + 1)
        for year in targets:
            if force or self.holidays.should_refresh(
                year, now, self.config.holiday_sync.refresh_interval_days
            ):
                await self.holidays.sync_year(
                    year,
                    self.config.holiday_sync.feed_urls,
                    timeout_seconds=self.config.holiday_sync.timeout_seconds,
                    now=now,
                )

    async def loop(self):
        await asyncio.sleep(3)
        while True:
            try:
                await self.sync_holidays_if_needed()
                self.refresh_status()
                await self.remind_due()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.ctx.logger.exception("待办提醒失败，下轮重试")
            await asyncio.sleep(self.config.tick_seconds)

    async def remind_due(self):
        if not self.config.enabled or not self.config.native_reminder_enabled:
            return
        sent_keys = self.store.data.setdefault("reminded", {})
        for row in self.todo_rows():
            key = f"{row['id']}:{row['revision']}"
            if row["owner_type"] == "care_note":
                continue
            if row["status"] != "open" or not row["start"] or not row["stream_id"] or key in sent_keys:
                continue
            if parse(row["start"]) > self.now():
                continue
            if not await self.target_in_scope(
                row["platform"] or "qq", row.get("group_id", ""), row["creator_id"], row["stream_id"]
            ):
                continue
            target = row["target_user_id"] if row["owner_type"] == "other" else ""
            text = render(self.config.reminder_template, target=target, text=row["text"])
            response = await service_send(
                self.ctx,
                text,
                row["stream_id"],
                return_details=True,
            )
            if send_succeeded(response):
                sent_keys[key] = send_receipt(response, key)
                self.store.save()

    def refresh_status(self):
        if self.store:
            context = self.day_context()
            self.calendar_status = {
                key: context[key] for key in ("date", "lunar", "solar_term", "is_workday", "valid")
            }

    async def get_config_widget_state(self):
        return {
            **await super().get_config_widget_state(),
            "refresh_calendar": ConfigWidgetState(),
            "sync_holidays": ConfigWidgetState(
                disabled=not bool(self.holidays and self.config.holiday_sync.enabled),
                text=self.holidays.summary_text(self.now().year) if self.holidays else "",
            ),
            "cleanup_todos": ConfigWidgetState(disabled=self.store is None),
        }

    async def on_config_widget_action(self, action_id):
        if action_id == "refresh_calendar":
            self.refresh_status()
            return
        if action_id == "sync_holidays" and self.holidays:
            await self.sync_holidays_if_needed(force=True)
            self.refresh_status()
            return
        if action_id == "cleanup_todos" and self.store:
            now = self.now()
            self.store.data["todos"] = [
                row
                for row in self.store.data["todos"]
                if row["status"] == "open" and not (row.get("end") and parse(row["end"]) < now)
            ]
            self.store.save()
            self.refresh_status()
            return
        await super().on_config_widget_action(action_id)

    async def on_config_update(self, scope, config_data, version):
        self.zone = ZoneInfo(self.config.timezone)
        if self.store:
            self.seed_todos()

    def seed_todos(self):
        configured = {row.get("id"): row for row in self.store.data["todos"] if row.get("id")}
        for item in self.config.todos:
            row = item.model_dump(mode="json")
            row["id"] = (
                row["id"]
                or "config:" + hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()[:24]
            )
            configured.setdefault(row["id"], row)
        self.store.data["todos"] = list(configured.values())
        self.store.save()

    def now(self):
        return datetime.now(self.zone)

    def logical_date(self, now=None):
        value = (now or self.now()).astimezone(self.zone)
        return (value - timedelta(hours=self.config.day_rollover_hour)).date()

    def is_workday(self, day):
        key = day.isoformat()
        for override in self.config.workday_overrides:
            if override.date == key:
                return override.is_workday
        if self.config.holiday_sync.enabled and self.holidays:
            synced = self.holidays.lookup(day)
            if synced is not None:
                return synced["is_workday"]
            if self.holidays.has_year(day.year):
                return day.weekday() < 5
        if self.config.use_chinese_calendar:
            try:
                from chinese_calendar import is_workday

                return bool(is_workday(day))
            except (ImportError, ValueError, NotImplementedError):
                pass
        for entry in self.config.events + self.config.dates:
            if entry.date == key and entry.kind in ("holiday", "workday"):
                return entry.kind == "workday"
        return day.weekday() < 5

    def event_rows(self, day, horizon=0):
        rows = []
        for entry in self.config.events + self.config.dates:
            if not entry.date:
                continue
            target = occurrence(entry, day)
            if target is None:
                continue
            if day <= target <= day + timedelta(days=max(horizon, entry.reminder_days)):
                rows.append(
                    {
                        "date": target.isoformat(),
                        "title": entry.title,
                        "kind": entry.kind,
                        "note": entry.note,
                        "days": (target - day).days,
                        "reminder_days": max(horizon, entry.reminder_days),
                    }
                )
        if self.config.holiday_sync.enabled and self.holidays:
            synced = self.holidays.lookup(day)
            if (
                synced
                and synced["title"]
                and not any(row["title"] == synced["title"] and row["days"] == 0 for row in rows)
            ):
                rows.append(
                    {
                        "date": day.isoformat(),
                        "title": synced["title"],
                        "kind": "holiday" if synced["is_off_day"] else "workday",
                        "note": "",
                        "days": 0,
                        "reminder_days": 0,
                    }
                )
        if self.config.use_chinese_calendar:
            try:
                from chinese_calendar import get_holiday_detail

                holiday, name = get_holiday_detail(day)
                if holiday and name and not any(row["title"] == name and row["days"] == 0 for row in rows):
                    rows.append(
                        {
                            "date": day.isoformat(),
                            "title": name,
                            "kind": "holiday",
                            "note": "",
                            "days": 0,
                            "reminder_days": 0,
                        }
                    )
            except (ImportError, ValueError, NotImplementedError):
                pass
        return rows

    def todo_rows(self):
        return [Todo.model_validate(row).model_dump(mode="json") for row in self.store.data["todos"]]

    def todo_for_day(self, day, include_other=True):
        rows = []
        for todo in self.todo_rows():
            if todo["status"] != "open" or not todo["start"]:
                continue
            if not include_other and todo["owner_type"] not in ("self", "mutual"):
                continue
            window_start = datetime.combine(day, datetime.min.time(), self.zone) + timedelta(
                hours=self.config.day_rollover_hour
            )
            window_end = window_start + timedelta(days=1)
            if parse(todo["start"]) < window_end and parse(todo["end"]) > window_start:
                rows.append(todo)
        return rows

    def day_context(self, day=None):
        day = day or self.now().date()
        events = self.event_rows(day, self.config.reminder_days)
        reminders = [
            row
            for row in self.todo_rows()
            if row["status"] == "open"
            and row["owner_type"] != "care_note"
            and row["start"]
            and 0 <= (parse(row["start"]).astimezone(self.zone).date() - day).days <= row["remind_days"]
        ]
        civil = civil_context(day, self.config)
        for title in civil["names"]:
            if not any(row["title"] == title and row["days"] == 0 for row in events):
                events.append(
                    {
                        "date": day.isoformat(),
                        "title": title,
                        "kind": "holiday",
                        "days": 0,
                        "reminder_days": 0,
                        "note": "",
                    }
                )
        valid = True
        has_override = any(row.date == day.isoformat() for row in self.config.workday_overrides)
        has_synced = bool(
            self.config.holiday_sync.enabled and self.holidays and self.holidays.has_year(day.year)
        )
        if not has_override and not has_synced and self.config.use_chinese_calendar:
            try:
                from chinese_calendar import is_workday

                is_workday(day)
            except (ValueError, ImportError, NotImplementedError):
                valid = False
        return {
            "lunar": civil["lunar"],
            "solar_term": civil["solar_term"],
            "date": day.isoformat(),
            "is_workday": self.is_workday(day),
            "events_today": [row for row in events if row["days"] == 0],
            "upcoming_events": [row for row in events if 0 < row["days"] <= row["reminder_days"]],
            "todos_today": self.todo_for_day(day),
            "todo_reminders": reminders,
            "valid": valid,
            "workday_source": "official_or_override" if valid else "weekday_fallback_unverified",
        }

    def hint(self, stream_id=""):
        if not self.config.enabled:
            return ""
        context = self.day_context()
        pieces = [row["title"] for row in context["events_today"]]
        pieces.extend(f"{row['title']}还有{row['days']}天" for row in context["upcoming_events"])
        pieces.extend(
            render(self.config.todo_template, text=row["text"])
            for row in context["todo_reminders"]
            if not row["stream_id"] or row["stream_id"] == stream_id
        )
        if self.config.care_note_enabled:
            pieces.extend(
                render(self.config.care_template, text=row["text"])
                for row in self.todo_rows()
                if row["owner_type"] == "care_note"
                and row["status"] == "open"
                and row["stream_id"] == stream_id
                and row["start"]
                and abs((parse(row["start"]) - self.now()).total_seconds())
                <= self.config.care_hint_window_hours * 3600
            )
        if not pieces:
            return ""
        return render(self.config.hint_template, date=context["date"], items="；".join(pieces))[
            : self.config.hint_chars
        ]

    def manage(self, action, owner_type="self", text="", start="", end="", todo_id="", **kwargs):
        if not self.config.enabled:
            raise ValueError("插件已禁用")
        if action == "list":
            return {"items": self.todo_rows()}
        row = next((item for item in self.store.data["todos"] if item["id"] == todo_id), None)
        if action in ("complete", "cancel"):
            if row is None:
                raise ValueError("待办不存在")
            row["status"] = "done" if action == "complete" else "cancelled"
            row["revision"] = row.get("revision", 1) + 1
            self.store.save()
            return row
        if action != "add":
            raise ValueError("action 应为 list / add / complete / cancel")
        if not text.strip():
            raise ValueError("待办内容不能为空")
        if owner_type == "care_note" and not self.config.care_note_enabled:
            raise ValueError("随口惦记已关闭")
        start = parse_time(start, self.now())
        end = (
            parse_time(end, self.now())
            if end
            else (parse(start) + timedelta(minutes=self.config.default_todo_minutes)).isoformat()
            if start
            else ""
        )
        if owner_type in ("self", "mutual") and start and end:
            for existing in self.todo_rows():
                if (
                    existing["status"] == "open"
                    and existing["owner_type"] in ("self", "mutual")
                    and (existing["owner_type"] == "mutual" or existing["flexibility"] == "locked")
                    and existing["start"]
                    and parse(start) < parse(existing["end"])
                    and parse(existing["start"]) < parse(end)
                ):
                    raise ValueError("与已确认的刚性待办冲突")
        row = Todo(
            id=todo_id or f"todo:{uuid.uuid4().hex}",
            owner_type=owner_type,
            text=text,
            start=start,
            end=end,
            flexibility=kwargs.get("flexibility", "soft"),
            remind_days=int(kwargs.get("remind_days", 0)),
            stream_id=kwargs.get("stream_id", ""),
            creator_id=kwargs.get("creator_id", ""),
            group_id=kwargs.get("group_id", ""),
            platform=kwargs.get("platform", ""),
            target_user_id=kwargs.get("target_user_id", ""),
        ).model_dump(mode="json")
        if any(item["id"] == row["id"] for item in self.store.data["todos"]):
            raise ValueError("待办标识已存在")
        self.store.data["todos"].append(row)
        self.store.save()
        return row

    @Tool(
        "query_calendar",
        description="查询日期、节假日、倒计时与待办事项。",
        parameters=[
            ToolParameterInfo(
                name="range", description="today / week / YYYY-MM-DD", required=False, default="today"
            )
        ],
        visibility="visible",
    )
    async def query_calendar(self, range="today", **kwargs):
        if not await self.in_scope(**kwargs):
            return result(error="当前会话不在插件生效范围")
        day = self.now().date()
        if range == "today":
            return result(self.day_context(day))
        if range == "week":
            return result({"days": [self.day_context(day + timedelta(days=i)) for i in builtins.range(7)]})
        try:
            return result(self.day_context(date.fromisoformat(range)))
        except ValueError:
            return result(error="range 应为 today / week / YYYY-MM-DD")

    @Tool(
        "manage_todos",
        description="查看、添加或修改待办事项、日程约定与日常关心。",
        parameters={
            "action": {"type": "string", "enum": ["list", "add", "complete", "cancel"]},
            "owner_type": {
                "type": "string",
                "enum": ["self", "mutual", "other", "care_note"],
                "default": "self",
            },
            "text": {"type": "string", "default": ""},
            "start": {"type": "string", "default": ""},
            "end": {"type": "string", "default": ""},
            "todo_id": {"type": "string", "default": ""},
            "target_user_id": {"type": "string", "default": ""},
            "flexibility": {"type": "string", "enum": ["locked", "soft", "open"], "default": "soft"},
        },
        visibility="visible",
    )
    async def manage_todo(self, action, owner_type="self", text="", start="", end="", todo_id="", **kwargs):
        if not await self.in_scope(**kwargs):
            return result(error="当前会话不在插件生效范围")
        try:
            message = kwargs.get("message") or {}
            chat = ChatIdentity.from_message(message or kwargs, kwargs.get("stream_id") or "")
            user_id, stream = chat.user_id, chat.stream_id
            if not stream or not user_id:
                return result(error="需要宿主提供当前会话和发送者")
            if action == "list":
                return result({"items": [row for row in self.todo_rows() if row["stream_id"] == stream]})
            existing = next((row for row in self.todo_rows() if row["id"] == todo_id), None)
            if existing and existing["stream_id"] != stream:
                return result(error="待办不属于当前会话")
            if not await self.can_manage(action, owner_type, existing, chat.platform, user_id):
                return result(error="需要管理员或待办创建者权限")
            if action == "add" and owner_type in ("self", "mutual") and start:
                availability = await optional_api(
                    self.ctx,
                    "zeyr.mai-day.check_availability",
                    start=parse_time(start, self.now()),
                    end=parse_time(end, self.now()) if end else "",
                )
                if availability and availability.get("availability") == "conflict_locked":
                    return result(error="与刚性日程冲突，请先商量其他时段")
            return result(
                self.manage(
                    action,
                    owner_type,
                    text,
                    start,
                    end,
                    todo_id,
                    stream_id=stream,
                    creator_id=user_id,
                    group_id=chat.group_id,
                    platform=chat.platform,
                    target_user_id=kwargs.get("target_user_id", user_id),
                    flexibility=kwargs.get("flexibility", "soft"),
                )
            )
        except (TypeError, ValueError) as exc:
            return result(error=str(exc))

    @API("get_day_context", public=True, version="1")
    async def api_day_context(self, date="", **kwargs):
        try:
            day = __import__("datetime").date.fromisoformat(date) if date else self.now().date()
        except ValueError:
            return result(error="date 应为 YYYY-MM-DD")
        return result(self.day_context(day))

    @API("get_schedulable_todos", public=True, version="1")
    async def api_schedulable(self, date="", **kwargs):
        try:
            day = __import__("datetime").date.fromisoformat(date) if date else self.logical_date()
        except ValueError:
            return result(error="date 应为 YYYY-MM-DD")
        return result(
            {
                "date": day.isoformat(),
                "items": [todo_item(row) for row in self.todo_for_day(day, include_other=False)]
                if self.config.enabled
                else [],
            }
        )

    @API("manage_todo", public=True, version="1")
    async def api_manage(
        self,
        action,
        owner_type="self",
        text="",
        start="",
        end="",
        todo_id="",
        stream_id="",
        creator_id="",
        platform="",
        target_user_id="",
        **kwargs,
    ):
        try:
            if not stream_id or not creator_id:
                return result(error="manage_todo 需要 stream_id 与 creator_id")
            if not await self.in_scope(stream_id=stream_id):
                return result(error="当前会话不在插件生效范围")
            if action == "list":
                return result({"items": [row for row in self.todo_rows() if row["stream_id"] == stream_id]})
            existing = next((row for row in self.todo_rows() if row["id"] == todo_id), None)
            if existing and existing["stream_id"] != stream_id:
                return result(error="待办不属于当前会话")
            if not await self.can_manage(action, owner_type, existing, platform, creator_id):
                return result(error="需要管理员或待办创建者权限")
            if action == "add" and owner_type in ("self", "mutual") and start:
                availability = await optional_api(
                    self.ctx,
                    "zeyr.mai-day.check_availability",
                    start=parse_time(start, self.now()),
                    end=parse_time(end, self.now()) if end else "",
                )
                if availability and availability.get("availability") == "conflict_locked":
                    return result(error="与刚性日程冲突，请先商量其他时段")
            return result(
                self.manage(
                    action,
                    owner_type,
                    text,
                    start,
                    end,
                    todo_id,
                    stream_id=stream_id,
                    creator_id=creator_id,
                    group_id=kwargs.get("group_id", ""),
                    platform=platform,
                    target_user_id=target_user_id,
                    flexibility=kwargs.get("flexibility", "soft"),
                )
            )
        except (TypeError, ValueError) as exc:
            return result(error=str(exc))

    async def is_admin(self, platform, user_id):
        if not self.config.enabled or not user_id:
            return False
        if any(row.platform == platform and row.user_id == user_id for row in self.config.admins):
            return True
        external = await optional_api(
            self.ctx, "zeyr.mai-circle.is_admin", platform=platform, user_id=user_id
        )
        return bool(external and external.get("value"))

    async def can_manage(self, action, owner_type, existing, platform, user_id):
        if await self.is_admin(platform, user_id):
            return True
        if action == "add":
            return owner_type in ("self", "mutual", "other", "care_note")
        return bool(existing and existing["creator_id"] == user_id)

    @HookHandler("maisaka.planner.before_request", order=HookOrder.NORMAL)
    async def planner(self, **kwargs):
        if not await self.in_scope(**kwargs):
            return {"action": "continue"}
        return inject(
            kwargs,
            "mai-calendar",
            self.hint(str(kwargs.get("session_id") or kwargs.get("stream_id") or "")),
            self.config.hint_chars,
        )

    @HookHandler("maisaka.replyer.before_request", order=HookOrder.NORMAL)
    async def replyer(self, **kwargs):
        if not await self.in_scope(**kwargs):
            return {"action": "continue"}
        return inject(
            kwargs,
            "mai-calendar",
            self.hint(str(kwargs.get("session_id") or kwargs.get("stream_id") or "")),
            self.config.hint_chars,
        )

    @Command(
        "todo_add",
        pattern=r"^/待办\s*\+\s*(?P<owner>self|mutual|other)\s+(?P<start>\S+)\s+(?P<end>\S+)\s+(?P<text>.+)$",
    )
    async def todo_add(self, matched_groups=None, message=None, stream_id="", **kwargs):
        if not await self.in_scope(message, stream_id=stream_id):
            return False, "当前会话不在插件生效范围", 1
        groups = matched_groups or {}
        info = (message or {}).get("message_info") or {}
        user = info.get("user_info") or {}
        platform = str((message or {}).get("platform") or user.get("platform") or "")
        user_id = str(user.get("user_id") or "")
        if not stream_id or not user_id:
            return False, "需要当前会话和发送者", 1
        try:
            if groups.get("owner") != "other" and not await self.is_admin(platform, user_id):
                return False, "需要管理员权限", 1
            row = self.manage(
                "add",
                groups["owner"],
                groups["text"],
                groups["start"],
                groups["end"],
                stream_id=stream_id,
                creator_id=user_id,
                group_id=str((info.get("group_info") or {}).get("group_id") or ""),
                platform=platform,
                target_user_id=str(
                    (((message or {}).get("message_info") or {}).get("user_info") or {}).get("user_id") or ""
                ),
            )
            text = f"待办已记录：{row['text']}"
            await service_send(
                self.ctx,
                text,
                stream_id,
            )
            return True, text, 2
        except (KeyError, ValueError) as exc:
            return False, str(exc), 1


def initial_state():
    return {"schema_version": 1, "todos": [], "reminded": {}}


def create_plugin():
    return Plugin()
