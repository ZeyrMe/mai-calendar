from datetime import date, datetime

import pytest
from conftest import module


@pytest.fixture
def plugin(tmp_path):
    instance = module.Plugin()
    instance.set_plugin_config({"plugin": {"config_version": "0.1.0"}})
    instance.store = module.StateFile(tmp_path / "calendar.json", module.initial_state())
    instance.zone = module.ZoneInfo("Asia/Shanghai")
    instance.config.events = [
        module.config_models.CalendarEntry(
            date="2026-12-01", title="纪念日", kind="countdown", reminder_days=5
        )
    ]
    instance.config.reminder_days = 5
    instance.config.workday_overrides = {"2026-11-28": True}
    return instance


def test_logical_day_and_workday_override(plugin):
    now = datetime.fromisoformat("2026-11-27T03:30:00+08:00")
    assert plugin.logical_date(now) == date(2026, 11, 26)
    assert plugin.is_workday(date(2026, 11, 28))


def test_event_countdown_and_todo_ownership(plugin):
    plugin.manage("add", "self", "写报告", "2026-11-27T10:00:00+08:00", "2026-11-27T11:00:00+08:00")
    plugin.manage("add", "other", "提醒对方", "2026-11-27T12:00:00+08:00", "2026-11-27T13:00:00+08:00")
    context = plugin.day_context(date(2026, 11, 27))
    assert context["upcoming_events"][0]["days"] == 4
    assert len(context["todos_today"]) == 2
    assert len(plugin.todo_for_day(date(2026, 11, 27), include_other=False)) == 1


def test_manage_todo_lifecycle_and_invalid_empty_text(plugin):
    with pytest.raises(ValueError, match="不能为空"):
        plugin.manage("add", text="", start="2026-11-27T10:00:00+08:00", end="2026-11-27T11:00:00+08:00")
    row = plugin.manage(
        "add", text="买咖啡", start="2026-11-27T10:00:00+08:00", end="2026-11-27T11:00:00+08:00"
    )
    assert plugin.manage("complete", todo_id=row["id"])["status"] == "done"
    assert plugin.manage("list")["items"][0]["status"] == "done"
