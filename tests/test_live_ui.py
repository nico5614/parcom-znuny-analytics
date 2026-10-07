import time
from unittest.mock import Mock

import pytest
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QLabel, QFileDialog, QMessageBox

from parcom_analytics import VERSION, DISPLAY_VERSION, WINDOWS_VERSION, PUBLISHER
from parcom_analytics.animations import Animator
from parcom_analytics.analytics import analyze, parse_age
from parcom_analytics.charts import draw_chart
from parcom_analytics.live_data import FIELD_MAP
from parcom_analytics.storage import LocalStore
from parcom_analytics.ui import MainWindow
from parcom_analytics.znuny import ConnectionError
from test_reports import pdf_text
from conftest import filename


def idle(qapp, window):
    deadline = time.monotonic()+10
    while time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(.005)
        if window.connection.worker is None and not window.refresh_after_login:
            qapp.processEvents()
            if window.connection.worker is None:
                return
    raise AssertionError("Network worker did not finish")


def test_live_login_refresh_all_kpis_pdf_failure_reconnect_logout(qapp, tmp_path, tickets, monkeypatch):
    window = MainWindow(LocalStore(tmp_path / "store"), require_login=True)
    window.showMaximized()
    client = Mock(connected=False, _session_id=None)
    def login(*args):
        client.connected, client._session_id = True, "synthetic-session"
    def logout():
        client.connected, client._session_id = False, None
    client.login.side_effect, client.logout.side_effect = login, logout
    client.search_tickets.return_value = [str(number) for number in range(1, 7)]
    raw = [{**{key: row.get(column) for key, column in FIELD_MAP.items()}, "TicketID": str(index),
            "Age": parse_age(row["Alter"]) * 60, "Queue": "PBX", "Created": "2026-10-01 10:00:00", "Closed": "2026-10-02 10:00:00"}
           for index, row in enumerate(tickets.to_dict("records"), 1)]
    client.get_tickets.return_value = raw
    client.get_history.return_value = []
    window.connection.client = client
    assert window.gate.currentIndex() == 1 and window.isMaximized()
    window.username.setText("synthetic-user")
    window.password.setText("synthetic-password")
    window.login()
    assert window.password.text() == ""
    idle(qapp, window)
    assert window.gate.currentIndex() == 0
    assert window.connection.state == "online"
    assert window.refresh_button.isEnabled()
    assert len(window.live_reports) == 7
    window.navigate(4)
    window.download_combo.setCurrentIndex(5)
    assert window.analysis is None
    target = tmp_path / "live.pdf"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(target), ""))
    monkeypatch.setattr(QMessageBox, "information", lambda *args: None)
    window.save_pdf()
    assert "ZnunyLive" in pdf_text(target) and "25min" in pdf_text(target)
    assert "Datenstand:" in pdf_text(target) and "Europe/Zurich" in pdf_text(target)
    window.navigate(2)
    for kpi in range(1, 8):
        window.kpi_combo.setCurrentIndex(kpi)
        assert window.analysis.kpi == kpi
        assert not window.month_combo.isVisible() and not window.snapshot_combo.isVisible()
    previous = window.live_cache.path.read_bytes()
    client.search_tickets.side_effect = ConnectionError("Keine Verbindung zu Znuny möglich.")
    window.refresh_live()
    idle(qapp, window)
    assert window.connection.state == "offline" and not window.refresh_button.isEnabled()
    assert window.analysis.kpi == 7
    assert window.live_cache.path.read_bytes() == previous
    client.search_tickets.side_effect = None
    window.show_login()
    window.username.setText("synthetic-user")
    window.password.setText("synthetic-password")
    window.login()
    idle(qapp, window)
    assert window.connection.state == "online"
    window.logout()
    idle(qapp, window)
    assert window.gate.currentIndex() == 1 and client._session_id is None
    window.close()
    restarted = MainWindow(LocalStore(tmp_path / "store"), require_login=True)
    restarted.enter_offline()
    restarted.source_combo.setCurrentIndex(1)
    restarted.kpi_combo.setCurrentIndex(3)
    assert restarted.analysis.metrics["Aktuell offene Tickets"] == 6
    assert not restarted.refresh_button.isEnabled()
    restarted.close()


def test_animations_finish_and_reduced_motion(qapp, tickets):
    canvas = FigureCanvasQTAgg(Figure())
    canvas.show()
    animator = Animator(reduced=False)
    for kpi in [1, 4, 5]:
        draw_chart(canvas.figure, analyze(kpi, tickets))
        canvas.draw()
        animator.chart(canvas)
        assert canvas in animator.active
        deadline = time.monotonic() + 2
        while canvas in animator.active and time.monotonic() < deadline:
            QTest.qWait(20)
        assert canvas not in animator.active
        if kpi == 4:
            assert round(sum(wedge.theta2-wedge.theta1 for wedge in canvas.figure.axes[0].patches)) == 360
    widget = QLabel()
    widget.show()
    animator.count(widget, 10, 20, lambda value: str(round(value)))
    deadline = time.monotonic() + 2
    while widget in animator.active and time.monotonic() < deadline:
        QTest.qWait(20)
    assert widget.text() == "20"
    animator.fade(widget)
    deadline = time.monotonic() + 2
    while widget in animator.active and time.monotonic() < deadline:
        QTest.qWait(20)
    assert widget.graphicsEffect() is None
    animator.reduced = True
    animator.count(widget, 20, 30, lambda value: str(round(value)))
    assert widget.text() == "30" and not animator.active
    canvas.close()
    widget.close()


def test_reduced_motion_setting_persists_and_versions(qapp, tmp_path):
    store = LocalStore(tmp_path)
    window = MainWindow(store)
    window.reduce_motion.setChecked(False)
    window.reduce_motion.setChecked(True)
    window.close()
    restarted = MainWindow(store)
    assert restarted.settings.value("reduce_motion", type=bool)
    assert VERSION == "1.0.0" and DISPLAY_VERSION == "1.0" and WINDOWS_VERSION == "1.0.0.0"
    assert PUBLISHER == "Nico Köchli"
    restarted.close()


@pytest.mark.parametrize("action", ["offline", "close"])
def test_active_session_ends_before_offline_or_close(qapp, tmp_path, action):
    window = MainWindow(LocalStore(tmp_path), require_login=True)
    window.show()
    client = Mock(connected=True, _session_id="synthetic-session")
    def logout():
        client._session_id, client.connected = None, False
    client.logout.side_effect = logout
    window.connection.client = client
    window.connection._set_state("online")
    if action == "offline":
        window.enter_offline()
    else:
        window.close()
    idle(qapp, window)
    qapp.processEvents()
    client.logout.assert_called_once()
    assert client._session_id is None and window.connection.state == "offline"
    if action == "offline":
        assert window.gate.currentIndex() == 0 and window.isVisible()
        window.close()
    else:
        assert not window.isVisible()


def test_dataset_deletion_requires_confirmation_and_updates_views(qapp, tmp_path, tickets, monkeypatch):
    source = tmp_path / filename(3)
    tickets.to_excel(source, index=False)
    store = LocalStore(tmp_path / "store")
    store.import_file(source)
    window = MainWindow(store)
    window.kpi_combo.setCurrentIndex(3)
    assert window.analysis.kpi == 3
    window.dataset_table.selectRow(0)
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.No)
    window.delete_dataset()
    assert len(store.records) == 1
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    window.delete_dataset()
    assert not store.records and window.analysis is None
    assert window.dataset_table.model().rowCount() == 0 and source.exists()
    window.close()
