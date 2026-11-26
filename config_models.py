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
        json_schema_extra={"label": "日期", "placeholder": "写 YYYY-MM-DD；农历写对应农历月日如 2000-08-15"},
    )
    title: str = Field(
        default="",
        description="这个日子的名称，比如 老铁生日、返校日。",
        json_schema_extra={"label": "事件名称", "placeholder": "这个日子叫什么，如：阿云生日、考研初试"},
    )
    kind: Literal["holiday", "workday", "birthday", "countdown", "custom"] = Field(
        default="custom",
        description="节日类型。",
        json_schema_extra={
            "label": "类型",
            "enum_labels": {
                "birthday": "birthday（生日，建议勾选每年重复）",
                "countdown": "countdown（考试/纪念日倒计时）",
                "holiday": "holiday（自定义休息日）",
                "workday": "workday（自定义工作日）",
                "custom": "custom（其他特别日子）",
            },
        },
    )
    calendar: Literal["solar", "lunar"] = Field(
        default="solar",
        description="solar 阳历；lunar 农历。",
        json_schema_extra={
            "label": "历法",
            "enum_labels": {
                "solar": "solar（公历/阳历，默认）",
                "lunar": "lunar（农历/阴历，年年自动换算公历）",
            },
        },
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
        json_schema_extra={"label": "补充备注", "placeholder": "选填备注，如：喜欢吃抹茶蛋糕"},
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
        description="待办归属类型。",
        json_schema_extra={
            "label": "归属类型",
            "enum_labels": {
                "self": "self（自己的安排，会进麦的一天）",
                "mutual": "mutual（双方约定，不可强行挪期）",
                "other": "other（帮群友记的到点提醒）",
                "care_note": "care_note（随口惦记，不发冰冷闹钟）",
            },
        },
    )
    text: str = Field(
        default="",
        description="具体要做什么或提醒什么。",
        json_schema_extra={"label": "事项内容", "placeholder": "写清楚事情内容，如：晚上八点一起联机打游戏"},
    )
    start: str = Field(
        default="",
        description="开始时间（含时区 ISO 格式）。",
        json_schema_extra={"label": "开始时间", "placeholder": "含时区格式，如：2026-12-01T20:00:00+08:00"},
    )
    end: str = Field(
        default="",
        description="结束时间（含时区 ISO 格式）。",
        json_schema_extra={
            "label": "结束时间",
            "placeholder": "须晚于开始时间，如：2026-12-01T22:00:00+08:00",
        },
    )
    flexibility: Literal["locked", "soft", "open"] = Field(
        default="soft",
        description="日程刚度。",
        json_schema_extra={
            "label": "时间刚度",
            "enum_labels": {
                "locked": "locked（刚性不可让）",
                "soft": "soft（柔和，可协商挪动）",
                "open": "open（自由安排）",
            },
        },
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
    note: str = Field(
        default="",
        description="补充说明。",
        json_schema_extra={"label": "备注", "placeholder": "选填补充细节"},
    )
    stream_id: str = Field(
        default="", description="所在会话标识。", json_schema_extra={"label": "会话标识", "hidden": True}
    )
    target_user_id: str = Field(
        default="",
        description="帮别人提醒时写对方 QQ 号。",
        json_schema_extra={"label": "提醒对象", "placeholder": "仅 other 需要填被提醒人的 QQ 号"},
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
        json_schema_extra={"label": "覆盖日期", "placeholder": "按 YYYY-MM-DD 填写，如 2026-10-10"},
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
    """每年国务院公布新年放假与调休安排后，自动从静态开源镜像拉取 JSON 并缓存到本地磁盘。断网时会无感回落到本地内置节假日库，手动覆盖永远优先。"""

    __ui_label__ = "年度调休自动同步"
    enabled: bool = Field(
        default=True,
        description="后台自动按年缓存官方调休表（不依赖每年升级 Python 依赖包）。",
        json_schema_extra={
            "label": "自动同步调休",
            "order": 1,
            "hint": "推荐保持开启：平时 100% 读本地磁盘缓存，仅缺当年数据或每年 11–12 月自动探一次新年数据。",
        },
    )
    feed_urls: list[str] = Field(
        default_factory=lambda: [
            "https://cdn.jsdelivr.net/gh/NateScarlet/holiday-cn@master/{year}.json",
            "https://fastly.jsdelivr.net/gh/NateScarlet/holiday-cn@master/{year}.json",
            "https://raw.githubusercontent.com/NateScarlet/holiday-cn/master/{year}.json",
        ],
        description="按顺序尝试的静态年度调休数据源模板，{year} 会替换成四位年份。",
        json_schema_extra={
            "label": "年度数据源镜像",
            "order": 2,
            "placeholder": "填写含 {year} 占位的公开 HTTPS JSON 地址",
            "hint": "已内置三条开源镜像顺序降级；如果机器处于特殊网络环境，可把私有静态镜像放在第一条。",
        },
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
    platform: str = Field(
        default="qq", description="平台名称。", json_schema_extra={"label": "平台", "placeholder": "默认 qq"}
    )
    user_id: str = Field(
        default="",
        description="管理员 QQ 号。",
        json_schema_extra={"label": "管理员账号", "placeholder": "填允许用 /待办 强制记日程的 QQ 号"},
    )


class PluginInfo(PluginConfigBase):
    config_version: str = Field(default="0.1.0", description="配置版本，由 Runner 管理")


class Config(PluginConfigBase):
    scope: ScopeConfig = Field(default_factory=ScopeConfig, description="独立控制哪些群或人启用日历和待办")
    show_advanced: bool = Field(
        default=False,
        description="展开节气开关、调休覆盖、随口惦记与提醒模板。",
        json_schema_extra={
            "label": "显示高级设置",
            "order": 6,
            "hint": "需要调整节假日库优先级、随口惦记时间窗、管理员或关闭本插件闹钟改为宿主原生提醒时勾选展开。",
        },
    )
    plugin: PluginInfo = Field(default_factory=PluginInfo)
    enabled: bool = Field(
        default=True,
        description="开启后感知中国节假日/农历/二十四节气，并支持自然语言记事和惦记。",
        json_schema_extra={
            "label": "启用日历待办",
            "order": 1,
            "hint": "若同时安装了「麦的一天」，今天的放假/补班判断和 self/mutual 待办会自动喂给生活日程表。",
        },
    )
    timezone: str = Field(
        default="Asia/Shanghai",
        description="判断今天日期和待办到期时间的时区。",
        json_schema_extra={
            "label": "本地时区",
            "order": 2,
            "placeholder": "填写 IANA 标准时区名，如 Asia/Shanghai、Asia/Tokyo",
            "hint": "中国大陆保持默认 Asia/Shanghai 即可，必须填标准地区时区名，不要写 UTC+8。",
        },
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
        json_schema_extra={
            "label": "默认提前几天",
            "hint": "单位：天（默认 3）。单条日子没设单独提前天数时使用此值；填 0 表示当天才提起。",
        },
    )
    events: list[CalendarEntry] = Field(
        default_factory=list,
        description="旧版重要日期兼容字段。",
        json_schema_extra={"label": "兼容旧日子表", "hidden": True},
    )
    workday_overrides: list[WorkdayOverride] = Field(
        default_factory=list,
        description="优先级最高的工作日覆盖（例如学校单独调课、公司多放一天假）。",
        json_schema_extra={
            "label": "调休手动覆盖",
            "hint": "覆盖规则永远高于远程调休表和内置库：比如某天学校单独补课，勾选「是否工作日」即可。",
        },
    )
    admins: list[Admin] = Field(
        default_factory=list,
        description="有权使用 /待办 强制录入自己和双方约定日程的管理员。",
        json_schema_extra={
            "label": "管理员名单",
            "hint": "普通群友聊天用自然语言也能约日程；只有 /待办 + self/mutual 强指令需要管理员权限。此处留空亦可继承「群关系」管理员。",
        },
    )
    todos: list[Todo] = Field(
        default_factory=list,
        description="预设的一批固定待办事项（通常直接聊天让它记就行）。",
        json_schema_extra={
            "label": "初始待办表",
            "order": 5,
            "hint": "一般保持留空，平时群聊/私聊里自然提到或发 /待办 就能实时记；只有启动就想带固定待办时才写在这里。",
        },
    )
    hint_chars: int = Field(
        default=80,
        ge=0,
        le=280,
        description="特殊日子和临近提醒塞进聊天思考里的最多字数。",
        json_schema_extra={
            "label": "轻提示字数上限",
            "hint": "普通工作日不注入（0 字）；仅今天命中节日/节气/生日倒计时或临近待办/惦记时才注 1 句。",
        },
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
        json_schema_extra={
            "label": "到点提醒句式",
            "hint": "可用 {target}（被提醒人标识，self/mutual 为空）与 {text}（事项内容）。",
        },
    )
    enable_solar_terms: bool = Field(
        default=True,
        description="感知冬至、清明、立春等二十四节气。",
        json_schema_extra={
            "label": "显示二十四节气",
            "hint": "打开后冬至、夏至、大寒等节气当天会自动带上背景提示。",
        },
    )
    enable_traditional_lunar_holidays: bool = Field(
        default=True,
        description="感知春节、元宵、端午、七夕、中秋、除夕等传统农历节日。",
        json_schema_extra={
            "label": "显示传统节日",
            "hint": "依据 lunar-python 农历精确换算，包含除夕和元宵/七夕等非法定节日。",
        },
    )
    enable_solar_holidays: bool = Field(
        default=True,
        description="感知元旦、劳动节、国庆节等常见公历节日。",
        json_schema_extra={
            "label": "显示公历节日",
            "hint": "包含元旦、情人节、妇女节、劳动节、儿童节、国庆节。",
        },
    )
    care_note_enabled: bool = Field(
        default=True,
        description="对方随口提到考试、体检等事时默默记着，到了时间轻轻提示关心。",
        json_schema_extra={
            "label": "允许随口惦记",
            "hint": "随口惦记不会发到点报时闹钟，只会在对应时间窗里作为轻提示让 Bot 自然顺嘴关心一句。",
        },
    )
    care_hint_window_hours: float = Field(
        default=12,
        ge=0.5,
        le=72,
        description="到了对方提到的时间前后几小时内，在对话里附上这句轻提示。",
        json_schema_extra={
            "label": "惦记有效小时",
            "hint": "单位：小时（默认 12）。在这个前后时间窗内对方说话时触发一次轻关心。",
        },
    )
    care_template: str = Field(
        default="对方之前随口提过「{text}」，聊天合适时可以顺嘴自然关心一下。",
        description="随口惦记触发时给自己的轻提示写法。",
        json_schema_extra={"label": "惦记轻提示句式", "hint": "支持 {text} 占位，保留自然的提示口吻即可。"},
    )
    native_reminder_enabled: bool = Field(
        default=True,
        description="是否由本插件到点发消息提醒待办。",
        json_schema_extra={
            "label": "插件到点发提醒",
            "hint": "MaiBot 1.4.4+ 已自带原生定时唤醒；如果你更习惯全交由宿主自带闹钟提醒，可关闭此项，仅保留本插件的历法与日程联动。",
        },
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
        json_schema_extra={
            "label": "重要日子与生日",
            "order": 4,
            "hint": "每条必填「日期(YYYY-MM-DD) + 事件名称」；如果是阴历生日，历法务必手动选 lunar 并勾上“每年重复”（程序绝不猜字面自动转阴历）。",
        },
    )
    use_chinese_calendar: bool = Field(
        default=True,
        description="当未手动覆盖且未联网同步到年度调休表时，使用本地内置节假日包兜底。",
        json_schema_extra={
            "label": "本地节假日库兜底",
            "hint": "建议保留开启：就算完全断网也能识别已知年份的法定调休安排。",
        },
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
