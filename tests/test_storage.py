from datetime import datetime
import json
import shutil

import pandas as pd
import pytest

from parcom_analytics.storage import LocalStore, parse_filename, read_workbook, reporting_month
from conftest import filename


@pytest.mark.parametrize("kpi", range(1, 8))
def test_filename_metadata(kpi):
    metadata = parse_filename(filename(kpi))
    assert metadata.kpi_number == kpi
    assert metadata.export_timestamp == "2026-09-29T10:52:00+02:00"
    assert metadata.timezone == "Europe/Zurich"
    assert metadata.reporting_month == ("2026-08" if kpi in {1, 2, 5, 6} else None)


@pytest.mark.parametrize("name", ["report.xlsx", filename(8), filename().replace(".xlsx", ".xls"),
                                  filename(date="2026-02-30"), filename(time="25-15"),
                                  filename(zone="Not_A_Zone"), filename().replace("KPI_7", "KPI_77")])
def test_invalid_filename(name):
    with pytest.raises(ValueError, match="Dateiname nicht erkannt"):
        parse_filename(name)


def test_timezone_with_underscore_in_city():
    metadata = parse_filename(filename(zone="America_Argentina_Buenos_Aires"))
    assert metadata.timezone == "America/Argentina/Buenos_Aires"
    assert metadata.export_timestamp.endswith("-03:00")


@pytest.mark.parametrize("date, expected", [("2026-09-29", "2026-08"), ("2026-01-01", "2025-12"),
                                           ("2024-03-01", "2024-02")])
def test_reporting_month(date, expected):
    assert reporting_month(datetime.fromisoformat(date)) == expected


def test_import_duplicate_and_persistence(tmp_path, tickets):
    source = tmp_path / filename()
    tickets.to_excel(source, index=False)
    store = LocalStore(tmp_path / "storage")
    assert store.index_path.exists()
    assert store.import_file(source).status == "Importiert"
    renamed = source.with_name(source.name.replace("Test", "Other_title"))
    shutil.copyfile(source, renamed)
    assert store.import_file(renamed).status == "Bereits importiert"
    assert len(store.records) == 1
    record = store.records[0]
    assert len(record.sha256) == 64
    source.unlink()
    renamed.unlink()
    restarted = LocalStore(store.root)
    assert restarted.records == store.records
    assert len(read_workbook(restarted.root / record.stored_path)) == 6
    assert len(list((store.root / "data").iterdir())) == 7


def test_same_content_new_timestamp_and_other_kpi_are_distinct_exports(tmp_path, tickets):
    first = tmp_path / filename(3)
    tickets.to_excel(first, index=False)
    store = LocalStore(tmp_path / "storage")
    store.import_file(first)
    for name in [filename(3, time="11-52"), filename(7)]:
        source = tmp_path / name
        shutil.copyfile(first, source)
        assert store.import_file(source).status == "Importiert"
    assert store.latest(3).export_timestamp.endswith("11:52:00+02:00")


def test_months_and_newest_export(tmp_path, tickets):
    store = LocalStore(tmp_path / "storage")
    for date, time in [("2026-09-29", "10-52"), ("2026-08-12", "12-00"), ("2026-09-30", "08-00")]:
        source = tmp_path / filename(1, date, time)
        tickets.to_excel(source, index=False)
        store.import_file(source)
    assert store.months(1) == ["2026-08", "2026-07"]
    assert "2026-09-30" in store.latest(1, "2026-08").export_timestamp
    assert store.latest(1, "2025-12") is None
    assert store.latest(7) is None


def test_corrupt_index_is_preserved(tmp_path):
    root = tmp_path / "storage"
    root.mkdir()
    index = root / "index.json"
    index.write_text("not json", encoding="utf-8")
    store = LocalStore(root)
    assert store.records == []
    assert store.warning
    backup = list(root.glob("index.corrupt-*.json"))
    assert len(backup) == 1
    assert backup[0].read_text() == "not json"
    assert json.loads(index.read_text()) == []


def test_index_rejects_paths_outside_storage(tmp_path, tickets):
    source = tmp_path / filename()
    tickets.to_excel(source, index=False)
    store = LocalStore(tmp_path / "storage")
    store.import_file(source)
    payload = json.loads(store.index_path.read_text(encoding="utf-8"))
    payload[0]["stored_path"] = "../../external.xlsx"
    store.index_path.write_text(json.dumps(payload), encoding="utf-8")
    assert LocalStore(store.root).warning


def test_invalid_excel_and_filename_status(tmp_path):
    store = LocalStore(tmp_path / "storage")
    source = tmp_path / filename()
    source.write_text("not a workbook")
    assert store.import_file(source).status == "Ungültige Excel-Datei"
    assert store.import_file(tmp_path / "invalid.xlsx").status == "Dateiname nicht erkannt"
    assert not store.records


def test_first_sheet_trimmed_columns_and_no_column_order_dependency(tmp_path, tickets):
    source = tmp_path / filename()
    tickets = tickets[tickets.columns[::-1]].rename(columns={"Ticket#": " Ticket# "})
    with pd.ExcelWriter(source, engine="openpyxl") as writer:
        tickets.to_excel(writer, index=False, sheet_name="First")
        pd.DataFrame({"ignore": [1]}).to_excel(writer, index=False, sheet_name="Second")
    frame = read_workbook(source)
    assert "Ticket#" in frame.columns
    assert len(frame) == 6
    assert "ignore" not in frame.columns


def test_missing_local_copy_can_be_reimported(tmp_path, tickets):
    source = tmp_path / filename()
    tickets.to_excel(source, index=False)
    store = LocalStore(tmp_path / "storage")
    store.import_file(source)
    (store.root / store.records[0].stored_path).unlink()
    assert store.import_file(source).status == "Importiert"
    assert len(store.records) == 1


def test_corrupted_local_copy_can_be_reimported(tmp_path, tickets):
    source = tmp_path / filename()
    tickets.to_excel(source, index=False)
    store = LocalStore(tmp_path / "storage")
    store.import_file(source)
    stored = store.root / store.records[0].stored_path
    stored.write_text("corrupted local copy")
    assert store.import_file(source).status == "Importiert"
    assert len(read_workbook(stored)) == 6
    assert len(store.records) == 1


def test_atomic_index_failure_does_not_publish_record(tmp_path, tickets, monkeypatch):
    source = tmp_path / filename()
    tickets.to_excel(source, index=False)
    store = LocalStore(tmp_path / "storage")
    def fail_save(records):
        raise PermissionError("synthetic write failure")
    monkeypatch.setattr(store, "_save", fail_save)
    with pytest.raises(PermissionError):
        store.import_file(source)
    assert store.records == []
    assert json.loads(store.index_path.read_text()) == []
