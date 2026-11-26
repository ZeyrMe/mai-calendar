from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from maibot_sdk import Field, PluginConfigBase
from pydantic import field_validator, model_validator

from .ecosystem import ScopeConfig


class CalendarEntry(PluginConfigBase):
    date: str = Field(
        default="",
        description="日期 YYYY-MM-DD（农历也按这格式写月日）。",
        json_schema_extra={"label": "日期", "placeholder": "例如 2026-08-15"},
    )
    title: str = Field(
        default="",
        description="这个日子的名称，比如 老铁生日、返校日。",
        json_schema_extra={"label": "事件名称", "placeholder": "例如 老铁生日"},
    )
    kind: Literal["holiday", "workday", "birthday", "countdown", "custom"] = Field(
        default="custom",
        description="生日、倒计时、放假、调休或自定义纪念日。",
        json_schema_extra={"label": "类型"},
    )
    calendar: Literal["solar", "lunar"] = Field(
        default="solar",
        description="solar 阳历；lunar 农历（必须手动点选，程序不瞎猜）。",
        json_schema_extra={"label": "历法"},
    )
    leap_month: bool = Field(
        default=False,
        description="仅当农历碰上闰月生日时勾上。",
        json_schema_extra={"label": "农历闰月"},
    )
    yearly: bool = Field(
        default=False,
        description="每年同一天自动循环提醒（适合生日、纪念日）。",
        json_schema_extra={"label": "每年重复"},
    )
    reminder_days: int = Field(
        default=0,
        ge=0,
        le=365,
        description="提前几天开始在对话里隐约想起这件事。",
        json_schema_extra={"label": "提前提醒天数"},
    )
    note: str = Field(
        default="",
        description="补充备注信息。",
        json_schema_extra={"label": "补充备注"},
    )

    @model_validator(mode="after")
    def valid_date(self):
        if self.date:
            if self.calendar == "solar":
                date.fromisoformat(self.date)
            else:
                year, month, day = map(int, self.date.split("-"))
                if not (1 <= year <= 9999 and 1 <= month <= 12 and 1 <= day <= 30):
                    raise ValueError("农历日期应为 YYYY-MM-DD，月份 1–12、日 1–30")
        return self


class Todo(PluginConfigBase):
    id: str = Field(
        default="",
        description="待办编号，留空会自动生成。",
        json_schema_extra={"label": "待办编号", "hidden": True},
    )
    owner_type: Literal["self", "mutual", "other", "care_note"] = Field(
        default="self",
        description="self 自己的事；mutual 双方约好（会进生活日程）；other 帮别人记的提醒；care_note 随口惦记。",
        json_schema_extra={"label": "归属类型"},
    )
    text: str = Field(
        default="",
        description="具体要做什么或提醒什么。",
        json_schema_extra={"label": "事项内容", "placeholder": "例如 晚上一起开黑"},
    )
    start: str = Field(
        default="",
        description="开始时间（含时区 ISO 格式）。",
        json_schema_extra={"label": "开始时间", "placeholder": "2026-12-01T20:00:00+08:00"},
    )
    end: str = Field(
        default="",
        description="结束时间（含时区 ISO 格式）。",
        json_schema_extra={"label": "结束时间", "placeholder": "2026-12-01T22:00:00+08:00"},
    )
    flexibility: Literal["locked", "soft", "open"] = Field(
        default="soft",
        description="locked 不能让人挪；soft 可以商量。",
        json_schema_extra={"label": "时间刚度"},
    )
    remind_days: int = Field(
        default=0,
        ge=0,
        le=365,
        description="提前几天开始挂念这件事。",
        json_schema_extra={"label": "提前提醒天数"},
    )
    status: Literal["open", "done", "cancelled"] = Field(
        default="open", description="当前状态。", json_schema_extra={"label": "状态"}
    )
    note: str = Field(default="", description="补充说明。", json_schema_extra={"label": "备注"})
    stream_id: str = Field(
        default="", description="所在会话标识。", json_schema_extra={"label": "会话标识", "hidden": True}
    )
    target_user_id: str = Field(
        default="", description="帮别人提醒时写对方 QQ 号。", json_schema_extra={"label": "提醒对象"}
    )
    group_id: str = Field(
        default="", description="所属 QQ 群号。", json_schema_extra={"label": "群号", "hidden": True}
    )
    creator_id: str = Field(
        default="", description="创建者账号。", json_schema_extra={"label": "创建者", "hidden": True}
    )
    platform: str = Field(
        default="", description="所属平台。", json_schema_extra={"label": "平台", "hidden": True}
    )
    revision: int = Field(
        default=1, ge=1, description="修订号。", json_schema_extra={"label": "版本号", "hidden": True}
    )

    @field_validator("start", "end")
    @classmethod
    def valid_datetime(cls, value):
        if value:
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None:
                raise ValueError("待办时间必须包含时区")
        return value

    @model_validator(mode="after")
    def valid_range(self):
        if bool(self.start) != bool(self.end):
            raise ValueError("start 与 end 必须同时填写")
        if self.start and self.end and datetime.fromisoformat(self.end) <= datetime.fromisoformat(self.start):
            raise ValueError("end 必须晚于 start")
        return self


