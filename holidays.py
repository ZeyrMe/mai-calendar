"""Static annual China holiday JSON sync and local disk cache."""

from __future__ import annotations

import ipaddress
import json
import os
import tempfile
import time
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import httpx

MAX_HOLIDAY_BYTES = 512 * 1024


def validate_public_url(url: str) -> str:
    parsed = urlsplit(url.strip())
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("节假日数据源必须是有效的 http/https 地址")
    host = parsed.hostname.rstrip(".").lower()
    if (
        "%" in host
        or host == "localhost"
        or host.endswith((".localhost", ".local", ".internal", ".home", ".lan"))
    ):
        raise ValueError("节假日数据源禁止使用内网或本地地址")
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        if "." not in host:
            raise ValueError("节假日数据源禁止使用本地名称") from None
        return url
    if not addr.is_global or addr.is_multicast:
        raise ValueError("节假日数据源禁止使用非公网地址")
    return url


def parse_holiday_payload(year: int, raw: bytes, synced_at: str) -> dict:
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("days"), list):
        raise ValueError("年度节假日数据格式无效")
    days: dict[str, dict] = {}
    for row in payload["days"]:
        if not isinstance(row, dict):
            continue
        day_str = str(row.get("date") or "").strip()
        is_off = row.get("isOffDay")
        if not day_str or not isinstance(is_off, bool):
            continue
        parsed = date.fromisoformat(day_str)
        if parsed.year != year:
            continue
        days[day_str] = {
            "name": str(row.get("name") or "").strip()[:60],
            "is_off_day": is_off,
        }
    return {
        "schema_version": 1,
        "year": year,
        "synced_at": synced_at,
        "days": days,
    }


class HolidayStore:
    def __init__(self, directory: Path):
        self.directory = directory
        self.years: dict[int, dict] = {}
        self.last_attempts: dict[int, float] = {}

    def _year_path(self, year: int) -> Path:
        return self.directory / f"{year}.json"

    def load_year(self, year: int) -> bool:
        path = self._year_path(year)
        if not path.is_file():
            return False
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict) and isinstance(loaded.get("days"), dict):
                self.years[year] = loaded
                return True
        except Exception:
            return False
        return False

    def load_from_disk(self, years: list[int]) -> None:
        for year in years:
            self.load_year(year)

    def _save_year(self, year: int, data: dict) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".holiday-{year}-", dir=self.directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, self._year_path(year))
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
        self.years[year] = data

    def has_year(self, year: int) -> bool:
        return year in self.years

    def lookup(self, day: date) -> dict | None:
        table = self.years.get(day.year)
        if not table:
            return None
        entry = table.get("days", {}).get(day.isoformat())
        if not entry:
            return None
        is_off = bool(entry.get("is_off_day"))
        name = str(entry.get("name") or "")
        title = name if is_off else (f"{name}调休补班" if name else "调休补班")
        return {
            "is_workday": not is_off,
            "is_off_day": is_off,
            "title": title,
            "name": name,
        }

    def should_refresh(self, year: int, now: datetime, refresh_interval_days: int) -> bool:
        last = self.last_attempts.get(year)
        if last is not None and time.monotonic() - last < 86400:
            return False
        table = self.years.get(year)
        if not table:
            return True
        synced_at = table.get("synced_at") or ""
        try:
            age = (now - datetime.fromisoformat(synced_at)).total_seconds()
            return age >= refresh_interval_days * 86400
        except ValueError:
            return True

    def summary_text(self, current_year: int) -> str:
        parts = []
        for year in (current_year, current_year + 1):
            parts.append(f"{year}({'已同步' if self.has_year(year) else '未同步'})")
        return "、".join(parts)

    async def _fetch_bytes(self, client: httpx.AsyncClient, url: str, timeout: float) -> bytes:
        current = validate_public_url(url)
        for hop in range(4):
            async with client.stream("GET", current, timeout=timeout, follow_redirects=False) as response:
                if response.status_code in (301, 302, 303, 307, 308):
                    location = response.headers.get("location")
                    if hop == 3 or not location:
                        raise ValueError("重定向次数过多")
                    current = validate_public_url(urljoin(current, location))
                    continue
                response.raise_for_status()
                chunks, total = [], 0
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > MAX_HOLIDAY_BYTES:
                        raise ValueError("节假日文件过大")
                    chunks.append(chunk)
                return b"".join(chunks)
        raise ValueError("重定向失败")

    async def sync_year(
        self,
        year: int,
        feed_urls: list[str],
        *,
        timeout_seconds: float = 8.0,
        now: datetime | None = None,
        client_factory=None,
    ) -> bool:
        self.last_attempts[year] = time.monotonic()
        synced_at = (now or datetime.now().astimezone()).isoformat()
        close_client = client_factory is None
        client = (
            client_factory() if client_factory else httpx.AsyncClient(follow_redirects=False, trust_env=False)
        )
        try:
            for template in feed_urls:
                if not template or "{year}" not in template:
                    continue
                try:
                    url = template.replace("{year}", str(year))
                    raw = await self._fetch_bytes(client, url, timeout_seconds)
                    parsed = parse_holiday_payload(year, raw, synced_at)
                    self._save_year(year, parsed)
                    return True
                except Exception:
                    continue
            return False
        finally:
            if close_client:
                await client.aclose()
