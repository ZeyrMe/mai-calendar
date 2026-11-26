from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from maibot_sdk import API, Command, HookHandler, MaiBotPlugin, Tool
from maibot_sdk.types import HookOrder, ToolParameterInfo

from .config_models import Config, Todo
from .runtime import StateFile, inject, result


def parse(value):
    return datetime.fromisoformat(value)


class Plugin(MaiBotPlugin):
    config_model = Config

    def __init__(self):
        super().__init__()
        self.store = None
        self.zone = ZoneInfo("Asia/Shanghai")

    async def on_load(self):
        self.zone = ZoneInfo(self.config.timezone)
        self.store = StateFile(self.ctx.paths.data_dir / "calendar.json", initial_state())
        self.seed_todos()

    async def on_unload(self):
        pass

    async def on_config_update(self, scope, config_data, version):
        self.zone = ZoneInfo(self.config.timezone)
        if self.store:
            self.seed_todos()

    def seed_todos(self):
        configured = {row.get("id"): row for row in self.store.data["todos"] if row.get("id")}
        for item in self.config.todos:
            row = item.model_dump(mode="json")
            row["id"] = row["id"] or f"config:{uuid.uuid4().hex}"
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
        if key in self.config.workday_overrides:
            return self.config.workday_overrides[key]
        if self.config.use_chinese_calendar:
            try:
                from chinese_calendar import is_workday

                return bool(is_workday(day))
            except (ImportError, ValueError):
                pass
        return day.weekday() < 5

    def event_rows(self, day, horizon=0):
        rows = []
        for entry in self.config.events:
            if not entry.date:
                continue
            original = date.fromisoformat(entry.date)
            target = date(day.year, original.month, original.day) if entry.yearly else original
            if entry.yearly and target < day:
                target = date(day.year + 1, original.month, original.day)
            if day - timedelta(days=horizon) <= target <= day + timedelta(days=horizon):
                rows.append(
                    {
                        "date": target.isoformat(),
                        "title": entry.title,
                        "kind": entry.kind,
                        "note": entry.note,
                        "days": (target - day).days,
                    }
                )
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
            start = parse(todo["start"]).astimezone(self.zone).date()
            end = parse(todo["end"]).astimezone(self.zone).date()
            if start <= day <= end:
                rows.append(todo)
        return rows

    def day_context(self, day=None):
        day = day or self.logical_date()
        events = self.event_rows(day, self.config.reminder_days)
        reminders = [
            row
            for row in self.todo_rows()
            if row["status"] == "open"
            and row["start"]
            and 0 <= (parse(row["start"]).astimezone(self.zone).date() - day).days <= row["remind_days"]
        ]
        return {
            "date": day.isoformat(),
            "is_workday": self.is_workday(day),
            "events_today": [row for row in events if row["days"] == 0],
            "upcoming_events": [row for row in events if 0 < row["days"] <= self.config.reminder_days],
            "todos_today": self.todo_for_day(day),
            "todo_reminders": reminders,
            "valid": True,
        }

    def hint(self):
        if not self.config.enabled:
            return ""
        context = self.day_context()
        pieces = [row["title"] for row in context["events_today"]]
        pieces.extend(f"{row['title']}还有{row['days']}天" for row in context["upcoming_events"])
        pieces.extend(self.config.todo_template.format(text=row["text"]) for row in context["todo_reminders"])
        if not pieces:
            return ""
        return self.config.hint_template.format(date=context["date"], items="；".join(pieces))[
            : self.config.hint_chars
        ]

    def manage(self, action, owner_type="self", text="", start="", end="", todo_id="", **kwargs):
        if action == "list":
            return {"items": self.todo_rows()}
        row = next((item for item in self.store.data["todos"] if item["id"] == todo_id), None)
        if action in ("complete", "cancel"):
            if row is None:
                raise ValueError("待办不存在")
            row["status"] = "done" if action == "complete" else "cancelled"
            self.store.save()
            return row
        if action != "add":
            raise ValueError("action 应为 list / add / complete / cancel")
        if not text.strip():
            raise ValueError("待办内容不能为空")
        row = Todo(
            id=todo_id or f"todo:{uuid.uuid4().hex}",
            owner_type=owner_type,
            text=text,
            start=start,
            end=end,
            flexibility=kwargs.get("flexibility", "soft"),
            remind_days=int(kwargs.get("remind_days", 0)),
        ).model_dump(mode="json")
        self.store.data["todos"].append(row)
        self.store.save()
        return row

    @Tool(
        "query_calendar",
        description="查询节日、工作日状态、倒计时和待办。",
        parameters=[
            ToolParameterInfo(
                name="range", description="today / week / YYYY-MM-DD", required=False, default="today"
            )
        ],
        visibility="visible",
    )
    async def query_calendar(self, range="today", **kwargs):
        day = self.logical_date()
        if range == "today":
            return result(self.day_context(day))
        if range == "week":
            return result({"days": [self.day_context(day + timedelta(days=i)) for i in range(7)]})
        try:
            return result(self.day_context(date.fromisoformat(range)))
        except ValueError:
            return result(error="range 应为 today / week / YYYY-MM-DD")

    @Tool(
        "manage_todos",
        description="列出、添加、完成或取消待办；other 不进入生活日程。",
        parameters={
            "action": {"type": "string", "enum": ["list", "add", "complete", "cancel"]},
            "owner_type": {"type": "string", "enum": ["self", "mutual", "other"], "default": "self"},
            "text": {"type": "string", "default": ""},
            "start": {"type": "string", "default": ""},
            "end": {"type": "string", "default": ""},
            "todo_id": {"type": "string", "default": ""},
        },
        visibility="visible",
    )
    async def manage_todo(self, action, owner_type="self", text="", start="", end="", todo_id="", **kwargs):
        try:
            return result(self.manage(action, owner_type, text, start, end, todo_id, **kwargs))
        except (TypeError, ValueError) as exc:
            return result(error=str(exc))

    @API("get_day_context", public=True, version="1")
    async def api_day_context(self, date="", **kwargs):
        try:
            day = __import__("datetime").date.fromisoformat(date) if date else self.logical_date()
        except ValueError:
            return result(error="date 应为 YYYY-MM-DD")
        return result(self.day_context(day))

    @API("get_schedulable_todos", public=True, version="1")
    async def api_schedulable(self, date="", **kwargs):
        try:
            day = __import__("datetime").date.fromisoformat(date) if date else self.logical_date()
        except ValueError:
            return result(error="date 应为 YYYY-MM-DD")
        return result({"date": day.isoformat(), "items": self.todo_for_day(day, include_other=False)})

    @API("manage_todo", public=True, version="1")
    async def api_manage(self, action, owner_type="self", text="", start="", end="", todo_id="", **kwargs):
        try:
            return result(self.manage(action, owner_type, text, start, end, todo_id, **kwargs))
        except (TypeError, ValueError) as exc:
            return result(error=str(exc))

    @HookHandler("maisaka.planner.before_request", order=HookOrder.NORMAL)
    async def planner(self, **kwargs):
        return inject(kwargs, "mai-calendar", self.hint(), self.config.hint_chars)

    @HookHandler("maisaka.replyer.before_request", order=HookOrder.NORMAL)
    async def replyer(self, **kwargs):
        return inject(kwargs, "mai-calendar", self.hint(), self.config.hint_chars)

    @Command(
        "todo_add",
        pattern=r"^/待办\s*\+\s*(?P<owner>self|mutual|other)\s+(?P<start>\S+)\s+(?P<end>\S+)\s+(?P<text>.+)$",
    )
    async def todo_add(self, matched_groups=None, **kwargs):
        groups = matched_groups or {}
        try:
            row = self.manage("add", groups["owner"], groups["text"], groups["start"], groups["end"])
            return True, f"待办已记录：{row['text']}", 2
        except (KeyError, ValueError) as exc:
            return False, str(exc), 1


def initial_state():
    return {"schema_version": 1, "todos": []}


def create_plugin():
    return Plugin()