class WorkdayOverride(PluginConfigBase):
    date: str = Field(
        default="",
        description="覆盖哪一天的上班/放假状态（YYYY-MM-DD）。",
        json_schema_extra={"label": "覆盖日期", "placeholder": "2026-10-10"},
    )
    is_workday: bool = Field(
        default=True,
        description="勾选表示这天需要上班/上课，取消表示休息放假（优先级最高）。",
        json_schema_extra={"label": "是否工作日"},
    )

    @field_validator("date")
    @classmethod
    def valid_date(cls, value):
        if value:
            date.fromisoformat(value)
        return value


class HolidaySyncConfig(PluginConfigBase):
    __ui_label__ = "年度调休自动同步"
    enabled: bool = Field(
        default=True,
        description="每年国务院发完明年调休后自动在后台静默缓存静态年度 JSON（断网自动回落本地库）。",
        json_schema_extra={"label": "自动同步调休"},
    )
    feed_urls: list[str] = Field(
        default_factory=lambda: [
            "https://cdn.jsdelivr.net/gh/NateScarlet/holiday-cn@master/{year}.json",
            "https://fastly.jsdelivr.net/gh/NateScarlet/holiday-cn@master/{year}.json",
            "https://raw.githubusercontent.com/NateScarlet/holiday-cn/master/{year}.json",
        ],
        description="按顺序尝试的静态年度调休数据源模板，{year} 会替换成四位年份。",
        json_schema_extra={"label": "年度数据源镜像"},
    )
    timeout_seconds: float = Field(
        default=8.0,
        ge=1,
        le=30,
        description="单镜像拉取超时秒数",
        json_schema_extra={"label": "同步超时秒数", "hidden": True},
    )
    refresh_interval_days: int = Field(
        default=7,
        ge=1,
        le=90,
        description="年底探新或重刷间隔天数",
        json_schema_extra={"label": "重刷间隔天数", "hidden": True},
    )


class Admin(PluginConfigBase):
    platform: str = Field(default="qq", description="平台名称。", json_schema_extra={"label": "平台"})
    user_id: str = Field(
        default="",
        description="管理员 QQ 号。",
        json_schema_extra={"label": "管理员账号", "placeholder": "例如 987654"},
    )


class PluginInfo(PluginConfigBase):
    config_version: str = Field(default="0.1.0", description="配置版本，由 Runner 管理")


