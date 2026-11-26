from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

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


def test_todos_are_scoped_to_stream(plugin):
    plugin.manage(
        "add",
        text="当前会话",
        start="2026-11-27T10:00:00+08:00",
        end="2026-11-27T11:00:00+08:00",
        stream_id="s1",
    )
    plugin.manage(
        "add",
        text="另一个会话",
        start="2026-11-27T10:00:00+08:00",
        end="2026-11-27T11:00:00+08:00",
        stream_id="s2",
    )
    assert [row["text"] for row in plugin.todo_rows() if row["stream_id"] == "s1"] == ["当前会话"]


@pytest.mark.asyncio
async def test_due_reminder_records_successful_receipt(plugin):
    plugin.store.data["todos"].append(
        {
            "id": "due",
            "owner_type": "other",
            "text": "提醒",
            "start": "2026-11-26T09:00:00+08:00",
            "end": "2026-11-26T10:00:00+08:00",
            "flexibility": "soft",
            "remind_days": 0,
            "status": "open",
            "note": "",
            "stream_id": "s",
            "target_user_id": "u",
            "creator_id": "c",
            "platform": "qq",
            "revision": 1,
        }
    )
    plugin.now = lambda: datetime.fromisoformat("2026-11-27T09:00:00+08:00")
    plugin._set_context(
        SimpleNamespace(
            send=SimpleNamespace(
                text=AsyncMock(return_value={"success": True, "sent": True, "message_id": "r"})
            )
        )
    )
    await plugin.remind_due()
    await plugin.remind_due()
    assert plugin.store.data["reminded"]["due:1"] == "r"
