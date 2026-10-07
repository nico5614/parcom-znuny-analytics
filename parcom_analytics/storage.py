"""Filename metadata, workbook loading and atomic local persistence."""

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shutil
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

import pandas as pd

LOGGER = logging.getLogger(__name__)
MONTHLY_KPIS = {1, 2, 5, 6}
MONTH_NAMES = ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
               "August", "September", "Oktober", "November", "Dezember")
FILENAME_PATTERN = re.compile(
    r"^KPI_(?P<kpi>[1-7])_.*?Created_(?P<date>\d{4}-\d{2}-\d{2})_"
    r"(?P<time>\d{2}-\d{2})_TimeZone_(?P<zone>[A-Za-z0-9_+\-/]+)\.xlsx$",
    re.IGNORECASE,
)
TIMEZONES = {zone.replace("/", "_"): zone for zone in available_timezones()}


@dataclass(frozen=True)
class FileMetadata:
    kpi_number: int
    export_timestamp: str
    timezone: str
    reporting_month: str | None


@dataclass(frozen=True)
class ImportRecord(FileMetadata):
    original_filename: str
    stored_filename: str
    stored_path: str
    sha256: str


@dataclass(frozen=True)
class ImportResult:
    filename: str
    status: str
    metadata: FileMetadata | None = None


def default_storage_path() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return base / "ParCom" / "ZnunyAnalytics"


