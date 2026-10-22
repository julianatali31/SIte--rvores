"""pt-BR relative-time text. Pure: `now` and `tz` are always passed in."""
from datetime import datetime, tzinfo

WEEKDAYS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def relative(when: datetime, now: datetime) -> str:
    """'agora mesmo', 'há 5 min', 'há 3 h', 'há 2 dias'."""
    seconds = max((now - when).total_seconds(), 0)
    minutes = int(seconds // 60)
    if minutes < 1:
        return "agora mesmo"
    if minutes < 60:
        return f"há {minutes} min"
    hours = minutes // 60
    if hours < 24:
        return f"há {hours} h"
    return "há " + _plural(hours // 24, "dia", "dias")


def calendar_label(when: datetime, now: datetime, tz: tzinfo) -> str:
    """'hoje, 08:10', 'ontem, 08:10', 'seg 19/10, 08:10' in local time."""
    local, local_now = when.astimezone(tz), now.astimezone(tz)
    hhmm = local.strftime("%H:%M")
    days = (local_now.date() - local.date()).days
    if days == 0:
        return f"hoje, {hhmm}"
    if days == 1:
        return f"ontem, {hhmm}"
    day = local.strftime("%d/%m") if local.year == local_now.year else local.strftime("%d/%m/%Y")
    return f"{WEEKDAYS[local.weekday()]} {day}, {hhmm}"


def date_label(when: datetime, tz: tzinfo) -> str:
    local = when.astimezone(tz)
    return f"{WEEKDAYS[local.weekday()]} {local.strftime('%d/%m')}"


def age(planted_at: datetime, now: datetime, tz: tzinfo) -> str:
    """'plantada hoje', 'plantada há 12 dias', 'plantada há 3 meses', 'plantada há 1 ano e 2 meses'."""
    days = (now.astimezone(tz).date() - planted_at.astimezone(tz).date()).days
    if days <= 0:
        return "plantada hoje"
    if days < 60:
        return "plantada há " + _plural(days, "dia", "dias")
    months = max(2, days * 12 // 365)
    if months < 24:
        return "plantada há " + _plural(months, "mês", "meses")
    years, rest = divmod(months, 12)
    text = "plantada há " + _plural(years, "ano", "anos")
    return text + (" e " + _plural(rest, "mês", "meses") if rest else "")
