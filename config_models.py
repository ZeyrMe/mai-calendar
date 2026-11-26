from datetime import date
from typing import Literal
from zoneinfo import ZoneInfo

from maibot_sdk import Field, PluginConfigBase
from pydantic import field_validator, model_validator


class CalendarEntry(PluginConfigBase):
    date: str = Field(default="", description="日期 YYYY-MM-DD")
    title: str = Field(default="", description="名称")
    kind: Literal["holiday", "workday", "birthday", "countdown", "custom"] = Field(default="custom")
    yearly: bool = Field(default=False, description="每年重复，用于生日等日期")
    reminder_days: int = Field(default=0, ge=0, le=365, description="提前提醒天数")
    note: str = Field(default="", description="简短说明")

    @field_validator("date")
    @classmethod
    def valid_date(cls, value):
        if value:
            date.fromisoformat(value)
        return value


class Todo(PluginConfigBase):
    id: str = Field(default="", description="稳定标识；空值由插件生成")
    owner_type: Literal["self", "mutual", "other"] = Field(default="self", description="归属")
    text: str = Field(default="", description="待办内容")
    start: str = Field(default="", description="开始时间 ISO 8601")
    end: str = Field(default="", description="结束时间 ISO 8601")
    flexibility: Literal["locked", "soft", "open"] = Field(default="soft", description="日程刚度")
    remind_days: int = Field(default=0, ge=0, le=365, description="提前提醒天数")
    status: Literal["open", "done", "cancelled"] = Field(default="open", description="状态")
    note: str = Field(default="", description="备注")

    @field_validator("start", "end")
    @classmethod
    def valid_datetime(cls, value):
        if value:
            from datetime import datetime

            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None:
                raise ValueError("待办时间必须包含时区")
        return value

    @model_validator(mode="after")
    def valid_range(self):
        if bool(self.start) != bool(self.end):
            raise ValueError("start 与 end 必须同时填写")
        if self.start and self.end and self.end <= self.start:
            raise ValueError("end 必须晚于 start")
        return self


class PluginInfo(PluginConfigBase):
    config_version: str = Field(default="0.1.0", description="配置版本，由 Runner 管理")


class Config(PluginConfigBase):
    show_advanced: bool = Field(default=False, description="显示高级设置")
    plugin: PluginInfo = Field(default_factory=PluginInfo)
    enabled: bool = Field(default=True, description="启用插件")
    timezone: str = Field(default="Asia/Shanghai", description="本地时区")
    day_rollover_hour: int = Field(default=5, ge=0, le=23, description="逻辑日切换小时")
    reminder_days: int = Field(default=3, ge=0, le=30, description="特殊日期默认提前提醒天数")
    events: list[CalendarEntry] = Field(default_factory=list, description="节日、调休和倒计时配置")
    workday_overrides: dict[str, bool] = Field(default_factory=dict, description="日期到是否工作日的覆盖")
    todos: list[Todo] = Field(default_factory=list, description="初始待办")
    hint_chars: int = Field(default=80, ge=0, le=280, description="轻提示字数上限")
    hint_template: str = Field(default="{date}：{items}", description="轻提示模板")
    todo_template: str = Field(default="待办：{text}", description="待办提醒模板")
    use_chinese_calendar: bool = Field(default=True, description="使用 chinese-calendar 内置节假日判断")

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value):
        ZoneInfo(value)
        return value


_BASIC_FIELDS = ["enabled", "show_advanced", "timezone", "events", "todos"]
for _name, _field in Config.model_fields.items():
    if _name not in _BASIC_FIELDS and _name != "plugin":
        _field.json_schema_extra = {
            **(_field.json_schema_extra or {}),
            "depends_on": "show_advanced",
            "depends_value": True,
        }
Config.model_rebuild(force=True)
