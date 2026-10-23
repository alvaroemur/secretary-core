"""Translate 5-field cron expressions into launchd StartCalendarInterval dicts.

Stdlib only: install-routine-schedule.sh imports this module from a bare `python3`.
"""

from __future__ import annotations

from itertools import product

WEEKDAY_NAMES = {"sun": 0, "mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6}
MONTH_NAMES = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _value(token: str, names: dict[str, int], field: str) -> int:
    if token.isdigit():
        return int(token)
    if token.lower() in names:
        return names[token.lower()]
    raise ValueError(f"unsupported cron field: {field}")


def expand_field(field: str, lo: int, hi: int, names: dict[str, int] | None = None) -> list[int]:
    """Expand `*`, lists (`1,3`), ranges (`1-5`) and steps (`*/15`, `8-18/2`)."""
    names = names or {}
    out: set[int] = set()
    for chunk in field.split(","):
        base, has_step, step_s = chunk.partition("/")
        if has_step and not step_s.isdigit() or step_s == "0":
            raise ValueError(f"unsupported cron field: {field}")
        step = int(step_s) if has_step else 1
        if base == "*":
            start, end = lo, hi
        elif "-" in base:
            a, b = base.split("-", 1)
            start, end = _value(a, names, field), _value(b, names, field)
        else:
            start = _value(base, names, field)
            end = hi if has_step else start
        if start > end:
            raise ValueError(f"unsupported cron field: {field}")
        out.update(range(start, end + 1, step))
    if min(out) < lo or max(out) > hi:
        raise ValueError(f"cron field out of range: {field}")
    return sorted(out)


def parse_cron(cron: str) -> list[dict[str, int]]:
    parts = cron.split()
    if len(parts) != 5:
        raise ValueError(f"unsupported cron: {cron}")
    minute_s, hour_s, dom_s, mon_s, dow_s = parts
    if dom_s != "*" and dow_s != "*":
        # cron ORs day-of-month and weekday; launchd ANDs the keys of one interval.
        raise ValueError(f"unsupported cron (day-of-month and weekday both set): {cron}")

    fields: dict[str, list[int]] = {}
    if dow_s != "*":
        # 7 is also Sunday; launchd uses 0.
        fields["Weekday"] = sorted({d % 7 for d in expand_field(dow_s, 0, 7, WEEKDAY_NAMES)})
    if mon_s != "*":
        fields["Month"] = expand_field(mon_s, 1, 12, MONTH_NAMES)
    if dom_s != "*":
        fields["Day"] = expand_field(dom_s, 1, 31)
    fields["Hour"] = expand_field(hour_s, 0, 23)
    fields["Minute"] = expand_field(minute_s, 0, 59)

    return [dict(zip(fields, combo)) for combo in product(*fields.values())]