class Config(PluginConfigBase):
    scope: ScopeConfig = Field(default_factory=ScopeConfig, description="独立控制哪些群或人启用日历和待办")
    show_advanced: bool = Field(
        default=False,
        description="展开节气开关、调休覆盖、随口惦记与提醒模板。",
        json_schema_extra={"label": "显示高级设置"},
    )
    plugin: PluginInfo = Field(default_factory=PluginInfo)
    enabled: bool = Field(
        default=True,
        description="开启后感知中国节假日/农历/二十四节气，并支持自然语言记事和惦记。",
        json_schema_extra={"label": "启用日历待办"},
    )
    timezone: str = Field(
        default="Asia/Shanghai",
        description="判断今天日期和待办到期时间的时区。",
        json_schema_extra={"label": "本地时区"},
    )
    holiday_sync: HolidaySyncConfig = Field(default_factory=HolidaySyncConfig)
    day_rollover_hour: int = Field(
        default=5,
        ge=0,
        le=23,
        description="逻辑日切换小时",
        json_schema_extra={"label": "作息换日点", "hidden": True},
    )
    reminder_days: int = Field(
        default=3,
        ge=0,
        le=30,
        description="生日、节日或倒计时默认提前几天开始轻轻惦记。",
        json_schema_extra={"label": "默认提前几天"},
    )
    events: list[CalendarEntry] = Field(
        default_factory=list,
        description="旧版重要日期兼容字段。",
        json_schema_extra={"label": "兼容旧日子表", "hidden": True},
    )
    workday_overrides: list[WorkdayOverride] = Field(
        default_factory=list,
        description="优先级最高的工作日覆盖（例如学校单独调课、公司多放一天假）。",
        json_schema_extra={"label": "调休手动覆盖"},
    )
    admins: list[Admin] = Field(
        default_factory=list,
        description="有权使用 /待办 强制录入自己和双方约定日程的管理员（亦可从群关系继承）。",
        json_schema_extra={"label": "管理员名单"},
    )
    todos: list[Todo] = Field(
        default_factory=list,
        description="预设的一批固定待办事项（通常直接聊天让它记就行）。",
        json_schema_extra={"label": "初始待办表"},
    )
    hint_chars: int = Field(
        default=80,
        ge=0,
        le=280,
        description="特殊日子和临近提醒塞进聊天思考里的最多字数。",
        json_schema_extra={"label": "轻提示字数上限"},
    )
    hint_template: str = Field(
        default="{date}：{items}",
        description="今日日期与事项提示拼装写法。",
        json_schema_extra={"label": "日历提示格式", "hidden": True},
    )
    todo_template: str = Field(
        default="待办：{text}",
        description="单条待办轻提示格式。",
        json_schema_extra={"label": "待办提示格式", "hidden": True},
    )
    tick_seconds: int = Field(
        default=30,
        ge=5,
        le=300,
        description="到期提醒检查间隔",
        json_schema_extra={"label": "巡检间隔秒数", "hidden": True},
    )
    reminder_template: str = Field(
        default="{target}到点啦，记得：{text}",
        description="到点发提醒消息时的说话格式。",
        json_schema_extra={"label": "到点提醒句式"},
    )
    enable_solar_terms: bool = Field(
        default=True,
        description="感知冬至、清明、立春等二十四节气。",
        json_schema_extra={"label": "显示二十四节气"},
    )
    enable_traditional_lunar_holidays: bool = Field(
        default=True,
        description="感知春节、元宵、端午、七夕、中秋、除夕等传统农历节日。",
        json_schema_extra={"label": "显示传统节日"},
    )
    enable_solar_holidays: bool = Field(
        default=True,
        description="感知元旦、劳动节、国庆节等常见公历节日。",
        json_schema_extra={"label": "显示公历节日"},
    )
    care_note_enabled: bool = Field(
        default=True,
        description="对方随口提到考试、体检等事时默默记着，到了时间轻轻提示关心（绝不发冷冰冰闹钟）。",
        json_schema_extra={"label": "允许随口惦记"},
    )
    care_hint_window_hours: float = Field(
        default=12,
        ge=0.5,
        le=72,
        description="到了对方提到的时间前后几小时内，在对话里附上这句轻提示。",
        json_schema_extra={"label": "惦记有效小时"},
    )
    care_template: str = Field(
        default="对方之前随口提过「{text}」，聊天合适时可以顺嘴自然关心一下。",
        description="随口惦记触发时给自己的轻提示写法。",
        json_schema_extra={"label": "惦记轻提示句式"},
    )
    native_reminder_enabled: bool = Field(
        default=True,
        description="是否由本插件到点发消息提醒待办；如果改用宿主自带定时唤醒，可在这里关掉。",
        json_schema_extra={"label": "插件到点发提醒"},
    )
    default_todo_minutes: int = Field(
        default=60,
        ge=1,
        le=1440,
        description="未填结束时间的待办时长",
        json_schema_extra={"label": "默认待办分钟", "hidden": True},
    )
    dates: list[CalendarEntry] = Field(
        default_factory=list,
        description="登记生日、纪念日或考试倒计时（阳历/农历显式区分）。",
        json_schema_extra={"label": "重要日子与生日"},
    )
    use_chinese_calendar: bool = Field(
        default=True,
        description="当未手动覆盖且未联网同步到年度调休表时，使用本地内置节假日包兜底。",
        json_schema_extra={"label": "本地节假日库兜底"},
    )

    @field_validator("workday_overrides", mode="before")
    @classmethod
    def legacy_workdays(cls, value):
        return (
            [{"date": day, "is_workday": working} for day, working in value.items()]
            if isinstance(value, dict)
            else value
        )

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value):
        ZoneInfo(value)
        return value


_BASIC_FIELDS = ["enabled", "show_advanced", "timezone", "dates", "todos"]
for _name, _field in Config.model_fields.items():
    if _name not in _BASIC_FIELDS and _name != "plugin":
        _field.json_schema_extra = {
            **(_field.json_schema_extra or {}),
            "depends_on": "show_advanced",
            "depends_value": True,
        }
Config.model_rebuild(force=True)

for _model in list(globals().values()):
    if isinstance(_model, type) and issubclass(_model, PluginConfigBase):
        for _field_name, _field_info in _model.model_fields.items():
            _field_info.json_schema_extra = {
                "label": _field_info.description or _field_name,
                **(_field_info.json_schema_extra or {}),
            }
        _model.model_rebuild(force=True)
