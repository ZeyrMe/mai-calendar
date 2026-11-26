"""Small SDK boundary helpers vendored for independent installation."""

from __future__ import annotations

import asyncio
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from string import Formatter
from typing import Any


def result(data: Any = None, *, error: str = "") -> dict:
    return {
        "schema_version": 1,
        "success": not bool(error),
        "data": data,
        "error": error,
        "content": error or json.dumps(data, ensure_ascii=False),
    }


def inject(kwargs: dict, plugin_id: str, text: str, limit: int) -> dict:
    if not text or limit <= 0:
        return {"action": "continue", "modified_kwargs": kwargs}
    if "items" not in kwargs or kwargs.get("item_schema_version", 1) != 1:
        return {"action": "continue", "modified_kwargs": {**kwargs, "extra_prompt": text[:limit]}}
    identity = f"zeyr:{plugin_id}:context"
    items = [item for item in kwargs["items"] if item.get("meta", {}).get("item_id") != identity]
    items.append(
        {
            "item_type": "UserMessageItem",
            "meta": {
                "item_id": identity,
                "logical_turn_id": None,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            "parts": [{"type": "text", "text": text[:limit]}],
        }
    )
    return {"action": "continue", "modified_kwargs": {**kwargs, "items": items}}


class StateFile:
    def __init__(self, path: Path, initial: dict):
        self.path = path
        self.data = json.loads(json.dumps(initial))
        if path.exists():
            loaded = json.loads(path.read_text())
            if loaded.get("schema_version") != initial["schema_version"]:
                raise ValueError("不支持的状态文件版本")
            self.data = loaded

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=".state-", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w") as handle:
                json.dump(self.data, handle, ensure_ascii=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)


def send_succeeded(response: Any) -> bool:
    """SDK text() returns bool or SendResult, which has no success field."""
    return response is True or (isinstance(response, dict) and response.get("sent") is True)


def send_receipt(response: Any, fallback: str) -> str:
    return str(response.get("message_id") or fallback) if isinstance(response, dict) else fallback


def render(template: str, **values: Any) -> str:
    # Only plain named fields; never execute expressions or traverse Python objects.
    fields = [field for _, field, _, _ in Formatter().parse(template) if field is not None]
    if any(not re.fullmatch(r"[a-z_]+", field) for field in fields):
        raise ValueError("模板只支持 {name} 形式的命名字段")
    return template.format_map({key: str(value) for key, value in values.items()})


async def optional_api(ctx: Any, full_name: str, **kwargs: Any) -> Any:
    try:
        async with asyncio.timeout(0.4):
            if not await ctx.api.get(full_name, version="1"):
                return None
            payload = await ctx.api.call(full_name, version="1", **kwargs)
        # Installed SDK exposes Host's outer success/result envelope.
        while isinstance(payload, dict) and "result" in payload and "schema_version" not in payload:
            if not payload.get("success", False):
                return None
            payload = payload["result"]
        if not isinstance(payload, dict) or not payload.get("success"):
            return None
        return payload.get("data")
    except (Exception, TimeoutError):
        return None


async def service_send(ctx: Any, text: str, stream_id: str, **kwargs: Any) -> Any:
    """Authorize only this exact service output; day remains an optional dependency."""
    await optional_api(ctx, "zeyr.mai-day.authorize_service_send", stream_id=stream_id, text=text)
    try:
        return await ctx.send.text(text, stream_id, **kwargs)
    finally:
        await optional_api(ctx, "zeyr.mai-day.revoke_service_send", stream_id=stream_id, text=text)
