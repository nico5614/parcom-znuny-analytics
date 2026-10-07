import time
from unittest.mock import Mock

from PySide6.QtCore import QTimer

from parcom_analytics.connection import ConnectionController
from parcom_analytics.znuny import LoginError


def finish(qapp, controller):
    deadline = time.monotonic()+5
    while controller.worker and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(.005)
    assert controller.worker is None


def test_background_login_responsive_and_logout(qapp):
    client = Mock()
    client.login.side_effect = lambda *args: time.sleep(.05)
    controller = ConnectionController(client=client)
    ticks, logins, logouts = [], [], []
    timer = QTimer()
    timer.timeout.connect(lambda: ticks.append(1))
    timer.start(5)
    controller.loggedIn.connect(lambda: logins.append(1))
    controller.loggedOut.connect(lambda: logouts.append(1))
    controller.login("synthetic", "password")
    finish(qapp, controller)
    assert len(ticks) > 2 and logins == [1]
    assert controller.state == "online"
    controller.logout()
    finish(qapp, controller)
    assert logouts == [1] and controller.state == "offline"
    client.logout.assert_called_once()
    timer.stop()


def test_failed_login_does_not_activate_online(qapp):
    client = Mock()
    client.login.side_effect = LoginError("Anmeldung fehlgeschlagen.")
    controller = ConnectionController(client=client)
    errors = []
    controller.failed.connect(errors.append)
    controller.login("synthetic", "password")
    finish(qapp, controller)
    assert controller.state == "offline" and errors == ["Anmeldung fehlgeschlagen."]


def test_close_while_login_running_cleans_session(qapp):
    client = Mock()
    client.login.side_effect = lambda *args: time.sleep(.03)
    controller = ConnectionController(client=client)
    controller.login("synthetic", "password")
    controller.logout()
    finish(qapp, controller)
    client.logout.assert_called_once()
    assert controller.state == "offline"
