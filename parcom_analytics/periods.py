"""Exact, timezone-aware rolling and custom reporting intervals."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import calendar

from .analytics import DataError

ZURICH = ZoneInfo("Europe/Zurich")
PRESETS = ("1J", "6M", "3M", "1M", "1W", "1T")


def now():
    return datetime.now(ZURICH).replace(microsecond=0)


def months_before(value, count):
    year, month = divmod(value.year * 12 + value.month - 1 - count, 12)
    return value.replace(year=year, month=month + 1,
                         day=min(value.day, calendar.monthrange(year, month + 1)[1]))


@dataclass(frozen=True)
class TimeRange:
    start: datetime
    end: datetime

    def __post_init__(self):
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise DataError("Der Zeitraum benötigt eine Zeitzone.")
        if self.end - self.start < timedelta(days=1):
            raise DataError("Bitte wählen Sie einen Zeitraum von mindestens einem Tag.")
        if self.start < months_before(self.end, 12):
            raise DataError("Bitte wählen Sie einen Zeitraum von höchstens einem Jahr.")
        if self.end > now() + timedelta(seconds=2):
            raise DataError("Das Bis-Datum darf nicht in der Zukunft liegen.")

    @property
    def label(self):
        return f"{self.start:%d.%m.%Y %H:%M} – {self.end:%d.%m.%Y %H:%M}"

    @classmethod
    def preset(cls, key="1W", end=None):
        end = end or now()
        start = (end - timedelta(days=1 if key == "1T" else 7) if key in {"1T", "1W"}
                 else months_before(end, 12 if key == "1J" else int(key[:-1])))
        return cls(start, end)

    @property
    def previous(self):
        # UTC subtraction makes the preceding comparison equal in elapsed duration at DST boundaries.
        end = self.start.astimezone(timezone.utc)
        duration = self.end.astimezone(timezone.utc) - end
        return (end - duration).astimezone(ZURICH), self.start

    def buckets(self):
        duration = self.end - self.start
        if duration <= timedelta(days=1):
            step = timedelta(hours=2)
        elif duration <= timedelta(days=32):
            step = timedelta(days=1)
        else:
            edges = [self.end]
            count = 1
            while months_before(self.end, count) > self.start:
                edges.append(months_before(self.end, count))
                count += 1
            return [self.start, *reversed(edges)]
        edges = [self.start]
        while edges[-1] + step < self.end:
            edges.append(edges[-1] + step)
        return [*edges, self.end]
