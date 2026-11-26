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


@pytest.mark.asyncio
async def test_week_query_returns_seven_consecutive_days(plugin):
    plugin.logical_date = lambda: date(2026, 11, 27)
    response = await plugin.query_calendar(range="week")
    assert response["success"]
    assert [row["date"] for row in response["data"]["days"]] == [
        "2026-11-27",
        "2026-11-28",
        "2026-11-29",
        "2026-11-30",
        "2026-12-01",
        "2026-12-02",
        "2026-12-03",
    ]


@pytest.mark.asyncio
async def test_api_cannot_modify_another_stream_even_as_admin(plugin):
    plugin.config.admins = [module.config_models.Admin(user_id="admin")]
    row = plugin.manage("add", text="原安排", stream_id="s1")
    response = await plugin.api_manage(
        "cancel", todo_id=row["id"], stream_id="s2", creator_id="admin", platform="qq"
    )
    assert not response["success"]
    assert plugin.todo_rows()[0]["status"] == "open"


@pytest.mark.asyncio
@pytest.mark.parametrize("owner", ["self", "mutual"])
async def test_force_commands_need_admin_but_natural_agreements_are_allowed(plugin, owner):
    plugin._set_context(SimpleNamespace(send=SimpleNamespace(text=AsyncMock())))
    message = {"platform": "qq", "session_id": "s", "message_info": {"user_info": {"user_id": "user"}}}
    command = await plugin.todo_add(
        message=message,
        stream_id="s",
        matched_groups={
            "owner": owner,
            "start": "2026-11-27T10:00:00+08:00",
            "end": "2026-11-27T11:00:00+08:00",
            "text": "安排",
        },
    )
    tool = await plugin.manage_todo("add", owner_type=owner, text="安排", message=message)
    api = await plugin.api_manage(
        "add", owner_type=owner, text="安排", stream_id="s", creator_id="user", platform="qq"
    )
    assert command[0] is False and tool["success"] and api["success"]
    assert len(plugin.todo_rows()) == 2
    plugin.ctx.send.text.assert_not_awaited()


@pytest.mark.asyncio
async def test_admin_command_records_creator_and_sends_confirmation(plugin):
    plugin.config.admins = [module.config_models.Admin(user_id="admin")]
    plugin._set_context(SimpleNamespace(send=SimpleNamespace(text=AsyncMock(return_value=True))))
    response = await plugin.todo_add(
        message={"platform": "qq", "message_info": {"user_info": {"user_id": "admin"}}},
        stream_id="s",
        matched_groups={
            "owner": "self",
            "start": "2026-11-27T10:00:00+08:00",
            "end": "2026-11-27T11:00:00+08:00",
            "text": "安排",
        },
    )
    assert response[0]
    assert plugin.todo_rows()[0]["creator_id"] == "admin"
    plugin.ctx.send.text.assert_awaited_once_with("待办已记录：安排", "s")


def test_templates_reject_attribute_access(plugin):
    plugin.config.hint_template = "{items.__class__}"
    plugin.logical_date = lambda: date(2026, 11, 27)
    with pytest.raises(ValueError, match="模板"):
        plugin.hint()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response", [True, {"sent": True, "message_id": "receipt"}, {"sent": False, "message_id": None}]
)
async def test_reminder_uses_sdk_send_result_and_only_retries_failures(plugin, response):
    plugin.now = lambda: datetime.fromisoformat("2026-11-27T12:00:00+08:00")
    row = plugin.manage(
        "add", text="到期", start="2026-11-27T10:00:00+08:00", end="2026-11-27T11:00:00+08:00", stream_id="s"
    )
    plugin._set_context(SimpleNamespace(send=SimpleNamespace(text=AsyncMock(return_value=response))))
    await plugin.remind_due()
    await plugin.remind_due()
    assert plugin.ctx.send.text.await_count == (1 if response is True or response["sent"] else 2)
    assert (f"{row['id']}:1" in plugin.store.data["reminded"]) == (response is True or response["sent"])


def test_legacy_workday_map_roundtrips_as_editable_entries(plugin):
    stored = plugin.config.model_dump(mode="python")
    assert stored["workday_overrides"] == [{"date": "2026-11-28", "is_workday": True}]
    plugin.set_plugin_config(stored)
    assert plugin.is_workday(date(2026, 11, 28))
