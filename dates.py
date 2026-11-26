"""Civil calendar and explicit lunar occurrences; no inferred lunar dates."""

import re
from datetime import date, datetime, timedelta

from lunar_python import Lunar, Solar

LUNAR_HOLIDAYS = {
    (1, 1): "春节",
    (1, 15): "元宵节",
    (5, 5): "端午节",
    (7, 7): "七夕",
    (8, 15): "中秋节",
    (9, 9): "重阳节",
    (12, 8): "腊八节",
}
SOLAR_HOLIDAYS = {
    (1, 1): "元旦",
    (2, 14): "情人节",
    (3, 8): "妇女节",
    (5, 1): "劳动节",
    (6, 1): "儿童节",
    (10, 1): "国庆节",
}


def civil_context(day, config):
    solar = Solar.fromYmd(day.year, day.month, day.day)
    lunar = solar.getLunar()
    names = []
    if config.enable_solar_terms and lunar.getJieQi():
        names.append(lunar.getJieQi())
    if config.enable_traditional_lunar_holidays:
        name = LUNAR_HOLIDAYS.get((lunar.getMonth(), lunar.getDay()))
        if name:
            names.append(name)
        next_lunar = solar.next(1).getLunar()
        if next_lunar.getMonth() == 1 and next_lunar.getDay() == 1:
            names.append("除夕")
    if config.enable_solar_holidays and (day.month, day.day) in SOLAR_HOLIDAYS:
        names.append(SOLAR_HOLIDAYS[(day.month, day.day)])
    return {
        "lunar": lunar.toString(),
        "solar_term": lunar.getJieQi() if config.enable_solar_terms else "",
        "names": list(dict.fromkeys(names)),
    }


def occurrence(entry, day):
    if entry.calendar == "solar":
        original = date.fromisoformat(entry.date)
        if not entry.yearly:
            return original
        for year in range(day.year, min(9999, day.year + 9)):
            try:
                target = original.replace(year=year)
            except ValueError:
                continue
            if target >= day:
                return target
        return None
    year, month, number = map(int, entry.date.split("-"))
    years = range(day.year - 1, day.year + 3) if entry.yearly else [year]
    for candidate in years:
        try:
            converted = Lunar.fromYmd(candidate, -month if entry.leap_month else month, number).getSolar()
            target = date(converted.getYear(), converted.getMonth(), converted.getDay())
        except Exception:
            continue
        if not entry.yearly or target >= day:
            return target
    return None


def parse_time(value, now):
    """Accept ISO, 今天/明天/后天 HH:MM, MM-DD HH:MM and 周五晚上8点."""
    if not value:
        return ""
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text)
        return (parsed.replace(tzinfo=now.tzinfo) if parsed.tzinfo is None else parsed).isoformat()
    except ValueError:
        pass
    target = now.date()
    match = re.match(r"^(今天|明天|后天)\s*", text)
    if match:
        target += timedelta(days={"今天": 0, "明天": 1, "后天": 2}[match[1]])
        text = text[match.end() :]
    else:
        match = re.match(r"^(?:周|星期)([一二三四五六日天])\s*", text)
        if match:
            weekday = "一二三四五六日".index(match[1].replace("天", "日"))
            target += timedelta(days=(weekday - now.weekday()) % 7)
            text = text[match.end() :]
        else:
            match = re.match(r"^(\d{2})-(\d{2})\s+", text)
            if match:
                target = date(now.year, int(match[1]), int(match[2]))
                if target < now.date():
                    target = target.replace(year=now.year + 1)
                text = text[match.end() :]
    match = re.fullmatch(
        r"(凌晨|早上|上午|中午|下午|晚上)?\s*(\d{1,2})(?::(\d{2})|点(?:(\d{1,2})分?)?)", text
    )
    if not match:
        raise ValueError("时间请用 今天/明天 20:00、12-01 09:30、周五晚上8点 或 ISO 日期")
    hour, minute = int(match[2]), int(match[3] or match[4] or 0)
    if match[1] in ("下午", "晚上") and hour < 12:
        hour += 12
    if match[1] == "中午" and hour < 11:
        hour += 12
    return datetime(target.year, target.month, target.day, hour, minute, tzinfo=now.tzinfo).isoformat()
