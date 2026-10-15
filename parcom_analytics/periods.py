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
        if self.end <= self.start:
            raise DataError("Bitte wählen Sie einen Zeitraum von mindestens einem Tag.")
        if self.start.date() < months_before(self.end, 12).date():
            raise DataError("Bitte wählen Sie einen Zeitraum von höchstens einem Jahr.")
        if self.end > now() + timedelta(seconds=2):
            raise DataError("Das Bis-Datum darf nicht in der Zukunft liegen.")

    @property
    def label(self):
        return f"{self.start:%d.%m.%Y} – {self.end:%d.%m.%Y}"

    @classmethod
    def preset(cls, key="1W", end=None):
        end = end or now()
        midnight = end.replace(hour=0, minute=0, second=0, microsecond=0)
        start = (midnight - timedelta(days=0 if key == "1T" else 6) if key in {"1T", "1W"}
                 else months_before(midnight, 12 if key == "1J" else int(key[:-1])))
        return cls(start, end)

    @classmethod
    def dates(cls, start, end):
        """Inclusive selected dates, with today's incomplete day ending at the live clock."""
        current = now()
        first = datetime.combine(start, datetime.min.time(), ZURICH)
        last = datetime.combine(end, datetime.max.time().replace(microsecond=0), ZURICH)
        if end > current.date():
            raise DataError("Das Bis-Datum darf nicht in der Zukunft liegen.")
        return cls(first, min(last, current))


    @property
    def previous(self):
        # UTC subtraction makes the preceding comparison equal in elapsed duration at DST boundaries.
        end = self.start.astimezone(timezone.utc)
        duration = self.end.astimezone(timezone.utc) - end
        return (end - duration).astimezone(ZURICH), self.start

    def buckets(self):
        # Calendar days in Zurich; never label a noon-to-noon bucket as a day.
        edges = [self.start]
        midnight = self.start.replace(hour=0, minute=0, second=0, microsecond=0)
        boundary = midnight + timedelta(days=1)
        while boundary < self.end:
            edges.append(boundary)
            boundary += timedelta(days=1)
        return [*edges, self.end]
