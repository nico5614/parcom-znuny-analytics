from parcom_analytics.web.bridge import DesktopBridge


def test_theme_defaults_light_before_login_and_respects_saved_preferences(tmp_path):
    bridge = DesktopBridge(root=tmp_path)
    assert bridge.getPreferences() == {"theme": "light", "reducedMotion": False}
    assert bridge.setPreferences("dark", True)["ok"]
    restored = DesktopBridge(root=tmp_path)
    assert restored.getPreferences() == {"theme": "dark", "reducedMotion": True}
    assert not restored.setPreferences("invalid", False)["ok"]


def test_last_connection_changes_only_on_successful_backend_operations(tmp_path):
    from parcom_analytics.web.validation import ValidationClient, validation_batch
    client = ValidationClient()
    bridge = DesktopBridge(root=tmp_path, client=client, fetch=validation_batch)
    assert bridge.getState()["lastSuccessfulConnection"] is None
    assert bridge.login("validation", "validation")["ok"]
    connected = bridge.getState()["lastSuccessfulConnection"]
    assert connected is not None
    bridge._fetch = lambda period: (_ for _ in ()).throw(RuntimeError("failed request"))
    assert not bridge.refresh({"preset": "1W"})["ok"]
    assert bridge.getState()["lastSuccessfulConnection"] == connected
    bridge._fetch = validation_batch
    assert bridge.refresh({"preset": "1W"})["ok"]
    assert bridge.getState()["lastSuccessfulConnection"] >= connected
    assert not bridge.login("wrong", "wrong")["ok"]
    assert bridge.getState()["lastSuccessfulConnection"] is not None