def reporting_month(timestamp: datetime) -> str:
    return (timestamp.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")


def month_label(month: str) -> str:
    year, number = map(int, month.split("-"))
    return f"{MONTH_NAMES[number - 1]} {year}"


def period_label(metadata: FileMetadata) -> str:
    if getattr(metadata, "period_start", None):
        start, end = datetime.fromisoformat(metadata.period_start), datetime.fromisoformat(metadata.period_end)
        return f"{start:%d.%m.%Y} – {end:%d.%m.%Y}"
    if metadata.reporting_month:
        return month_label(metadata.reporting_month)
    timestamp = datetime.fromisoformat(metadata.export_timestamp)
    return f"Datenstand: {timestamp:%d.%m.%Y} – {timestamp:%H:%M} Uhr"


def parse_filename(filename: str) -> FileMetadata:
    match = FILENAME_PATTERN.fullmatch(Path(filename).name)
    if not match:
        raise ValueError("Dateiname nicht erkannt")
    zone = TIMEZONES.get(match["zone"], match["zone"])
    try:
        timestamp = datetime.strptime(f'{match["date"]}_{match["time"]}', "%Y-%m-%d_%H-%M")
        timestamp = timestamp.replace(tzinfo=ZoneInfo(zone))
    except (ValueError, ZoneInfoNotFoundError) as error:
        raise ValueError("Dateiname nicht erkannt") from error
    kpi = int(match["kpi"])
    return FileMetadata(kpi, timestamp.isoformat(), zone,
                        reporting_month(timestamp) if kpi in MONTHLY_KPIS else None)


def read_workbook(path: Path) -> pd.DataFrame:
    frame = pd.read_excel(path, sheet_name=0, engine="openpyxl", dtype=object)
    frame.columns = [str(column).strip() for column in frame.columns]
    if not frame.columns.is_unique:
        raise ValueError("Die Datei enthält doppelte Spaltennamen.")
    return frame.dropna(how="all").reset_index(drop=True)


def file_hash(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


class LocalStore:
    def __init__(self, root: Path | None = None):
        self.root = root if root is not None else default_storage_path()
        self.index_path = self.root / "index.json"
        self.records: list[ImportRecord] = []
        self.warning = ""
        for directory in ["exports", "logs", *(f"data/kpi_{kpi}" for kpi in range(1, 8))]:
            (self.root / directory).mkdir(parents=True, exist_ok=True)
        self._load()

    def _save(self, records: list[ImportRecord]) -> None:
        temporary = self.index_path.with_suffix(".json.tmp")
        with temporary.open("w", encoding="utf-8") as output:
            json.dump([asdict(record) for record in records], output, ensure_ascii=False, indent=2)
            output.flush()
            os.fsync(output.fileno())
        temporary.replace(self.index_path)
        self.records = records

    def _validate_record(self, item: dict) -> ImportRecord:
        record = ImportRecord(**item)
        metadata = parse_filename(record.original_filename)
        if any(getattr(record, key) != value for key, value in asdict(metadata).items()):
            raise ValueError("Inconsistent index metadata")
        if not re.fullmatch(r"[0-9a-f]{64}", record.sha256):
            raise ValueError("Invalid digest")
        expected = Path("data") / f"kpi_{record.kpi_number}" / record.stored_filename
        if Path(record.stored_filename).name != record.stored_filename or Path(record.stored_path) != expected:
            raise ValueError("Invalid stored path")
        if not (self.root / expected).resolve().is_relative_to(self.root.resolve()):
            raise ValueError("Stored path escapes local storage")
        return record

    def _load(self) -> None:
        if not self.index_path.exists():
            self._save([])
            return
        try:
            payload = json.loads(self.index_path.read_text(encoding="utf-8"))
            if not isinstance(payload, list):
                raise ValueError("Index must be a list")
            self.records = [self._validate_record(item) for item in payload]
        except (ValueError, TypeError, KeyError, UnicodeError):
            LOGGER.error("Malformed index; preserving original index and imported workbooks")
            backup = self.root / f"index.corrupt-{datetime.now():%Y%m%d-%H%M%S-%f}.json"
            self.index_path.replace(backup)
            self.warning = ("Der lokale Dateiindex war beschädigt und wurde gesichert. "
                            "Vorhandene Excel-Dateien bleiben im Datenordner erhalten und können erneut importiert werden.")
            self._save([])

    def import_file(self, source: Path) -> ImportResult:
        try:
            metadata = parse_filename(source.name)
        except ValueError:
            LOGGER.warning("Filename parse failure")
            return ImportResult(source.name, "Dateiname nicht erkannt")
        try:
            read_workbook(source)
            digest = file_hash(source)
        except Exception as error:
            LOGGER.warning("Excel validation failed: %s", type(error).__name__)
            return ImportResult(source.name, "Ungültige Excel-Datei", metadata)
        for record in self.records:
            if (record.sha256 == digest and record.kpi_number == metadata.kpi_number
                    and record.export_timestamp == metadata.export_timestamp):
                stored = self.root / record.stored_path
                if stored.is_file() and file_hash(stored) == digest:
                    LOGGER.info("Duplicate import: KPI %s, SHA %s", metadata.kpi_number, digest[:12])
                    return ImportResult(source.name, "Bereits importiert", metadata)
        stamp = datetime.fromisoformat(metadata.export_timestamp).strftime("%Y%m%d-%H%M%z")
        filename = f"{stamp}_{digest}.xlsx"
        relative = Path("data") / f"kpi_{metadata.kpi_number}" / filename
        destination = self.root / relative
        temporary = destination.with_suffix(".xlsx.tmp")
        try:
            shutil.copyfile(source, temporary)
            if file_hash(temporary) != digest:
                raise OSError("Source file changed during import")
            temporary.replace(destination)
            record = ImportRecord(**asdict(metadata), original_filename=source.name,
                                  stored_filename=filename, stored_path=relative.as_posix(), sha256=digest)
            remaining = [existing for existing in self.records if existing.stored_path != record.stored_path]
            self._save([*remaining, record])
        finally:
            temporary.unlink(missing_ok=True)
        LOGGER.info("Imported KPI %s, SHA %s", metadata.kpi_number, digest[:12])
        return ImportResult(source.name, "Importiert", metadata)

    def months(self, kpi: int) -> list[str]:
        return sorted({record.reporting_month for record in self.records
                       if record.kpi_number == kpi and record.reporting_month}, reverse=True)

    def delete_record(self, record: ImportRecord) -> None:
        """Remove only a validated app-owned copy, rolling back a failed index write."""
        if record not in self.records:
            raise ValueError("Der Datensatz ist nicht mehr vorhanden.")
        self._validate_record(asdict(record))
        path = self.root / record.stored_path
        backup = path.with_suffix(".deleting")
        existed = path.exists()
        if existed:
            path.replace(backup)
        try:
            self._save([item for item in self.records if item != record])
        except Exception:
            if existed:
                backup.replace(path)
            raise
        if existed:
            backup.unlink()
        LOGGER.info("Deleted local dataset KPI %s", record.kpi_number)

    def latest(self, kpi: int, month: str | None = None) -> ImportRecord | None:
        candidates = [record for record in self.records if record.kpi_number == kpi
                      and (kpi not in MONTHLY_KPIS or record.reporting_month == month)]
        # For corrected exports with equal timestamps, prefer the last import.
        return max(reversed(candidates), key=lambda record: datetime.fromisoformat(record.export_timestamp), default=None)
