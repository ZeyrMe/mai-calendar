import importlib
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

from conftest import module

calendar_dates = importlib.import_module(module.__package__ + ".dates")


def test_solar_terms_lunar_holidays_and_new_year_eve_are_real_dates():
    config = module.Config()
    assert "冬至" in calendar_dates.civil_context(date(2026, 12, 22), config)["names"]
    assert "春节" in calendar_dates.civil_context(date(2026, 2, 17), config)["names"]
    assert "除夕" in calendar_dates.civil_context(date(2026, 2, 16), config)["names"]


def test_explicit_lunar_yearly_birthday_and_solar_default_are_separate():
    Entry = module.config_models.CalendarEntry
    solar = Entry(date="2020-01-01", yearly=True)
    lunar = Entry(date="2020-01-01", yearly=True, calendar="lunar")
    assert calendar_dates.occurrence(solar, date(2026, 1, 1)) == date(2026, 1, 1)
    assert calendar_dates.occurrence(lunar, date(2026, 1, 1)) == date(2026, 2, 17)
    # Valid lunar day 30 is not rejected as February 30 in Gregorian parsing.
    Entry(date="2026-02-30", calendar="lunar")


def test_human_times_are_local_timezone_and_weekday_is_explicit():
    now = datetime.fromisoformat("2026-11-27T12:00:00+08:00")
    assert calendar_dates.parse_time("明天 20:00", now) == "2026-11-28T20:00:00+08:00"
    assert calendar_dates.parse_time("周五晚上8点", now) == "2026-11-27T20:00:00+08:00"
    assert calendar_dates.parse_time("12-01 09:30", now) == "2026-12-01T09:30:00+08:00"


async def test_care_notes_only_hint_in_own_chat_never_alarm_or_schedule(tmp_path):
    plugin = module.Plugin()
    plugin.set_plugin_config({})
    plugin.store = module.StateFile(tmp_path / "calendar.json", module.initial_state())
    plugin.now = lambda: datetime.fromisoformat("2026-11-27T12:00:00+08:00")
    plugin._set_context(SimpleNamespace(send=SimpleNamespace(text=AsyncMock())))
    plugin.manage("add", "care_note", "答辩", "今天 12:00", stream_id="s", creator_id="u")
    await plugin.remind_due()
    plugin.ctx.send.text.assert_not_awaited()
    assert "答辩" in plugin.hint("s")
    assert "答辩" not in plugin.hint("other")
    assert not (await plugin.api_schedulable())["data"]["items"]


def test_unknown_chinese_workday_year_is_not_claimed_official(tmp_path):
    plugin = module.Plugin()
    plugin.set_plugin_config({})
    plugin.store = module.StateFile(tmp_path / "calendar.json", module.initial_state())
    assert plugin.day_context(date(2049, 2, 1))["valid"] is False


def test_calendar_alone_refuses_overlapping_confirmed_mutual_appointments(tmp_path):
    import pytest

    p = module.Plugin()
    p.set_plugin_config({})
    p.store = module.StateFile(tmp_path / "calendar.json", module.initial_state())
    p.manage("add", "mutual", "已有约定", "2026-12-01T18:00:00+08:00", "2026-12-01T19:00:00+08:00")
    with pytest.raises(ValueError, match="刚性待办"):
        p.manage("add", "self", "新邀约", "2026-12-01T18:30:00+08:00", "2026-12-01T19:30:00+08:00")
