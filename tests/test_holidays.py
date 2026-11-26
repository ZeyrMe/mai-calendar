import importlib
import json
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from conftest import module

holidays_mod = importlib.import_module(module.__package__ + ".holidays")


def test_four_tier_holiday_priority_and_compensation_workday(tmp_path):
    p = module.Plugin()
    p.set_plugin_config(
        {
            "plugin": {"config_version": "0.1.0"},
            "workday_overrides": [{"date": "2028-10-01", "is_workday": True}],
        }
    )
    p.store = module.StateFile(tmp_path / "calendar.json", module.initial_state())
    p.holidays = module.HolidayStore(tmp_path / "holidays")
    p.zone = module.ZoneInfo("Asia/Shanghai")

    # Future year 2028 (not in chinese_calendar) resolved cleanly from cached annual holiday JSON.
    raw = json.dumps(
        {
            "year": 2028,
            "days": [
                {"date": "2028-10-01", "name": "国庆节", "isOffDay": True},
                {"date": "2028-10-02", "name": "国庆节", "isOffDay": True},
                {"date": "2028-10-08", "name": "国庆节", "isOffDay": False},
            ],
        }
    ).encode("utf-8")
    p.holidays._save_year(
        2028,
        holidays_mod.parse_holiday_payload(2028, raw, "2028-01-01T00:00:00+08:00"),
    )

    # 1. Explicit workday_overrides wins over holiday JSON
    assert p.is_workday(date(2028, 10, 1)) is True
    # 2. Holiday off day & makeup workday from synced JSON
    assert p.is_workday(date(2028, 10, 2)) is False
    assert p.is_workday(date(2028, 10, 8)) is True
    ctx_makeup = p.day_context(date(2028, 10, 8))
    assert ctx_makeup["valid"] is True
    assert any("调休补班" in item["title"] for item in ctx_makeup["events_today"])

    # Disk persistence reloads cleanly without network.
    reloaded = module.HolidayStore(tmp_path / "holidays")
    reloaded.load_from_disk([2028])
    assert reloaded.has_year(2028)
    assert reloaded.lookup(date(2028, 10, 8))["is_workday"] is True


@pytest.mark.asyncio
async def test_holiday_sync_mirror_fallback_and_widget_action(tmp_path):
    p = module.Plugin()
    p.set_plugin_config(
        {
            "plugin": {"config_version": "0.1.0"},
            "holiday_sync": {
                "enabled": True,
                "feed_urls": [
                    "https://mirror-a.example.com/{year}.json",
                    "https://mirror-b.example.com/{year}.json",
                ],
            },
        }
    )
    p.store = module.StateFile(tmp_path / "calendar.json", module.initial_state())
    p.holidays = module.HolidayStore(tmp_path / "holidays")
    p.zone = module.ZoneInfo("Asia/Shanghai")
    p.now = lambda: datetime.fromisoformat("2028-11-15T10:00:00+08:00")

    payload = json.dumps(
        {"year": 2029, "days": [{"date": "2029-01-01", "name": "元旦", "isOffDay": True}]}
    ).encode("utf-8")

    def handler(request: httpx.Request):
        if "mirror-a" in str(request.url):
            return httpx.Response(503)
        if "2029.json" in str(request.url):
            return httpx.Response(200, content=payload)
        return httpx.Response(200, content=json.dumps({"year": 2028, "days": []}).encode("utf-8"))

    transport = httpx.MockTransport(handler)
    ok = await p.holidays.sync_year(
        2029,
        p.config.holiday_sync.feed_urls,
        now=p.now(),
        client_factory=lambda: httpx.AsyncClient(transport=transport),
    )
    assert ok is True
    assert p.holidays.lookup(date(2029, 1, 1))["is_off_day"] is True

    # Verify private/localhost feed URLs are blocked by SSRF check.
    with pytest.raises(ValueError, match="非公网|内网|本地"):
        holidays_mod.validate_public_url("http://127.0.0.1/2029.json")

    # Verify sync_holidays widget action works end-to-end.
    p._set_context(SimpleNamespace(api=SimpleNamespace(get=AsyncMock(return_value=None))))
    p.sync_holidays_if_needed = AsyncMock()
    await p.on_config_widget_action("sync_holidays")
    p.sync_holidays_if_needed.assert_awaited_once_with(force=True)
